#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {count}: {old[:120]!r}")
    write(path, content.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, flags: int = 0) -> None:
    content = read(path)
    updated, count = re.subn(pattern, replacement, content, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{path}: regex expected one occurrence, found {count}: {pattern[:120]!r}")
    write(path, updated)


# Version and app identity.
replace_once("app/build.gradle.kts", "versionCode = 1370035", "versionCode = 1370036")
replace_once("app/build.gradle.kts", 'versionName = "13.7.26"', 'versionName = "13.7.27"')


# Persist the last main player tab across real process restarts.
write(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLastTabStore.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.variant

        import android.content.Context

        /** Persists only stable top-level right-pane routes, never detail routes. */
        internal object VehicleLastTabStore {
            private const val PREFS = "dudu7_vehicle_layout"
            private const val KEY_LAST_ROUTE = "last_right_pane_route"

            internal fun normalize(savedRoute: String?, allowedRoutes: Set<String>, fallback: String): String =
                savedRoute?.takeIf { it in allowedRoutes } ?: fallback

            fun read(context: Context, allowedRoutes: Set<String>, fallback: String): String =
                normalize(
                    context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                        .getString(KEY_LAST_ROUTE, null),
                    allowedRoutes,
                    fallback,
                )

            fun persist(context: Context, route: String, allowedRoutes: Set<String>) {
                if (route !in allowedRoutes) return
                context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    .edit()
                    .putString(KEY_LAST_ROUTE, route)
                    .apply()
            }
        }
        '''
    ),
)

layout = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(
    layout,
    '''    val paneNavController = rememberNavController()
    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()
    val currentPaneRoute = paneBackStackEntry?.destination?.route
    var selectedTab by rememberSaveable { mutableStateOf(VehicleRightPaneTab.QUEUE) }
    val context = LocalContext.current
''',
    '''    val context = LocalContext.current
    val mainTabRoutes = remember { VehicleRightPaneTab.entries.map { it.route }.toSet() }
    val initialPaneRoute =
        remember(context, mainTabRoutes) {
            VehicleLastTabStore.read(context, mainTabRoutes, VEHICLE_QUEUE_ROUTE)
        }
    val initialTab =
        remember(initialPaneRoute) {
            VehicleRightPaneTab.entries.firstOrNull { it.route == initialPaneRoute }
                ?: VehicleRightPaneTab.QUEUE
        }
    val paneNavController = rememberNavController()
    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()
    val currentPaneRoute = paneBackStackEntry?.destination?.route
    var selectedTab by rememberSaveable { mutableStateOf(initialTab) }
''',
)
replace_once(
    layout,
    '''    LaunchedEffect(selectedTab, orderedTabs.toList()) {
''',
    '''    LaunchedEffect(selectedTab) {
        VehicleLastTabStore.persist(context, selectedTab.route, mainTabRoutes)
    }

    LaunchedEffect(selectedTab, orderedTabs.toList()) {
''',
)
replace_once(layout, "startDestination = VEHICLE_QUEUE_ROUTE", "startDestination = initialPaneRoute")


# Robust RadioDNS implementation with transparent stage diagnostics.
write(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.radio

        import android.content.Context
        import android.util.Xml
        import kotlinx.coroutines.Dispatchers
        import kotlinx.coroutines.flow.MutableStateFlow
        import kotlinx.coroutines.flow.StateFlow
        import kotlinx.coroutines.flow.asStateFlow
        import kotlinx.coroutines.withContext
        import org.json.JSONObject
        import org.xmlpull.v1.XmlPullParser
        import timber.log.Timber
        import java.io.ByteArrayInputStream
        import java.net.HttpURLConnection
        import java.net.URI
        import java.net.URL
        import java.net.URLEncoder
        import java.nio.charset.StandardCharsets
        import java.util.Locale
        import java.util.TimeZone
        import kotlin.math.abs
        import kotlin.math.roundToInt

        /** RadioDNS Project Logo lookup for an FM bearer using RDS PI, frequency and GCC. */
        object RadioDnsLogoResolver {
            private const val TAG = "RadioDNS"
            private const val USER_AGENT = "Metrolist-dudu7/13.7.27 RadioDNS receiver"
            private const val MAX_SI_BYTES = 3_000_000
            private const val MAX_CNAME_DEPTH = 6
            private val DNS_ENDPOINTS = listOf(
                "https://dns.google/resolve",
                "https://cloudflare-dns.com/dns-query",
            )

            data class LookupTrace(
                val stage: String = "Noch nicht geprüft",
                val detail: String = "",
                val frequency: Float = 0f,
                val piHex: String = "",
                val ecc: String = "",
                val eccSource: String = "",
                val gcc: String = "",
                val lookup: String = "",
                val bearer: String = "",
                val cnameChain: List<String> = emptyList(),
                val srvTargets: List<String> = emptyList(),
                val siUrl: String = "",
                val contentType: String = "",
                val candidates: Int = 0,
                val updatedAt: Long = 0L,
            ) {
                val summary: String
                    get() = buildString {
                        append(stage)
                        if (detail.isNotBlank()) append(": ").append(detail)
                    }
            }

            internal data class FmIdentity(
                val frequencyCode: String,
                val piHex: String,
                val ecc: String,
                val gcc: String,
                val lookup: String,
                val bearer: String,
            )

            private data class EccResult(val value: String, val source: String)
            private data class SrvRecord(val priority: Int, val weight: Int, val port: Int, val target: String)
            private data class DnsResult(val answers: List<String>, val detail: String)
            private data class HttpPayload(
                val bytes: ByteArray?,
                val finalUrl: String,
                val contentType: String,
                val status: Int,
                val detail: String,
            )

            private val _lastTrace = MutableStateFlow(LookupTrace())
            val lastTrace: StateFlow<LookupTrace> = _lastTrace.asStateFlow()

            suspend fun resolveFm(
                context: Context,
                frequency: Float,
                pi: Int,
                ecc: String? = null,
            ): List<RadioLogoCandidate> =
                withContext(Dispatchers.IO) {
                    val eccResult = resolveEcc(context, ecc)
                    if (pi <= 0) {
                        publish(LookupTrace(stage = "Abbruch PI", detail = "Keine bestätigte RDS-PI", frequency = frequency))
                        return@withContext emptyList()
                    }
                    if (eccResult == null) {
                        publish(
                            LookupTrace(
                                stage = "Abbruch ECC",
                                detail = "Keine RDS-ECC und keine sichere Geräte-/Regionszuordnung",
                                frequency = frequency,
                                piHex = (pi and 0xffff).toString(16).padStart(4, '0'),
                            ),
                        )
                        return@withContext emptyList()
                    }
                    val identity = buildFmIdentity(frequency, pi, eccResult.value)
                    if (identity == null) {
                        publish(
                            LookupTrace(
                                stage = "Abbruch Bearer",
                                detail = "Ungültige Frequenz, PI oder ECC",
                                frequency = frequency,
                            ),
                        )
                        return@withContext emptyList()
                    }
                    var trace =
                        LookupTrace(
                            stage = "DNS CNAME",
                            detail = "RadioDNS-Adresse wird aufgelöst",
                            frequency = frequency,
                            piHex = identity.piHex,
                            ecc = identity.ecc,
                            eccSource = eccResult.source,
                            gcc = identity.gcc,
                            lookup = identity.lookup,
                            bearer = identity.bearer,
                        )
                    publish(trace)

                    val cnameChain = resolveCnameChain(identity.lookup)
                    if (cnameChain == null || cnameChain.size < 2) {
                        publish(trace.copy(stage = "Kein CNAME", detail = "Für den FM-Bearer ist kein RadioDNS-CNAME registriert"))
                        return@withContext emptyList()
                    }
                    val authoritative = cnameChain.last()
                    trace = trace.copy(stage = "DNS SRV", detail = authoritative, cnameChain = cnameChain)
                    publish(trace)

                    val srvResult = dnsAnswers("_radioepg._tcp.$authoritative", 33)
                    val srvRecords =
                        srvResult.answers.mapNotNull(::parseSrv)
                            .sortedWith(compareBy<SrvRecord> { it.priority }.thenByDescending { it.weight })
                    if (srvRecords.isEmpty()) {
                        publish(trace.copy(stage = "Kein RadioEPG-SRV", detail = srvResult.detail))
                        return@withContext emptyList()
                    }
                    trace = trace.copy(
                        stage = "SPI abrufen",
                        detail = "${srvRecords.size} Server gefunden",
                        srvTargets = srvRecords.map { "${it.target}:${it.port}" },
                    )
                    publish(trace)

                    for (srv in srvRecords) {
                        for (siUrl in serviceInformationUrls(srv)) {
                            val payload = download(siUrl, "application/xml,text/xml,application/radiodns+xml,*/*;q=0.5")
                            trace = trace.copy(
                                stage = "SPI prüfen",
                                detail = "HTTP ${payload.status}: ${payload.detail}",
                                siUrl = payload.finalUrl.ifBlank { siUrl },
                                contentType = payload.contentType,
                            )
                            publish(trace)
                            val xml = payload.bytes ?: continue
                            val logos =
                                runCatching { parseServiceInformation(xml, payload.finalUrl.ifBlank { siUrl }, identity.bearer) }
                                    .onFailure { Timber.tag(TAG).w(it, "Could not parse SPI %s", siUrl) }
                                    .getOrDefault(emptyList())
                            if (logos.isNotEmpty()) {
                                val sorted = logos.distinctBy { it.url }.sortedByDescending { it.ranking }
                                publish(
                                    trace.copy(
                                        stage = "Erfolgreich",
                                        detail = "${sorted.size} RadioDNS-Logo(s) gefunden",
                                        candidates = sorted.size,
                                    ),
                                )
                                Timber.tag(TAG).i(
                                    "Resolved %d RadioDNS logo(s) lookup=%s bearer=%s via=%s",
                                    sorted.size,
                                    identity.lookup,
                                    identity.bearer,
                                    siUrl,
                                )
                                return@withContext sorted
                            }
                        }
                    }
                    publish(trace.copy(stage = "Kein Logo", detail = "SPI erreichbar, aber kein passender Bearer/Multimedia-Eintrag"))
                    emptyList()
                }

            internal fun buildFmIdentity(frequency: Float, pi: Int, ecc: String): FmIdentity? {
                val normalizedEcc = normaliseEcc(ecc) ?: return null
                if (pi <= 0 || frequency !in 65f..110f) return null
                val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
                val gcc = "${piHex.first()}$normalizedEcc"
                val frequencyCode = (frequency * 100f).roundToInt().toString().padStart(5, '0')
                return FmIdentity(
                    frequencyCode = frequencyCode,
                    piHex = piHex,
                    ecc = normalizedEcc,
                    gcc = gcc,
                    lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org",
                    bearer = "fm:$gcc.$piHex.$frequencyCode",
                )
            }

            fun defaultEcc(context: Context): String? = resolveEcc(context, null)?.value

            private fun resolveEcc(context: Context, supplied: String?): EccResult? {
                normaliseEcc(supplied)?.let { return EccResult(it, "RDS") }
                val countries = buildList {
                    val locales = context.resources.configuration.locales
                    for (index in 0 until locales.size()) add(locales[index].country)
                    add(Locale.getDefault().country)
                    add(System.getProperty("user.country").orEmpty())
                }
                countries.map(String::uppercase).firstNotNullOfOrNull { country ->
                    when (country) {
                        "AT", "DE" -> EccResult("e0", "Geräteregion $country")
                        "CH" -> EccResult("e1", "Geräteregion CH")
                        "LI" -> EccResult("e2", "Geräteregion LI")
                        else -> null
                    }
                }?.let { return it }
                return when (TimeZone.getDefault().id.lowercase(Locale.ROOT)) {
                    "europe/vienna", "europe/berlin" -> EccResult("e0", "Zeitzone")
                    "europe/zurich" -> EccResult("e1", "Zeitzone")
                    else -> null
                }
            }

            private fun resolveCnameChain(start: String): List<String>? {
                val chain = mutableListOf(start.trimEnd('.'))
                var current = chain.last()
                repeat(MAX_CNAME_DEPTH) {
                    val result = dnsAnswers(current, 5)
                    val next = result.answers.firstOrNull()?.trim()?.trim('"')?.trimEnd('.')
                    if (next.isNullOrBlank()) return chain.takeIf { it.size > 1 }
                    if (chain.any { it.equals(next, ignoreCase = true) }) return null
                    chain += next
                    current = next
                }
                return chain.takeIf { it.size > 1 }
            }

            private fun parseSrv(value: String): SrvRecord? {
                val parts = value.trim().trim('"').split(Regex("\\s+"))
                if (parts.size < 4) return null
                return SrvRecord(
                    priority = parts[0].toIntOrNull() ?: return null,
                    weight = parts[1].toIntOrNull() ?: 0,
                    port = parts[2].toIntOrNull() ?: return null,
                    target = parts[3].trimEnd('.'),
                )
            }

            private fun serviceInformationUrls(srv: SrvRecord): List<String> {
                fun authority(scheme: String): String {
                    val standard = (scheme == "https" && srv.port == 443) || (scheme == "http" && srv.port == 80)
                    return if (standard) srv.target else "${srv.target}:${srv.port}"
                }
                val preferred = if (srv.port == 443) "https" else "http"
                val alternate = if (preferred == "https") "http" else "https"
                return buildList {
                    for (scheme in listOf(preferred, alternate)) {
                        val root = "$scheme://${authority(scheme)}"
                        add("$root/radiodns/spi/3.1/SI.xml")
                        add("$root/radiodns/spi/3.2/SI.xml")
                        add("$root/radiodns/spi/3.1/si.xml")
                    }
                }.distinct()
            }

            private fun dnsAnswers(name: String, type: Int): DnsResult {
                var lastDetail = "Keine DNS-Antwort"
                for (base in DNS_ENDPOINTS) {
                    val endpoint = "$base?name=${encode(name)}&type=$type"
                    val connection = open(endpoint, "application/dns-json,application/json") ?: continue
                    try {
                        val code = connection.responseCode
                        if (code !in 200..299) {
                            lastDetail = "${URL(base).host}: HTTP $code"
                            continue
                        }
                        val root = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                        val status = root.optInt("Status", -1)
                        if (status != 0) {
                            lastDetail = "${URL(base).host}: DNS-Status $status"
                            continue
                        }
                        val answers = root.optJSONArray("Answer")
                        val values = buildList {
                            if (answers != null) {
                                for (index in 0 until answers.length()) {
                                    val answer = answers.optJSONObject(index) ?: continue
                                    if (answer.optInt("type") == type) {
                                        answer.optString("data").takeIf(String::isNotBlank)?.let(::add)
                                    }
                                }
                            }
                        }
                        return DnsResult(values, "${URL(base).host}: ${values.size} Antwort(en)")
                    } catch (error: Exception) {
                        lastDetail = "${URL(base).host}: ${error.javaClass.simpleName}: ${error.message.orEmpty()}"
                    } finally {
                        connection.disconnect()
                    }
                }
                return DnsResult(emptyList(), lastDetail)
            }

            private fun download(url: String, accept: String): HttpPayload {
                val connection = open(url, accept)
                    ?: return HttpPayload(null, url, "", -1, "Verbindung konnte nicht geöffnet werden")
                return try {
                    val code = connection.responseCode
                    val finalUrl = connection.url.toString()
                    val contentType = connection.contentType.orEmpty()
                    if (code !in 200..299) {
                        HttpPayload(null, finalUrl, contentType, code, "HTTP-Fehler")
                    } else {
                        val output = java.io.ByteArrayOutputStream()
                        connection.inputStream.use { input ->
                            val buffer = ByteArray(8192)
                            var total = 0
                            while (true) {
                                val count = input.read(buffer)
                                if (count <= 0) break
                                total += count
                                if (total > MAX_SI_BYTES) {
                                    return HttpPayload(null, finalUrl, contentType, code, "SI-Datei größer als $MAX_SI_BYTES Bytes")
                                }
                                output.write(buffer, 0, count)
                            }
                        }
                        val bytes = output.toByteArray().takeIf { it.isNotEmpty() }
                        HttpPayload(bytes, finalUrl, contentType, code, if (bytes == null) "Leere Antwort" else "${bytes.size} Bytes")
                    }
                } catch (error: Exception) {
                    HttpPayload(null, connection.url.toString(), connection.contentType.orEmpty(), -1, "${error.javaClass.simpleName}: ${error.message.orEmpty()}")
                } finally {
                    connection.disconnect()
                }
            }

            private fun parseServiceInformation(
                xml: ByteArray,
                baseUrl: String,
                expectedBearer: String,
            ): List<RadioLogoCandidate> {
                val parser = Xml.newPullParser()
                parser.setInput(ByteArrayInputStream(xml), StandardCharsets.UTF_8.name())
                var inService = false
                var serviceMatches = false
                var serviceName = ""
                var logos = mutableListOf<RadioLogoCandidate>()
                while (parser.eventType != XmlPullParser.END_DOCUMENT) {
                    when (parser.eventType) {
                        XmlPullParser.START_TAG -> when (parser.name.substringAfter(':')) {
                            "service" -> {
                                inService = true
                                serviceMatches = false
                                serviceName = ""
                                logos = mutableListOf()
                            }
                            "shortName", "mediumName", "longName" -> if (inService && serviceName.isBlank()) {
                                serviceName = runCatching { parser.nextText().trim() }.getOrDefault("")
                            }
                            "bearer" -> if (inService) {
                                val id = parser.getAttributeValue(null, "id").orEmpty()
                                if (bearerMatches(id, expectedBearer)) serviceMatches = true
                            }
                            "multimedia" -> if (inService) {
                                val rawUrl = parser.getAttributeValue(null, "url").orEmpty()
                                val resolvedUrl = runCatching { URI(baseUrl).resolve(rawUrl).toString() }.getOrNull().orEmpty()
                                if (resolvedUrl.startsWith("http://") || resolvedUrl.startsWith("https://")) {
                                    logos += RadioLogoCandidate(
                                        url = resolvedUrl,
                                        source = RadioLogoSource.RADIO_DNS,
                                        matchScore = 100,
                                        width = parser.getAttributeValue(null, "width")?.toIntOrNull() ?: 0,
                                        height = parser.getAttributeValue(null, "height")?.toIntOrNull() ?: 0,
                                        title = serviceName,
                                    )
                                }
                            }
                        }
                        XmlPullParser.END_TAG -> if (parser.name.substringAfter(':') == "service" && inService) {
                            if (serviceMatches) return logos.distinctBy { it.url }
                            inService = false
                        }
                    }
                    parser.next()
                }
                return emptyList()
            }

            internal fun bearerMatches(actual: String, expected: String): Boolean {
                if (actual.equals(expected, ignoreCase = true)) return true
                val left = actual.lowercase(Locale.ROOT).split('.')
                val right = expected.lowercase(Locale.ROOT).split('.')
                if (left.size != 3 || right.size != 3) return false
                return left[0] == right[0] && left[1] == right[1] &&
                    abs((left[2].toIntOrNull() ?: -100) - (right[2].toIntOrNull() ?: 100)) <= 1
            }

            private fun normaliseEcc(value: String?): String? =
                value?.trim()?.lowercase(Locale.ROOT)?.removePrefix("0x")
                    ?.takeIf { it.matches(Regex("[0-9a-f]{2}")) }

            private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

            private fun open(url: String, accept: String): HttpURLConnection? =
                runCatching {
                    (URL(url).openConnection() as HttpURLConnection).apply {
                        connectTimeout = 7_000
                        readTimeout = 11_000
                        instanceFollowRedirects = true
                        setRequestProperty("User-Agent", USER_AGENT)
                        setRequestProperty("Accept", accept)
                        setRequestProperty("Accept-Language", "de-AT,de;q=0.9,en;q=0.6")
                        setRequestProperty("Connection", "close")
                    }
                }.getOrNull()

            private fun publish(trace: LookupTrace) {
                val value = trace.copy(updatedAt = System.currentTimeMillis())
                _lastTrace.value = value
                Timber.tag(TAG).d(
                    "stage=%s detail=%s lookup=%s bearer=%s cname=%s srv=%s si=%s candidates=%d",
                    value.stage,
                    value.detail,
                    value.lookup,
                    value.bearer,
                    value.cnameChain.joinToString(" -> "),
                    value.srvTargets.joinToString(),
                    value.siUrl,
                    value.candidates,
                )
            }
        }
        '''
    ),
)


# Let a fresh RadioDNS result upgrade a cached fallback logo instead of being blocked for 30 days.
resolver = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/ReliableFmStationLogoResolver.kt"
replace_once(
    resolver,
    '''    private const val AUTO_REFRESH_MS = 30L * 24L * 60L * 60L * 1000L
''',
    '''    private const val AUTO_REFRESH_MS = 30L * 24L * 60L * 60L * 1000L
    private const val RADIODNS_RETRY_MS = 6L * 60L * 60L * 1000L
    private const val RADIODNS_CHECKED_PREFIX = "radiodns_checked_"
    private const val RADIODNS_RESULT_PREFIX = "radiodns_result_"
''',
)
replace_once(
    resolver,
    '''            val cached = prefs.getString(AUTO_PREFIX + key, null)?.takeIf(String::isNotBlank)
            val updatedAt = prefs.getLong(UPDATED_PREFIX + key, 0L)
            val now = System.currentTimeMillis()
            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)
            if (!force && cacheFresh) return@withContext cached

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
''',
    '''            val cached = prefs.getString(AUTO_PREFIX + key, null)?.takeIf(String::isNotBlank)
            val cachedSource = prefs.getString(SOURCE_PREFIX + key, "").orEmpty()
            val updatedAt = prefs.getLong(UPDATED_PREFIX + key, 0L)
            val now = System.currentTimeMillis()
            val cacheFresh = cached != null && (updatedAt <= 0L || now - updatedAt < AUTO_REFRESH_MS)
            val radioDnsDue = force || now - prefs.getLong(RADIODNS_CHECKED_PREFIX + key, 0L) >= RADIODNS_RETRY_MS
            if (!force && cacheFresh && (pi <= 0 || cachedSource == RadioLogoSource.RADIO_DNS.label || !radioDnsDue)) {
                return@withContext cached
            }

            if (pi > 0 && radioDnsDue) {
                for (candidateFrequency in frequencies) {
                    val candidates = RadioDnsLogoResolver.resolveFm(appContext, candidateFrequency, pi, ecc)
                    for (candidate in candidates) {
                        val stored = cacheAndPersistAutomatic(appContext, key, candidate)
                        if (stored != null) {
                            prefs.edit()
                                .putLong(RADIODNS_CHECKED_PREFIX + key, now)
                                .putString(RADIODNS_RESULT_PREFIX + key, RadioDnsLogoResolver.lastTrace.value.summary)
                                .apply()
                            return@withContext stored
                        }
                    }
                }
                prefs.edit()
                    .putLong(RADIODNS_CHECKED_PREFIX + key, now)
                    .putString(RADIODNS_RESULT_PREFIX + key, RadioDnsLogoResolver.lastTrace.value.summary)
                    .apply()
                if (!force && cacheFresh) return@withContext cached
            }
            if (!force && cacheFresh) return@withContext cached

            val resolvedStation = FmStationIdentity.resolve(stationName, null, frequencies, pi, ecc)
            val identity = AustrianFmStationCatalog.identify(resolvedStation.canonicalName, frequencies)
            if (pi <= 0 && identity == null && !isSafeAutomaticName(resolvedStation.canonicalName)) return@withContext cached
            val lastFailure = failedAt[key] ?: 0L
            if (!force && now - lastFailure < RETRY_COOLDOWN_MS) return@withContext cached
''',
)
replace_once(
    resolver,
    '''            .remove(UPDATED_PREFIX + key)
            .apply()
''',
    '''            .remove(UPDATED_PREFIX + key)
            .remove(RADIODNS_CHECKED_PREFIX + key)
            .remove(RADIODNS_RESULT_PREFIX + key)
            .apply()
''',
)


# Expose the exact RadioDNS stage in the existing FM diagnostics and add a cache-independent test button.
diag = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/FmRadioDiagnostics.kt"
replace_once(
    diag,
    '''    val revision by ReliableFmStationLogoResolver.revisions.collectAsState()
''',
    '''    val revision by ReliableFmStationLogoResolver.revisions.collectAsState()
    val radioDnsTrace by RadioDnsLogoResolver.lastTrace.collectAsState()
''',
)
replace_once(
    diag,
    '''        Text("Bearer: $bearer", style = MaterialTheme.typography.bodySmall)
''',
    '''        Text("Bearer: $bearer", style = MaterialTheme.typography.bodySmall)
        Text(
            "RadioDNS-Status: ${radioDnsTrace.stage}${radioDnsTrace.detail.takeIf { it.isNotBlank() }?.let { ": $it" }.orEmpty()}",
            style = MaterialTheme.typography.bodySmall,
        )
        if (radioDnsTrace.eccSource.isNotBlank()) {
            Text(
                "RadioDNS-ECC: ${radioDnsTrace.ecc.uppercase(Locale.ROOT)} aus ${radioDnsTrace.eccSource}",
                style = MaterialTheme.typography.bodySmall,
            )
        }
        if (radioDnsTrace.cnameChain.isNotEmpty()) {
            Text("CNAME: ${radioDnsTrace.cnameChain.joinToString(" → ")}", style = MaterialTheme.typography.bodySmall, maxLines = 3)
        }
        if (radioDnsTrace.srvTargets.isNotEmpty()) {
            Text("SRV: ${radioDnsTrace.srvTargets.joinToString()}", style = MaterialTheme.typography.bodySmall, maxLines = 2)
        }
        if (radioDnsTrace.siUrl.isNotBlank()) {
            Text("SI: ${radioDnsTrace.siUrl}", style = MaterialTheme.typography.bodySmall, maxLines = 3)
        }
''',
)
replace_once(
    diag,
    '''        Button(
            onClick = {
                scope.launch {
                    ReliableFmStationLogoResolver.invalidateAuto(context, state.displayStation, state.frequency, state.pi, state.ecc)
''',
    '''        Button(
            onClick = {
                scope.launch {
                    val frequencies =
                        (listOf(state.frequency) + state.alternativeFrequencies + state.rtrAfPredictions.map { it.frequency })
                            .distinctBy { (it * 100f).roundToInt() }
                    for (candidateFrequency in frequencies) {
                        if (RadioDnsLogoResolver.resolveFm(context, candidateFrequency, state.pi, state.ecc).isNotEmpty()) break
                    }
                }
            },
            enabled = state.pi > 0,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("RADIODNS DIREKT TESTEN") }
        Button(
            onClick = {
                scope.launch {
                    ReliableFmStationLogoResolver.invalidateAuto(context, state.displayStation, state.frequency, state.pi, state.ecc)
''',
)


# Replace the official RTR index with deterministic joins, public-name validation and DMS coordinate support.
write(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrOfficialProgramIndex.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.radio.fyt

        import kotlinx.serialization.json.Json
        import kotlinx.serialization.json.JsonArray
        import kotlinx.serialization.json.JsonObject
        import kotlinx.serialization.json.JsonPrimitive
        import kotlinx.serialization.json.contentOrNull
        import kotlinx.serialization.json.jsonArray
        import kotlinx.serialization.json.jsonObject
        import java.util.Locale
        import kotlin.math.abs
        import kotlin.math.roundToInt

        /** Resolves public programme names from RTR's MedienFrequenzbuch without guessing ambiguous rows. */
        class RtrOfficialProgramIndex private constructor(
            private val byFrequency: Map<Int, List<Entry>>,
            val recordCount: Int,
        ) {
            data class Entry(
                val publicName: String,
                val frequency: Float,
                val stationCode: String,
                val pi: Int,
                val stationName: String,
                val stationLocation: String,
                val broadcaster: String,
                val latitude: Double?,
                val longitude: Double?,
            )

            fun resolve(
                frequency: Float,
                stationCode: String,
                pi: Int,
                stationName: String,
                stationLocation: String,
                broadcaster: String,
                latitude: Double,
                longitude: Double,
            ): String? {
                val candidates = byFrequency[frequencyKey(frequency)].orEmpty()
                if (candidates.isEmpty()) return null

                val strategies = listOf(
                    candidates.filter { stationCode.isNotBlank() && it.stationCode.equals(stationCode, ignoreCase = true) },
                    candidates.filter { pi > 0 && it.pi == pi },
                    candidates.filter { sameText(it.stationName, stationName) && sameText(it.stationLocation, stationLocation) },
                    candidates.filter { sameText(it.stationName, stationName) || sameText(it.stationLocation, stationLocation) },
                    candidates.filter {
                        it.latitude != null && it.longitude != null &&
                            abs(it.latitude - latitude) <= 0.002 && abs(it.longitude - longitude) <= 0.002
                    },
                    candidates.filter { sameText(it.broadcaster, broadcaster) },
                )
                strategies.forEach { matches -> uniquePublicName(matches)?.let { return it } }
                return uniquePublicName(candidates.takeIf { it.size == 1 }.orEmpty())
            }

            private fun uniquePublicName(entries: List<Entry>): String? {
                if (entries.isEmpty()) return null
                val names = entries.map(Entry::publicName).filter(String::isNotBlank).distinctBy(RtrFmText::key)
                return names.singleOrNull()
            }

            companion object {
                private val json = Json { ignoreUnknownKeys = true }
                private val EMPTY = RtrOfficialProgramIndex(emptyMap(), 0)

                fun parseOrEmpty(payload: String?): RtrOfficialProgramIndex {
                    if (payload.isNullOrBlank()) return EMPTY
                    return runCatching {
                        val root = json.parseToJsonElement(payload).jsonObject
                        val rows = root["data"]?.jsonArray ?: JsonArray(emptyList())
                        val entries = rows.mapNotNull { element ->
                            val row = element.jsonObject
                            val rawProgram = row.string("programm_liste").trim()
                            val frequency = row.string("funkst_frequenz").decimalOrNull()?.toFloat() ?: return@mapNotNull null
                            if (rawProgram.isBlank() || frequency !in 87.5f..108.0f) return@mapNotNull null
                            val broadcaster = row.string("veranstalter_name")
                            val coverageName = row.string("versorgungsgebiet").ifBlank { row.string("gebiet_name") }
                            Entry(
                                publicName = RtrPublicProgramName.resolve(rawProgram, broadcaster, coverageName),
                                frequency = frequency,
                                stationCode = row.string("funkst_code").trim(),
                                pi = parsePi(row.string("funkst_rds")),
                                stationName = row.string("funkst_name"),
                                stationLocation = row.string("funkst_standort"),
                                broadcaster = broadcaster,
                                latitude = parseCoordinate(row.string("funkst_nord")),
                                longitude = parseCoordinate(row.string("funkst_ost")),
                            )
                        }
                        RtrOfficialProgramIndex(entries.groupBy { frequencyKey(it.frequency) }, entries.size)
                    }.getOrElse { EMPTY }
                }

                internal fun parseCoordinate(value: String): Double? {
                    val normalized = value.trim().uppercase(Locale.ROOT).replace(',', '.')
                    normalized.toDoubleOrNull()?.let { return it }
                    val prefixDirection = Regex("^([0-9]{1,3})\\s*([NSEW])\\s*([0-9]{1,2})(?:\\s+|[^0-9.]+)([0-9]{1,2}(?:\\.[0-9]+)?)$")
                    val suffixDirection = Regex("^([0-9]{1,3})(?:\\s+|[^0-9.]+)([0-9]{1,2})(?:\\s+|[^0-9.]+)([0-9]{1,2}(?:\\.[0-9]+)?)\\s*([NSEW])$")
                    val first = prefixDirection.matchEntire(normalized)
                    val second = suffixDirection.matchEntire(normalized)
                    val degrees: Double
                    val minutes: Double
                    val seconds: Double
                    val direction: String
                    when {
                        first != null -> {
                            degrees = first.groupValues[1].toDouble()
                            direction = first.groupValues[2]
                            minutes = first.groupValues[3].toDouble()
                            seconds = first.groupValues[4].toDouble()
                        }
                        second != null -> {
                            degrees = second.groupValues[1].toDouble()
                            minutes = second.groupValues[2].toDouble()
                            seconds = second.groupValues[3].toDouble()
                            direction = second.groupValues[4]
                        }
                        else -> return null
                    }
                    if (minutes !in 0.0..<60.0 || seconds !in 0.0..<60.0) return null
                    val decimal = degrees + minutes / 60.0 + seconds / 3600.0
                    return if (direction == "S" || direction == "W") -decimal else decimal
                }

                private fun frequencyKey(value: Float): Int = (value * 10f).roundToInt()
                private fun parsePi(value: String): Int =
                    value.trim().takeIf { it.matches(Regex("[0-9A-Fa-f]{4}")) }?.toIntOrNull(16) ?: 0
                private fun sameText(first: String, second: String): Boolean =
                    first.isNotBlank() && second.isNotBlank() && RtrFmText.key(first) == RtrFmText.key(second)
                private fun JsonObject.string(name: String): String =
                    (get(name) as? JsonPrimitive)?.contentOrNull.orEmpty()
                private fun String.decimalOrNull(): Double? = trim().replace(',', '.').toDoubleOrNull()
            }
        }
        '''
    ),
)

catalog = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmCatalog.kt"
replace_once(catalog, "import kotlin.math.tan\n", "import kotlin.math.tan\nimport timber.log.Timber\n")
replace_once(
    catalog,
    '''        val stations =
            programs.mapNotNull { element ->
''',
    '''        var officialLinks = 0
        val stations =
            programs.mapNotNull { element ->
''',
)
replace_once(
    catalog,
    '''                val latitude = row.string("rtr_funkst_nord").decimalOrNull() ?: return@mapNotNull null
                val longitude = row.string("rtr_funkst_ost").decimalOrNull() ?: return@mapNotNull null
''',
    '''                val latitude = RtrOfficialProgramIndex.parseCoordinate(row.string("rtr_funkst_nord")) ?: return@mapNotNull null
                val longitude = RtrOfficialProgramIndex.parseCoordinate(row.string("rtr_funkst_ost")) ?: return@mapNotNull null
''',
)
replace_once(
    catalog,
    '''                val code = row.string("rtr_gebiet_code").trim()
                val pi = parseExactPi(row.string("rtr_funkst_rds"))
                val program = officialNames.resolve(
                    frequency = frequency,
                    coverageCode = code,
''',
    '''                val code = row.string("rtr_gebiet_code").trim()
                val stationCode = row.string("rtr_funkst_code").trim()
                val pi = parseExactPi(row.string("rtr_funkst_rds"))
                val officialProgram = officialNames.resolve(
                    frequency = frequency,
                    stationCode = stationCode,
''',
)
replace_once(
    catalog,
    '''                    longitude = longitude,
                ) ?: RtrPublicProgramName.resolve(
''',
    '''                    longitude = longitude,
                )
                if (officialProgram != null) officialLinks += 1
                val program = officialProgram ?: RtrPublicProgramName.resolve(
''',
)
replace_once(
    catalog,
    '''        return RtrCatalogSnapshot(
''',
    '''        Timber.tag("RtrFmCatalog").i(
            "MedienFrequenzbuch loaded records=%d linked=%d senderkataster=%d",
            officialNames.recordCount,
            officialLinks,
            stations.size,
        )
        return RtrCatalogSnapshot(
''',
)

repo = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"
replace_once(
    repo,
    '''    private val officialCatalogFile = File(cacheDirectory, "medien-frequenzbuch.json")
    private val coverageDirectory = File(cacheDirectory, "coverage").apply { mkdirs() }
''',
    '''    private val officialCatalogFile = File(cacheDirectory, "medien-frequenzbuch.json")
    private val schemaFile = File(cacheDirectory, "schema.version")
    private val coverageDirectory = File(cacheDirectory, "coverage").apply { mkdirs() }
''',
)
replace_once(
    repo,
    '''    val state: StateFlow<RtrRepositoryState> = _state.asStateFlow()

    @Volatile
''',
    '''    val state: StateFlow<RtrRepositoryState> = _state.asStateFlow()

    init {
        ensureCacheSchema()
    }

    @Volatile
''',
)
replace_once(
    repo,
    '''    private fun parseCatalog(payload: String): RtrCatalogSnapshot =
''',
    '''    private fun ensureCacheSchema() {
        val existing = schemaFile.takeIf(File::isFile)?.readText()?.trim()?.toIntOrNull()
        if (existing == CACHE_SCHEMA_VERSION) return
        catalogFile.delete()
        officialCatalogFile.delete()
        coverageDirectory.listFiles()?.forEach(File::delete)
        schemaFile.writeText(CACHE_SCHEMA_VERSION.toString())
        Timber.tag(TAG).i("RTR cache schema reset %s -> %d", existing?.toString() ?: "none", CACHE_SCHEMA_VERSION)
    }

    private fun parseCatalog(payload: String): RtrCatalogSnapshot =
''',
)
replace_once(repo, 'setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.26")', 'setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.27")')
replace_once(
    repo,
    '''        private const val MIN_EXPECTED_STATIONS = 500
''',
    '''        private const val MIN_EXPECTED_STATIONS = 500
        private const val CACHE_SCHEMA_VERSION = 4
''',
)


# Port all playback-relevant changes from current original MetroList since the pinned 13.6.1 baseline.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt",
    '''        // For IO_UNSPECIFIED and IO_BAD_HTTP_STATUS, try recovery first
        if (error.errorCode == PlaybackException.ERROR_CODE_IO_UNSPECIFIED ||
            error.errorCode == PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS
        ) {
''',
    '''        // For IO_BAD_HTTP_STATUS, try recovery first. IO_UNSPECIFIED may require
        // client fallback instead of repeatedly reloading the same authenticated URL.
        if (error.errorCode == PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS) {
''',
)
# Newer original MetroList removed this DETACH block; tolerate branches where it is already absent.
music_service_path = ROOT / "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
music_service = music_service_path.read_text(encoding="utf-8")
music_service = music_service.replace(
    '''        // User removed the task while paused: drop foreground promotion so the process can idle.
        // Queue/state remain persisted; opening the app restores playback as usual.
        if (::player.isInitialized && !player.isPlaying) {
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_DETACH)
        }
''',
    "",
)
music_service_path.write_text(music_service, encoding="utf-8")

yt = "app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt"
replace_once(
    yt,
    '''                if (currentClient.clientName == "WEB_REMIX" &&
                    !webRemixFailedIds.contains(videoId)
                ) {
''',
    '''                val isUgcOrPodcast =
                    musicVideoType == "MUSIC_VIDEO_TYPE_UGC" ||
                        musicVideoType?.contains("PODCAST") == true ||
                        musicVideoType == null

                if (currentClient.clientName == "WEB_REMIX" &&
                    !webRemixFailedIds.contains(videoId) &&
                    !isUgcOrPodcast
                ) {
''',
)
replace_once(
    yt,
    '''            val response = httpClient.newCall(requestBuilder.build()).execute()
            val isSuccessful = response.isSuccessful
            Timber.tag(logTag).d("Stream URL validation result: ${if (isSuccessful) "Success" else "Failed"} (${response.code})")
            return isSuccessful
''',
    '''            httpClient.newCall(requestBuilder.build()).execute().use { response ->
                val isSuccessful = response.isSuccessful
                Timber.tag(logTag).d("Stream URL validation result: ${if (isSuccessful) "Success" else "Failed"} (${response.code})")
                return isSuccessful
            }
''',
)


# Focused regression tests.
write(
    "app/src/test/kotlin/com/metrolist/music/variant/VehicleLastTabStoreTest.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.variant

        import org.junit.Assert.assertEquals
        import org.junit.Test

        class VehicleLastTabStoreTest {
            private val routes = setOf("vehicle_queue", "vehicle_webradio", "vehicle_physical_radio", "search")

            @Test
            fun restoresValidMainRoute() {
                assertEquals("vehicle_physical_radio", VehicleLastTabStore.normalize("vehicle_physical_radio", routes, "vehicle_queue"))
            }

            @Test
            fun rejectsDetailAndUnknownRoutes() {
                assertEquals("vehicle_queue", VehicleLastTabStore.normalize("artist/abc", routes, "vehicle_queue"))
                assertEquals("vehicle_queue", VehicleLastTabStore.normalize("removed_tab", routes, "vehicle_queue"))
            }
        }
        '''
    ),
)
write(
    "app/src/test/kotlin/com/metrolist/music/radio/RadioDnsLogoResolverTest.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.radio

        import org.junit.Assert.assertEquals
        import org.junit.Assert.assertFalse
        import org.junit.Assert.assertTrue
        import org.junit.Test

        class RadioDnsLogoResolverTest {
            @Test
            fun buildsOfficialFmLookupAndBearer() {
                val identity = RadioDnsLogoResolver.buildFmIdentity(98.7f, 0xA902, "E0")!!
                assertEquals("09870.a902.ae0.fm.radiodns.org", identity.lookup)
                assertEquals("fm:ae0.a902.09870", identity.bearer)
            }

            @Test
            fun bearerAllowsOnlyOneFrequencyCodeTolerance() {
                assertTrue(RadioDnsLogoResolver.bearerMatches("fm:ae0.a902.09871", "fm:ae0.a902.09870"))
                assertFalse(RadioDnsLogoResolver.bearerMatches("fm:ae0.a903.09870", "fm:ae0.a902.09870"))
                assertFalse(RadioDnsLogoResolver.bearerMatches("fm:ae0.a902.09873", "fm:ae0.a902.09870"))
            }
        }
        '''
    ),
)
write(
    "app/src/test/kotlin/com/metrolist/music/radio/fyt/RtrOfficialCoordinateTest.kt",
    textwrap.dedent(
        '''\
        package com.metrolist.music.radio.fyt

        import org.junit.Assert.assertEquals
        import org.junit.Test

        class RtrOfficialCoordinateTest {
            @Test
            fun parsesRtrDegreeMinuteSecondCoordinates() {
                assertEquals(15.711944, RtrOfficialProgramIndex.parseCoordinate("015E42 43")!!, 0.000001)
                assertEquals(48.213056, RtrOfficialProgramIndex.parseCoordinate("48N12 47")!!, 0.000001)
            }
        }
        '''
    ),
)

print("Applied Metrolist dudu7 13.7.27 complete fix")
