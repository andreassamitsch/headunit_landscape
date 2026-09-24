package com.metrolist.music.radio.fyt

import android.content.Context
import kotlin.math.abs
import kotlin.math.floor
import kotlin.math.roundToInt

internal data class FmReceptionPath(
    val favouriteId: String,
    val frequency: Float,
    val regionKey: String,
    val pi: Int,
    val stationId: String,
    val confirmedAt: Long,
    val rssi: Int,
    val coverageStrength: Int,
)

internal data class FmRtrLocalCandidate(
    val frequency: Float,
    val coverageStrength: Int,
    val source: String,
)

internal data class FmLocalAfCandidate(
    val frequency: Float,
    val predictedCoverage: Int,
    val source: String,
    val cachedPath: Boolean,
)

/** Coarse 0.1-degree cells keep reception paths regional without storing the exact route. */
internal object FmReceptionRegion {
    fun key(
        latitude: Double?,
        longitude: Double?,
    ): String? {
        if (latitude == null || longitude == null) return null
        if (!latitude.isFinite() || !longitude.isFinite()) return null
        if (latitude !in -90.0..90.0 || longitude !in -180.0..180.0) return null
        val latCell = floor(latitude * 10.0).toInt()
        val lonCell = floor(longitude * 10.0).toInt()
        return "$latCell:$lonCell"
    }
}

/**
 * Builds a deliberately small AF plan. RTR only proposes frequencies that have positive
 * coverage at the current location; cached paths must have been confirmed in the same region
 * with the same PI and station identity. The tuner still has to confirm the target PI afresh.
 */
internal object FmLocalAfPlanner {
    const val MAX_CANDIDATES = 3

    fun plan(
        favouriteId: String,
        currentFrequency: Float,
        expectedPi: Int,
        stationId: String,
        regionKey: String?,
        history: Collection<FmReceptionPath>,
        rtrCandidates: Collection<FmRtrLocalCandidate>,
    ): List<FmLocalAfCandidate> {
        if (favouriteId.isBlank() || regionKey.isNullOrBlank()) return emptyList()
        if (expectedPi <= 0 || stationId.isBlank()) return emptyList()
        val normalizedPi = expectedPi and 0xffff
        val currentKey = frequencyKey(currentFrequency)

        val cached =
            history
                .asSequence()
                .filter { it.favouriteId == favouriteId }
                .filter { it.regionKey == regionKey }
                .filter { (it.pi and 0xffff) == normalizedPi }
                .filter { it.stationId == stationId }
                .filter { frequencyKey(it.frequency) != currentKey }
                .sortedWith(
                    compareByDescending<FmReceptionPath> { it.confirmedAt }
                        .thenByDescending { it.coverageStrength }
                        .thenByDescending { it.rssi },
                ).map {
                    FmLocalAfCandidate(
                        frequency = normalizeFrequency(it.frequency),
                        predictedCoverage = it.coverageStrength,
                        source = "lokal bestätigter Empfangspfad",
                        cachedPath = true,
                    )
                }

        val rtr =
            rtrCandidates
                .asSequence()
                .filter { it.coverageStrength > 0 }
                .filter { frequencyKey(it.frequency) != currentKey }
                .sortedByDescending(FmRtrLocalCandidate::coverageStrength)
                .map {
                    FmLocalAfCandidate(
                        frequency = normalizeFrequency(it.frequency),
                        predictedCoverage = it.coverageStrength,
                        source = it.source.ifBlank { "RTR lokal" },
                        cachedPath = false,
                    )
                }

        return (cached + rtr)
            .filter { it.frequency in FM_MIN..FM_MAX }
            .distinctBy { frequencyKey(it.frequency) }
            .take(MAX_CANDIDATES)
            .toList()
    }
}

internal object FmReceptionPathCodec {
    fun encode(paths: Collection<FmReceptionPath>): String =
        paths.joinToString("\n") { path ->
            listOf(
                "v1",
                clean(path.favouriteId),
                normalizeFrequency(path.frequency).toString(),
                clean(path.regionKey),
                (path.pi and 0xffff).toString(),
                clean(path.stationId),
                path.confirmedAt.coerceAtLeast(0L).toString(),
                path.rssi.coerceAtLeast(0).toString(),
                path.coverageStrength.coerceAtLeast(0).toString(),
            ).joinToString("\t")
        }

    fun decode(value: String?): List<FmReceptionPath> =
        value.orEmpty()
            .lineSequence()
            .mapNotNull { line ->
                val parts = line.split('\t')
                if (parts.size < 9 || parts[0] != "v1") return@mapNotNull null
                val favouriteId = parts[1].trim()
                val frequency = parts[2].toFloatOrNull()?.let(::normalizeFrequency) ?: return@mapNotNull null
                val regionKey = parts[3].trim()
                val pi = parts[4].toIntOrNull()?.and(0xffff) ?: return@mapNotNull null
                val stationId = parts[5].trim()
                val confirmedAt = parts[6].toLongOrNull() ?: return@mapNotNull null
                val rssi = parts[7].toIntOrNull() ?: 0
                val coverage = parts[8].toIntOrNull() ?: 0
                if (
                    favouriteId.isBlank() || regionKey.isBlank() || stationId.isBlank() ||
                    frequency !in FM_MIN..FM_MAX || pi <= 0
                ) return@mapNotNull null
                FmReceptionPath(
                    favouriteId = favouriteId,
                    frequency = frequency,
                    regionKey = regionKey,
                    pi = pi,
                    stationId = stationId,
                    confirmedAt = confirmedAt.coerceAtLeast(0L),
                    rssi = rssi.coerceAtLeast(0),
                    coverageStrength = coverage.coerceAtLeast(0),
                )
            }.toList()

    private fun clean(value: String): String =
        value.replace('\t', ' ').replace('\n', ' ').replace('\r', ' ').trim()
}

internal class FmReceptionPathStore(context: Context) {
    private val prefs =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    private val lock = Any()

    fun snapshot(): List<FmReceptionPath> =
        synchronized(lock) {
            FmReceptionPathCodec.decode(prefs.getString(KEY_PATHS, null))
        }

    fun candidatesFor(
        favouriteId: String,
        regionKey: String?,
        expectedPi: Int,
        stationId: String,
    ): List<FmReceptionPath> {
        if (regionKey.isNullOrBlank() || expectedPi <= 0 || stationId.isBlank()) return emptyList()
        val pi = expectedPi and 0xffff
        return snapshot()
            .asSequence()
            .filter { it.favouriteId == favouriteId }
            .filter { it.regionKey == regionKey }
            .filter { (it.pi and 0xffff) == pi }
            .filter { it.stationId == stationId }
            .sortedWith(
                compareByDescending<FmReceptionPath> { it.confirmedAt }
                    .thenByDescending { it.coverageStrength }
                    .thenByDescending { it.rssi },
            ).toList()
    }

    fun bestFor(
        favouriteId: String,
        regionKey: String?,
        expectedPi: Int,
        stationId: String,
    ): FmReceptionPath? = candidatesFor(favouriteId, regionKey, expectedPi, stationId).firstOrNull()

    fun rememberConfirmed(
        favouriteId: String,
        frequency: Float,
        regionKey: String?,
        pi: Int,
        stationId: String,
        rssi: Int,
        coverageStrength: Int,
        confirmedAt: Long = System.currentTimeMillis(),
    ): Boolean {
        if (favouriteId.isBlank() || regionKey.isNullOrBlank() || stationId.isBlank() || pi <= 0) return false
        val normalizedFrequency = normalizeFrequency(frequency)
        if (normalizedFrequency !in FM_MIN..FM_MAX) return false
        val normalizedPi = pi and 0xffff

        synchronized(lock) {
            val paths = FmReceptionPathCodec.decode(prefs.getString(KEY_PATHS, null)).toMutableList()
            val index = paths.indexOfFirst {
                it.favouriteId == favouriteId &&
                    it.regionKey == regionKey &&
                    frequencyKey(it.frequency) == frequencyKey(normalizedFrequency)
            }
            val previous = paths.getOrNull(index)
            if (
                previous != null &&
                previous.pi == normalizedPi &&
                previous.stationId == stationId &&
                confirmedAt - previous.confirmedAt < MIN_REWRITE_INTERVAL_MS &&
                previous.rssi >= rssi &&
                previous.coverageStrength >= coverageStrength
            ) return false

            val updated =
                FmReceptionPath(
                    favouriteId = favouriteId,
                    frequency = normalizedFrequency,
                    regionKey = regionKey,
                    pi = normalizedPi,
                    stationId = stationId,
                    confirmedAt = confirmedAt.coerceAtLeast(0L),
                    rssi = rssi.coerceAtLeast(0),
                    coverageStrength = coverageStrength.coerceAtLeast(0),
                )
            if (index >= 0) paths[index] = updated else paths += updated

            val bounded =
                paths
                    .groupBy(FmReceptionPath::favouriteId)
                    .values
                    .flatMap { group -> group.sortedByDescending(FmReceptionPath::confirmedAt).take(MAX_PER_FAVOURITE) }
                    .sortedByDescending(FmReceptionPath::confirmedAt)
                    .take(MAX_TOTAL)
            prefs.edit().putString(KEY_PATHS, FmReceptionPathCodec.encode(bounded)).apply()
            return true
        }
    }

    fun removeFavourite(favouriteId: String) {
        if (favouriteId.isBlank()) return
        synchronized(lock) {
            val retained =
                FmReceptionPathCodec.decode(prefs.getString(KEY_PATHS, null))
                    .filterNot { it.favouriteId == favouriteId }
            prefs.edit().putString(KEY_PATHS, FmReceptionPathCodec.encode(retained)).apply()
        }
    }

    fun clear() {
        synchronized(lock) {
            prefs.edit().remove(KEY_PATHS).apply()
        }
    }

    companion object {
        private const val PREFS = "dudu7_fm_reception_paths"
        private const val KEY_PATHS = "paths_v1"
        private const val MAX_PER_FAVOURITE = 6
        private const val MAX_TOTAL = 60
        private const val MIN_REWRITE_INTERVAL_MS = 5 * 60 * 1000L
    }
}

private const val FM_MIN = 87.5f
private const val FM_MAX = 108.0f

private fun normalizeFrequency(value: Float): Float =
    (value.coerceIn(FM_MIN, FM_MAX) * 10f).roundToInt() / 10f

private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()
