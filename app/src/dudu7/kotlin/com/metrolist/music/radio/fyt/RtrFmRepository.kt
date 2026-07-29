package com.metrolist.music.radio.fyt

import android.content.Context
import android.graphics.BitmapFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.Locale

data class RtrRepositoryState(
    val status: String = "Noch nicht geladen",
    val stationCount: Int = 0,
    val updatedAt: Long = 0L,
    val loading: Boolean = false,
    val error: String = "",
)

/**
 * Defensive local cache for the official RTR Senderkataster catalogue.
 * GPS coordinates never leave the head unit. The same Austria-wide catalogue is
 * downloaded for every user; relevant georeferenced coverage PNGs are sampled locally.
 */
class RtrFmRepository private constructor(context: Context) {
    private val appContext = context.applicationContext
    private val cacheDirectory = File(appContext.filesDir, "rtr_fm").apply { mkdirs() }
    private val catalogFile = File(cacheDirectory, "senderkataster-programs.json")
    private val coverageDirectory = File(cacheDirectory, "coverage").apply { mkdirs() }
    private val loadMutex = Mutex()
    private val coverageMutex = Mutex()
    private val _state = MutableStateFlow(RtrRepositoryState())
    val state: StateFlow<RtrRepositoryState> = _state.asStateFlow()

    @Volatile
    private var snapshot: RtrCatalogSnapshot? = null

    suspend fun refreshIfNeeded(force: Boolean = false): RtrCatalogSnapshot? =
        loadMutex.withLock {
            snapshot?.let { current ->
                if (!force && isFresh(catalogFile, CATALOG_MAX_AGE_MS)) return@withLock current
            }
            _state.value = _state.value.copy(
                loading = true,
                status = if (force) "RTR-Daten werden neu geladen …" else "RTR-Daten werden geladen …",
                error = "",
            )

            val cached = if (catalogFile.isFile) {
                runCatching { parseCatalog(catalogFile.readText()) }
                    .onFailure { Timber.tag(TAG).w(it, "Cached RTR catalogue is invalid") }
                    .getOrNull()
            } else null
            if (cached != null) {
                snapshot = cached
                publishState(cached, "RTR-Cache bereit")
            }
            if (!force && cached != null && isFresh(catalogFile, CATALOG_MAX_AGE_MS)) {
                _state.value = _state.value.copy(loading = false, status = "RTR-Cache aktuell")
                return@withLock cached
            }

            val downloaded = runCatching {
                val payload = downloadText(CATALOG_URL)
                val parsed = RtrFmCatalogParser.parse(payload, System.currentTimeMillis())
                require(parsed.stations.size >= MIN_EXPECTED_STATIONS) {
                    "RTR-Antwort enthält nur ${parsed.stations.size} UKW-Sender"
                }
                atomicWrite(catalogFile, payload)
                catalogFile.setLastModified(parsed.parsedAt)
                parsed
            }.onFailure { Timber.tag(TAG).w(it, "Could not refresh RTR catalogue") }.getOrNull()

            if (downloaded != null) {
                snapshot = downloaded
                publishState(downloaded, "RTR-Frequenzbuch aktuell")
                cleanupCoverageCache()
                downloaded
            } else {
                _state.value = _state.value.copy(
                    loading = false,
                    status = if (cached != null) "RTR offline – Cache wird verwendet" else "RTR-Daten nicht verfügbar",
                    error = if (cached == null) "Keine RTR-Daten geladen" else "",
                )
                cached
            }
        }

    suspend fun resolve(
        frequency: Float,
        rawPs: String,
        storedName: String?,
        pi: Int,
        location: FmGeoPoint?,
    ): RtrFmMatch? {
        val current = refreshIfNeeded() ?: return null
        val strengths = if (location == null) emptyMap() else {
            RtrFmMatcher.candidateCoverageCodes(current, frequency, rawPs, storedName, pi, location)
                .associateWith { code -> sampleCoverage(current, code, location) }
        }
        return RtrFmMatcher.resolve(current, frequency, rawPs, storedName, pi, location, strengths)
    }

    suspend fun alternatives(
        match: RtrFmMatch,
        currentFrequency: Float,
        location: FmGeoPoint?,
    ): List<RtrAfPrediction> {
        val current = refreshIfNeeded() ?: return emptyList()
        val strengths = if (location == null) emptyMap() else {
            RtrFmMatcher.candidateCoverageCodesForProgram(current, match.stableId, location)
                .associateWith { code -> sampleCoverage(current, code, location) }
        }
        return RtrFmMatcher.alternatives(current, match, currentFrequency, location, strengths)
    }

    fun cachedSnapshot(): RtrCatalogSnapshot? = snapshot

    private fun parseCatalog(payload: String): RtrCatalogSnapshot =
        RtrFmCatalogParser.parse(payload, catalogFile.lastModified().takeIf { it > 0L } ?: System.currentTimeMillis())

    private suspend fun sampleCoverage(current: RtrCatalogSnapshot, coverageCode: String, point: FmGeoPoint): Int =
        withContext(Dispatchers.IO) {
            val station = current.stations.firstOrNull {
                it.coverageCode == coverageCode && it.coverageImageUrl.isNotBlank() &&
                    it.coverageBounds?.contains(point) == true
            } ?: return@withContext 0
            val bounds = station.coverageBounds ?: return@withContext 0
            val file = coverageFile(station) ?: return@withContext 0
            val options = BitmapFactory.Options().apply {
                inPreferredConfig = android.graphics.Bitmap.Config.ARGB_8888
            }
            val bitmap = BitmapFactory.decodeFile(file.absolutePath, options) ?: return@withContext 0
            try {
                val pixel = RtrCoverageProjection.pixelFor(bounds, bitmap.width, bitmap.height, point)
                    ?: return@withContext 0
                RtrCoverageProjection.strengthFromArgb(bitmap.getPixel(pixel.first, pixel.second))
            } finally {
                bitmap.recycle()
            }
        }

    private suspend fun coverageFile(station: RtrFmStation): File? = coverageMutex.withLock {
        val url = station.coverageImageUrl
        if (url.isBlank()) return@withLock null
        val target = File(coverageDirectory, "${station.coverageCode}_${sha256(url).take(12)}.png")
        if (target.isFile && target.length() > 0 && isFresh(target, COVERAGE_MAX_AGE_MS)) {
            target.setLastModified(System.currentTimeMillis())
            return@withLock target
        }
        runCatching {
            downloadFile(url, target)
            cleanupCoverageCache()
            target
        }.onFailure {
            Timber.tag(TAG).w(it, "Could not download RTR coverage %s", station.coverageCode)
        }.getOrNull()
    }

    private fun cleanupCoverageCache() {
        val files = coverageDirectory.listFiles()?.filter(File::isFile).orEmpty().sortedByDescending(File::lastModified)
        var total = files.sumOf(File::length)
        files.drop(MAX_COVERAGE_FILES).forEach { file ->
            total -= file.length()
            file.delete()
        }
        if (total <= MAX_COVERAGE_BYTES) return
        files.asReversed().forEach { file ->
            if (total <= MAX_COVERAGE_BYTES) return
            total -= file.length()
            file.delete()
        }
    }

    private fun publishState(catalog: RtrCatalogSnapshot, status: String) {
        _state.value = RtrRepositoryState(
            status = status,
            stationCount = catalog.stations.size,
            updatedAt = catalog.parsedAt,
            loading = false,
        )
    }

    private fun downloadText(url: String): String = openConnection(url).let { connection ->
        try {
            connection.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }

    private fun downloadFile(url: String, target: File) {
        val temporary = File(target.parentFile, "${target.name}.tmp")
        openConnection(url).let { connection ->
            try {
                connection.inputStream.use { input ->
                    temporary.outputStream().buffered().use { output -> input.copyTo(output) }
                }
            } finally {
                connection.disconnect()
            }
        }
        require(temporary.length() > 0) { "Leere RTR-Abdeckungskarte" }
        if (target.exists()) target.delete()
        require(temporary.renameTo(target)) { "RTR-Abdeckungskarte konnte nicht gespeichert werden" }
    }

    private fun openConnection(url: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 35_000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.25")
            setRequestProperty("Accept", "application/json,image/png,*/*")
            val code = responseCode
            if (code !in 200..299) {
                disconnect()
                error("RTR HTTP $code")
            }
        }

    private fun atomicWrite(target: File, content: String) {
        val temporary = File(target.parentFile, "${target.name}.tmp")
        temporary.writeText(content)
        if (target.exists()) target.delete()
        require(temporary.renameTo(target)) { "RTR-Cache konnte nicht gespeichert werden" }
    }

    private fun isFresh(file: File, maxAge: Long): Boolean =
        file.isFile && System.currentTimeMillis() - file.lastModified() < maxAge

    private fun sha256(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray()).joinToString("") { "%02x".format(Locale.ROOT, it) }

    companion object {
        private const val TAG = "RtrFmRepository"
        private const val CATALOG_URL = "https://senderkataster.rtr.at/programs/"
        private const val CATALOG_MAX_AGE_MS = 7L * 24L * 60L * 60L * 1000L
        private const val COVERAGE_MAX_AGE_MS = 30L * 24L * 60L * 60L * 1000L
        private const val MAX_COVERAGE_BYTES = 48L * 1024L * 1024L
        private const val MAX_COVERAGE_FILES = 12
        private const val MIN_EXPECTED_STATIONS = 500

        @Volatile private var instance: RtrFmRepository? = null

        fun get(context: Context): RtrFmRepository = instance ?: synchronized(this) {
            instance ?: RtrFmRepository(context).also { instance = it }
        }
    }
}
