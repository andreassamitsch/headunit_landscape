package com.metrolist.music.radio.fyt

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.metrolist.music.R
import com.metrolist.music.radio.RadioDnsLogoResolver
import com.metrolist.music.radio.RadioLogoCandidate
import com.metrolist.music.radio.RadioLogoSource
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationLogoCache
import com.metrolist.music.radio.RadioStationLogoResolver
import com.metrolist.music.radio.RadioStationLogoSearch
import com.metrolist.music.radio.RadioStationStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.roundToInt

/** Shared FM logo resolver: manual override, RadioDNS, local WebRadio and multi-source search. */
object FmStationLogoResolver {
    private const val TAG = "FmStationLogo"
    private const val PREFS = "dudu7_fm_station_logos_v2"
    private const val AUTO_PREFIX = "logo_" // Keep the old key for migration compatibility.
    private const val MANUAL_PREFIX = "manual_"
    private const val SOURCE_PREFIX = "source_"
    private const val SOURCE_URL_PREFIX = "source_url_"
    private const val UPDATED_PREFIX = "updated_"
    private const val MANUAL_SOURCE_PREFIX = "manual_source_"
    private const val MANUAL_SOURCE_URL_PREFIX = "manual_source_url_"
    private const val MANUAL_UPDATED_PREFIX = "manual_updated_"
    private const val RETRY_COOLDOWN_MS = 10L * 60L * 1000L
    private const val AUTO_REFRESH_MS = 30L * 24L * 60L * 60L * 1000L

    data class LogoInfo(
        val localUri: String,
        val sourceLabel: String,
        val sourceUrl: String,
        val manual: Boolean,
        val updatedAt: Long,
    )

    private val failedAt = ConcurrentHashMap<String, Long>()
    private val _revisions = MutableStateFlow(0L)
    val revisions: StateFlow<Long> = _revisions.asStateFlow()

    fun logoInfo(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ): LogoInfo? {
        val key = cacheKey(stationName, frequency, pi)
        val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val manual = prefs.getString(MANUAL_PREFIX + key, null)
        if (!manual.isNullOrBlank()) {
            return LogoInfo(
                localUri = manual,
                sourceLabel = prefs.getString(MANUAL_SOURCE_PREFIX + key, "Manuell gewählt").orEmpty(),
                sourceUrl = prefs.getString(MANUAL_SOURCE_URL_PREFIX + key, "").orEmpty(),
                manual = true,
                updatedAt = prefs.getLong(MANUAL_UPDATED_PREFIX + key, 0L),
            )
        }
        val automatic = prefs.getString(AUTO_PREFIX + key, null) ?: return null
        return LogoInfo(
            localUri = automatic,
            sourceLabel = prefs.getString(SOURCE_PREFIX + key, "Automatik-Cache").orEmpty(),
            sourceUrl = prefs.getString(SOURCE_URL_PREFIX + key, "").orEmpty(),
            manual = false,
            updatedAt = prefs.getLong(UPDATED_PREFIX + key, 0L),
        )
    }

    fun cachedLogo(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ): String? = logoInfo(context, stationName, frequency, pi)?.localUri

    suspend fun resolve(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
        ecc: String? = null,
        force: Boolean = false,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(stationName, frequency, pi)
            val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

            prefs.getString(MANUAL_PREFIX + key, null)?.takeIf(String::isNotBlank)?.let {
                return@withContext it
            }

            val cached = prefs.getString(AUTO_PREFIX + key, null)?.takeIf(String::isNotBlank)
            val updatedAt = prefs.getLong(UPDATED_PREFIX + key, 0L)
            val now = System.currentTimeMillis()
            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)
            if (!force && cacheFresh) return@withContext cached

            if (pi <= 0 && !isUsefulStationName(stationName)) return@withContext cached
            val lastFailure = failedAt[key] ?: 0L
            if (!force && now - lastFailure < RETRY_COOLDOWN_MS) return@withContext cached

            if (pi > 0) {
                RadioDnsLogoResolver.resolveFm(appContext, frequency, pi, ecc).forEach { candidate ->
                    cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
                }
            }

            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestMatch(stationName, localStations)
            val fixedLocal = localMatch?.let { station ->
                when {
                    station.manualFavicon && station.favicon.isNotBlank() -> station.favicon
                    else -> RadioStationLogoResolver.resolve(station) ?: station.favicon
                }
            }
            if (!fixedLocal.isNullOrBlank()) {
                val candidate =
                    RadioLogoCandidate(
                        url = fixedLocal,
                        source = RadioLogoSource.STATION_WEBSITE,
                        matchScore = 100,
                        title = localMatch?.name.orEmpty(),
                    )
                cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
            }

            RadioStationLogoSearch.search(stationName, localMatch).getOrDefault(emptyList()).forEach { candidate ->
                cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
            }

            failedAt[key] = now
            Timber.tag(TAG).w(
                "No FM logo resolved station=%s frequency=%.1f PI=%04X ECC=%s; retaining stale=%s",
                stationName,
                frequency,
                pi and 0xffff,
                ecc.orEmpty(),
                cached != null,
            )
            cached
        }

    suspend fun searchCandidates(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
        ecc: String? = null,
    ): List<RadioLogoCandidate> =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestMatch(stationName, localStations)
            buildList {
                if (pi > 0) addAll(RadioDnsLogoResolver.resolveFm(appContext, frequency, pi, ecc))
                localMatch?.let { station ->
                    val fixed =
                        when {
                            station.manualFavicon && station.favicon.isNotBlank() -> station.favicon
                            else -> RadioStationLogoResolver.resolve(station) ?: station.favicon
                        }
                    if (fixed.isNotBlank()) {
                        add(
                            RadioLogoCandidate(
                                url = fixed,
                                source = RadioLogoSource.STATION_WEBSITE,
                                matchScore = 100,
                                title = station.name,
                            ),
                        )
                    }
                }
                addAll(RadioStationLogoSearch.search(stationName, localMatch).getOrDefault(emptyList()))
            }.filter { it.url.startsWith("http://") || it.url.startsWith("https://") }
                .distinctBy { it.url.substringBefore('#') }
                .sortedByDescending { it.ranking }
                .take(36)
        }

    suspend fun setManualLogo(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
        sourceUrl: String,
        sourceLabel: String = "Manuell gewählt",
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(stationName, frequency, pi)
            val stable = RadioStationLogoCache.cache(appContext, "fm_manual_$key", sourceUrl) ?: return@withContext null
            appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString(MANUAL_PREFIX + key, stable)
                .putString(MANUAL_SOURCE_PREFIX + key, sourceLabel)
                .putString(MANUAL_SOURCE_URL_PREFIX + key, sourceUrl)
                .putLong(MANUAL_UPDATED_PREFIX + key, System.currentTimeMillis())
                .apply()
            failedAt.remove(key)
            bumpRevision()
            Timber.tag(TAG).i("FM manual logo stored key=%s source=%s url=%s", key, sourceLabel, sourceUrl)
            stable
        }

    fun clearManualLogo(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ) {
        val key = cacheKey(stationName, frequency, pi)
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .remove(MANUAL_PREFIX + key)
            .remove(MANUAL_SOURCE_PREFIX + key)
            .remove(MANUAL_SOURCE_URL_PREFIX + key)
            .remove(MANUAL_UPDATED_PREFIX + key)
            .apply()
        failedAt.remove(key)
        bumpRevision()
    }

    fun invalidateAuto(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ) {
        val key = cacheKey(stationName, frequency, pi)
        failedAt.remove(key)
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .remove(AUTO_PREFIX + key)
            .remove(SOURCE_PREFIX + key)
            .remove(SOURCE_URL_PREFIX + key)
            .remove(UPDATED_PREFIX + key)
            .apply()
        bumpRevision()
    }

    /** Backwards-compatible alias used by earlier code. */
    fun invalidate(context: Context, stationName: String, frequency: Float, pi: Int = 0) =
        invalidateAuto(context, stationName, frequency, pi)

    private suspend fun cacheAndPersistAutomatic(
        context: Context,
        key: String,
        candidate: RadioLogoCandidate,
    ): String? {
        val stable = RadioStationLogoCache.cache(context, "fm_$key", candidate.url) ?: return null
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(AUTO_PREFIX + key, stable)
            .putString(SOURCE_PREFIX + key, candidate.source.label)
            .putString(SOURCE_URL_PREFIX + key, candidate.url)
            .putLong(UPDATED_PREFIX + key, System.currentTimeMillis())
            .apply()
        failedAt.remove(key)
        bumpRevision()
        Timber.tag(TAG).i(
            "FM logo resolved key=%s source=%s url=%s",
            key,
            candidate.source.label,
            candidate.url,
        )
        return stable
    }

    private fun bumpRevision() = _revisions.update { it + 1L }

    private fun bestMatch(requestedName: String, stations: List<RadioStation>): RadioStation? =
        stations.asSequence()
            .map { station -> station to matchScore(requestedName, station) }
            .filter { (_, score) -> score >= 70 }
            .maxByOrNull { (_, score) -> score }
            ?.first

    private fun matchScore(requestedName: String, station: RadioStation): Int {
        val requested = normalize(requestedName)
        val candidate = normalize(station.name)
        if (requested.isBlank() || candidate.isBlank()) return 0
        var score =
            when {
                requested == candidate -> 100
                candidate.startsWith(requested) || requested.startsWith(candidate) -> 92
                candidate.contains(requested) || requested.contains(candidate) -> 84
                else -> {
                    val left = requested.split(' ').filter { it.length >= 2 }.toSet()
                    val right = candidate.split(' ').filter { it.length >= 2 }.toSet()
                    if (left.isEmpty() || right.isEmpty()) 0 else left.intersect(right).size * 100 / maxOf(left.size, right.size)
                }
            }
        if (station.country.equals("Austria", true) || station.country.equals("Österreich", true)) score += 5
        if (station.manualFavicon) score += 4
        return score
    }

    private fun isUsefulStationName(value: String): Boolean {
        val normalized = normalize(value)
        if (normalized.isBlank() || normalized.matches(Regex("fm \\d{2,3} \\d"))) return false
        return normalized !in setOf("fm", "radio", "antennenempfang", "physischer antennenempfang")
    }

    private fun cacheKey(stationName: String, frequency: Float, pi: Int): String {
        if (pi > 0) return "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}"
        val identity = normalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace("&", " and ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}

@Composable
fun FmStationArtwork(
    stationName: String,
    frequency: Float,
    pi: Int = 0,
    ecc: String? = null,
    size: Dp,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val revision by FmStationLogoResolver.revisions.collectAsState()
    val artworkKey =
        remember(stationName, frequency, pi, ecc, revision) {
            if (pi > 0) {
                "pi-${(pi and 0xffff).toString(16)}-$revision"
            } else {
                "${stationName.trim()}-${(frequency * 100f).roundToInt()}-$revision"
            }
        }
    var artworkUrl by
        remember(artworkKey) {
            mutableStateOf(FmStationLogoResolver.cachedLogo(context, stationName, frequency, pi))
        }
    LaunchedEffect(artworkKey) {
        if (artworkUrl.isNullOrBlank()) {
            artworkUrl = FmStationLogoResolver.resolve(context, stationName, frequency, pi, ecc)
        }
    }
    val shape = RoundedCornerShape((size.value / 7f).dp)
    if (!artworkUrl.isNullOrBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo $stationName",
            contentScale = ContentScale.Fit,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        )
    } else {
        Box(
            contentAlignment = Alignment.Center,
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size((size.value * 0.62f).dp),
            )
        }
    }
}
