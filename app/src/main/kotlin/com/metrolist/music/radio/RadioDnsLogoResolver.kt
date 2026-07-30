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
        val parts = value.trim().trim('"').split(Regex("""\s+"""))
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
