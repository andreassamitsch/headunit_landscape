package com.metrolist.music.radio.fyt

import android.content.Context
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
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Reliable FM artwork resolution inspired by NavRadio+'s station-first approach.
 *
 * Automatic resolution is deliberately conservative:
 * 1. exact RadioDNS bearer matching for the current and every known AF frequency;
 * 2. a curated Austrian PS/frequency identity mapping;
 * 3. an exact, Austria-only match from locally saved WebRadio stations.
 *
 * Broad web/logo searches are only exposed in the manual logo picker. This avoids
 * assigning regional or similarly named stations to short RDS names such as
 * "ANTENNE", "RADIO-ST" or "OE 1".
 */
object ReliableFmStationLogoResolver {
    private const val TAG = "ReliableFmLogo"
    private const val PREFS = "dudu7_fm_station_logos_v3"
    private const val LEGACY_PREFS = "dudu7_fm_station_logos_v2"
    private const val AUTO_PREFIX = "logo_"
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
        ecc: String? = null,
        allFrequencies: List<Float> = emptyList(),
    ): LogoInfo? {
        val appContext = context.applicationContext
        val frequencies = orderedFrequencies(frequency, allFrequencies)
        val key = cacheKey(appContext, stationName, frequency, pi, ecc)
        migrateLegacyManual(appContext, key, legacyCacheKey(stationName, frequency, pi))
        val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
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
        ).also {
            @Suppress("UNUSED_VARIABLE")
            val keepFrequencyIdentity = frequencies
        }
    }

    fun cachedLogo(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
        ecc: String? = null,
        allFrequencies: List<Float> = emptyList(),
    ): String? = logoInfo(context, stationName, frequency, pi, ecc, allFrequencies)?.localUri

    suspend fun resolve(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
        ecc: String? = null,
        force: Boolean = false,
        allFrequencies: List<Float> = emptyList(),
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val frequencies = orderedFrequencies(frequency, allFrequencies)
            val key = cacheKey(appContext, stationName, frequency, pi, ecc)
            migrateLegacyManual(appContext, key, legacyCacheKey(stationName, frequency, pi))
            val prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

            prefs.getString(MANUAL_PREFIX + key, null)?.takeIf(String::isNotBlank)?.let {
                return@withContext it
            }

            val cached = prefs.getString(AUTO_PREFIX + key, null)?.takeIf(String::isNotBlank)
            val updatedAt = prefs.getLong(UPDATED_PREFIX + key, 0L)
            val now = System.currentTimeMillis()
            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)
            val cachedSource = prefs.getString(SOURCE_PREFIX + key, "").orEmpty()
            val cachedIsRadioDns = cachedSource == RadioLogoSource.RADIO_DNS.label
            if (!force && cacheFresh && (pi <= 0 || cachedIsRadioDns)) return@withContext cached

            val resolvedStation = FmStationIdentity.resolve(stationName, null, frequencies, pi, ecc)
            val identity = AustrianFmStationCatalog.identify(resolvedStation.canonicalName, frequencies)
            if (pi <= 0 && identity == null && !isSafeAutomaticName(resolvedStation.canonicalName)) return@withContext cached
            val lastFailure = failedAt[key] ?: 0L
            if (!force && now - lastFailure < RETRY_COOLDOWN_MS) return@withContext cached

            if (pi > 0) {
                for (candidateFrequency in frequencies) {
                    val candidates = RadioDnsLogoResolver.resolveFm(appContext, candidateFrequency, pi, ecc)
                    for (candidate in candidates) {
                        cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
                    }
                }
            }

            identity?.candidate()?.let { candidate ->
                cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
            }

            val exactLocal = exactLocalMatch(identity?.canonicalName ?: resolvedStation.canonicalName, RadioStationStore.get(appContext).stations.value)
            val fixedLocal = exactLocal?.let { station ->
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
                        title = exactLocal?.name.orEmpty(),
                    )
                cacheAndPersistAutomatic(appContext, key, candidate)?.let { return@withContext it }
            }

            failedAt[key] = now
            Timber.tag(TAG).w(
                "No reliable automatic FM logo station=%s frequencies=%s PI=%04X ECC=%s; stale=%s",
                stationName,
                frequencies.joinToString(),
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
        allFrequencies: List<Float> = emptyList(),
    ): List<RadioLogoCandidate> =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val frequencies = orderedFrequencies(frequency, allFrequencies)
            val resolvedStation = FmStationIdentity.resolve(stationName, null, frequencies, pi, ecc)
            val identity = AustrianFmStationCatalog.identify(resolvedStation.canonicalName, frequencies)
            val query = identity?.canonicalName ?: resolvedStation.canonicalName
            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestManualMatch(query, localStations)

            buildList {
                if (pi > 0) {
                    frequencies.forEach { candidateFrequency ->
                        addAll(RadioDnsLogoResolver.resolveFm(appContext, candidateFrequency, pi, ecc))
                    }
                }
                identity?.candidate()?.let(::add)
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
                addAll(RadioStationLogoSearch.search(query, localMatch).getOrDefault(emptyList()))
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
        ecc: String? = null,
        sourceUrl: String,
        sourceLabel: String = "Manuell gewählt",
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(appContext, stationName, frequency, pi, ecc)
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
        ecc: String? = null,
    ) {
        val appContext = context.applicationContext
        val key = cacheKey(appContext, stationName, frequency, pi, ecc)
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
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
        ecc: String? = null,
    ) {
        val appContext = context.applicationContext
        val key = cacheKey(appContext, stationName, frequency, pi, ecc)
        failedAt.remove(key)
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .remove(AUTO_PREFIX + key)
            .remove(SOURCE_PREFIX + key)
            .remove(SOURCE_URL_PREFIX + key)
            .remove(UPDATED_PREFIX + key)
            .apply()
        bumpRevision()
    }

    private suspend fun cacheAndPersistAutomatic(
        context: Context,
        key: String,
        candidate: RadioLogoCandidate,
    ): String? {
        val stable = RadioStationLogoCache.cache(context, "fm_v3_$key", candidate.url) ?: return null
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(AUTO_PREFIX + key, stable)
            .putString(SOURCE_PREFIX + key, candidate.source.label)
            .putString(SOURCE_URL_PREFIX + key, candidate.url)
            .putLong(UPDATED_PREFIX + key, System.currentTimeMillis())
            .apply()
        failedAt.remove(key)
        bumpRevision()
        Timber.tag(TAG).i("Reliable FM logo key=%s source=%s title=%s url=%s", key, candidate.source.label, candidate.title, candidate.url)
        return stable
    }

    private fun migrateLegacyManual(context: Context, newKey: String, legacyKey: String) {
        val target = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!target.getString(MANUAL_PREFIX + newKey, null).isNullOrBlank()) return
        val legacy = context.getSharedPreferences(LEGACY_PREFS, Context.MODE_PRIVATE)
        val localUri = legacy.getString(MANUAL_PREFIX + legacyKey, null)?.takeIf(String::isNotBlank) ?: return
        target.edit()
            .putString(MANUAL_PREFIX + newKey, localUri)
            .putString(MANUAL_SOURCE_PREFIX + newKey, legacy.getString(MANUAL_SOURCE_PREFIX + legacyKey, "Manuell gewählt"))
            .putString(MANUAL_SOURCE_URL_PREFIX + newKey, legacy.getString(MANUAL_SOURCE_URL_PREFIX + legacyKey, ""))
            .putLong(MANUAL_UPDATED_PREFIX + newKey, legacy.getLong(MANUAL_UPDATED_PREFIX + legacyKey, 0L))
            .apply()
        Timber.tag(TAG).i("Migrated legacy manual FM logo %s -> %s", legacyKey, newKey)
    }

    private fun exactLocalMatch(requestedName: String, stations: List<RadioStation>): RadioStation? {
        val requested = normalizeAlias(requestedName)
        if (requested.isBlank()) return null
        return stations.firstOrNull { station ->
            normalizeAlias(station.name) == requested &&
                (station.country.equals("Austria", true) || station.country.equals("Österreich", true))
        }
    }

    private fun bestManualMatch(requestedName: String, stations: List<RadioStation>): RadioStation? =
        stations.asSequence()
            .map { station -> station to manualMatchScore(requestedName, station.name) }
            .filter { (station, score) ->
                score >= 72 &&
                    (station.country.equals("Austria", true) || station.country.equals("Österreich", true))
            }.maxByOrNull { (_, score) -> score }
            ?.first

    private fun manualMatchScore(requestedName: String, candidateName: String): Int {
        val left = normalizeAlias(requestedName)
        val right = normalizeAlias(candidateName)
        if (left.isBlank() || right.isBlank()) return 0
        if (left == right) return 100
        val compactLeft = left.replace(" ", "")
        val compactRight = right.replace(" ", "")
        if (compactLeft == compactRight) return 100
        if (right.contains(left) || left.contains(right)) return 86
        val leftTokens = left.split(' ').filter { it.length >= 2 }.toSet()
        val rightTokens = right.split(' ').filter { it.length >= 2 }.toSet()
        if (leftTokens.isEmpty() || rightTokens.isEmpty()) return 0
        return leftTokens.intersect(rightTokens).size * 100 / maxOf(leftTokens.size, rightTokens.size)
    }

    private fun cacheKey(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int,
        ecc: String?,
    ): String {
        val resolved = FmStationIdentity.resolve(stationName, null, listOf(frequency), pi, ecc)
        if (resolved.recognized) return "station_${resolved.stableId.replace(':', '_')}"
        if (pi > 0) {
            val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
            val resolvedEcc = normaliseEcc(ecc) ?: RadioDnsLogoResolver.defaultEcc(context)
            val gcc = resolvedEcc?.let { "${piHex.first()}$it" } ?: "unknown"
            return "gcc_${gcc}_pi_$piHex"
        }
        val identity = normalizeAlias(resolved.canonicalName).ifBlank { "unknown" }.replace(' ', '_')
        return "name_${identity}_${(frequency * 100f).roundToInt()}"
    }

    private fun legacyCacheKey(stationName: String, frequency: Float, pi: Int): String {
        if (pi > 0) return "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}"
        val identity = legacyNormalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }

    private fun orderedFrequencies(primary: Float, others: List<Float>): List<Float> =
        (listOf(primary) + others)
            .filter { it in 65f..110f }
            .distinctBy { (it * 100f).roundToInt() }

    private fun isSafeAutomaticName(value: String): Boolean {
        val compact = normalizeAlias(value).replace(" ", "")
        if (compact.isBlank()) return false
        if (compact in setOf("fm", "radio", "antenne", "antennenempfang", "physischerantennenempfang")) return false
        return compact.length >= 4
    }

    private fun normaliseEcc(value: String?): String? =
        value?.trim()?.lowercase(Locale.ROOT)?.takeIf { it.matches(Regex("[0-9a-f]{2}")) }

    private fun bumpRevision() = _revisions.update { it + 1L }

    private fun legacyNormalize(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace("&", " and ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}

internal data class AustrianFmIdentity(
    val canonicalName: String,
    val radioAtSlug: String,
) {
    fun candidate(): RadioLogoCandidate =
        RadioLogoCandidate(
            url = "https://www.radio.at/300/$radioAtSlug.png?version=",
            source = RadioLogoSource.RADIO_AT,
            matchScore = 100,
            width = 300,
            height = 300,
            title = canonicalName,
        )
}

/** Curated, deterministic identities for common Austrian FM RDS names. */
internal object AustrianFmStationCatalog {
    private val antennaSteiermarkFrequencies =
        setOf(106.8f, 90.6f, 95.5f, 105.7f, 99.7f, 105.0f, 101.2f, 99.1f, 97.4f, 100.1f, 103.4f, 104.2f, 88.9f, 96.8f, 106.5f, 106.1f, 104.4f, 92.0f, 100.7f, 97.0f)
    private val antennaKaerntenFrequencies =
        setOf(96.1f, 101.1f, 95.7f, 104.9f, 107.4f, 102.1f, 104.3f)

    private val oe1 = AustrianFmIdentity("Ö1", "oe1")
    private val oe3 = AustrianFmIdentity("Hitradio Ö3", "oe3")
    private val fm4 = AustrianFmIdentity("FM4", "fm4")
    private val radioSteiermark = AustrianFmIdentity("ORF Radio Steiermark", "steiermark")
    private val oe24 = AustrianFmIdentity("oe24 RADIO", "oe24")
    private val njoy = AustrianFmIdentity("NJOY Radio | 88.2 fm Steiermark", "njoyaustria")
    private val antennaSteiermark = AustrianFmIdentity("Antenne Steiermark", "antennesteiermark")
    private val antennaKaernten = AustrianFmIdentity("Antenne Kärnten", "antennekaernten")

    fun identify(stationName: String, frequencies: List<Float>): AustrianFmIdentity? {
        val compact = normalizeAlias(stationName).replace(" ", "")
        return when {
            compact in setOf("oe1", "orfoe1", "orfradiooe1") -> oe1
            compact in setOf("oe3", "orfoe3", "orfradiooe3", "hitradiooe3") -> oe3
            compact in setOf("fm4", "orffm4", "orfradiofm4") -> fm4
            compact in setOf("oe24", "oe24radio", "radiooe24") -> oe24
            compact in setOf("radiosteiermark", "orfradiosteiermark", "orfsteiermark", "radiostmk") -> radioSteiermark
            compact == "radiost" && hasFrequency(frequencies, 98.7f) -> radioSteiermark
            compact in setOf("njoy", "njoyradio", "njoy882", "njoyradio882fmsteiermark") && hasFrequency(frequencies, 88.2f) -> njoy
            compact.contains("antennesteiermark") || compact in setOf("antennestmk", "antstmk") -> antennaSteiermark
            compact.contains("antennekaernten") || compact in setOf("antennektn", "antktn") -> antennaKaernten
            compact == "antenne" -> identifyAntenneByFrequency(frequencies)
            else -> null
        }
    }

    private fun identifyAntenneByFrequency(frequencies: List<Float>): AustrianFmIdentity? {
        val steiermark = antennaSteiermarkFrequencies.any { known -> hasFrequency(frequencies, known) }
        val kaernten = antennaKaerntenFrequencies.any { known -> hasFrequency(frequencies, known) }
        return when {
            steiermark && !kaernten -> antennaSteiermark
            kaernten && !steiermark -> antennaKaernten
            else -> null
        }
    }

    private fun hasFrequency(values: List<Float>, expected: Float): Boolean =
        values.any { abs(it - expected) < 0.06f }
}

internal fun normalizeAlias(value: String): String {
    val transliterated =
        value.lowercase(Locale.GERMAN)
            .replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
    return Normalizer.normalize(transliterated, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "")
        .replace("&", " und ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()
}
