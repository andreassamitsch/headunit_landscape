package com.metrolist.music.radio

import android.content.Context
import android.util.Xml
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import org.xmlpull.v1.XmlPullParser
import java.io.ByteArrayInputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.Locale
import timber.log.Timber
import kotlin.math.abs
import kotlin.math.roundToInt

/** RadioDNS Project Logo lookup for an FM bearer using RDS PI, frequency and GCC. */
object RadioDnsLogoResolver {
    private const val TAG = "RadioDNS"
    private const val USER_AGENT = "MetrolistHU/13.7.8 (RadioDNS receiver)"
    private const val DNS_ENDPOINT = "https://dns.google/resolve"
    private const val MAX_SI_BYTES = 3_000_000

    suspend fun resolveFm(
        context: Context,
        frequency: Float,
        pi: Int,
        ecc: String? = null,
    ): List<RadioLogoCandidate> =
        withContext(Dispatchers.IO) {
            if (pi <= 0 || frequency !in 65f..110f) return@withContext emptyList()
            val resolvedEcc = normaliseEcc(ecc) ?: defaultEcc(context) ?: return@withContext emptyList()
            val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
            val gcc = "${piHex.first()}$resolvedEcc"
            val frequencyCode = (frequency * 100f).roundToInt().toString().padStart(5, '0')
            val lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org"
            Timber.tag(TAG).d("lookup=%s PI=%s ECC=%s GCC=%s", lookup, piHex, resolvedEcc, gcc)
            val authoritative = dnsAnswers(lookup, 5).firstOrNull()?.trimEnd('.')
            if (authoritative.isNullOrBlank()) {
                Timber.tag(TAG).d("No CNAME for %s", lookup)
                return@withContext emptyList()
            }
            val srv = dnsAnswers("_radioepg._tcp.$authoritative", 33).mapNotNull(::parseSrv).minByOrNull { it.priority }
            if (srv == null) {
                Timber.tag(TAG).d("No RadioEPG SRV for %s", authoritative)
                return@withContext emptyList()
            }
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            Timber.tag(TAG).d("CNAME=%s SRV=%s:%d bearer=%s", authoritative, srv.target, srv.port, bearer)
            serviceInformationUrls(srv).forEach { siUrl ->
                val xml = download(siUrl)
                if (xml == null) {
                    Timber.tag(TAG).d("SPI unavailable %s", siUrl)
                    return@forEach
                }
                val logos = parseServiceInformation(xml, siUrl, bearer)
                if (logos.isNotEmpty()) {
                    Timber.tag(TAG).i("Resolved %d logo(s) for %s via %s", logos.size, bearer, siUrl)
                    return@withContext logos.sortedByDescending { it.ranking }
                }
            }
            Timber.tag(TAG).d("No matching multimedia entry for %s", bearer)
            emptyList()
        }

    fun defaultEcc(context: Context): String? {
        val locale = context.resources.configuration.locales.get(0) ?: Locale.getDefault()
        return when (locale.country.uppercase(Locale.ROOT)) {
            "AT" -> "e0"
            "DE" -> "e0"
            "CH" -> "e1"
            "LI" -> "e2"
            else -> null
        }
    }

    private data class SrvRecord(val priority: Int, val port: Int, val target: String)

    private fun parseSrv(value: String): SrvRecord? {
        val parts = value.trim().split(Regex("\\s+"))
        if (parts.size < 4) return null
        return SrvRecord(
            priority = parts[0].toIntOrNull() ?: return null,
            port = parts[2].toIntOrNull() ?: return null,
            target = parts[3].trimEnd('.'),
        )
    }

    private fun serviceInformationUrls(srv: SrvRecord): List<String> {
        val authority = if ((srv.port == 443) || (srv.port == 80)) srv.target else "${srv.target}:${srv.port}"
        val preferredScheme = if (srv.port == 443) "https" else "http"
        val alternateScheme = if (preferredScheme == "https") "http" else "https"
        return buildList {
            add("$preferredScheme://$authority/radiodns/spi/3.1/SI.xml")
            add("$preferredScheme://$authority/radiodns/spi/3.2/SI.xml")
            add("$alternateScheme://$authority/radiodns/spi/3.1/SI.xml")
        }.distinct()
    }

    private fun dnsAnswers(name: String, type: Int): List<String> {
        val endpoint = "$DNS_ENDPOINT?name=${encode(name)}&type=$type"
        val connection = open(endpoint, "application/dns-json,application/json") ?: return emptyList()
        return try {
            if (connection.responseCode !in 200..299) return emptyList()
            val root = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            if (root.optInt("Status", -1) != 0) return emptyList()
            val answers = root.optJSONArray("Answer") ?: return emptyList()
            buildList {
                for (index in 0 until answers.length()) {
                    val answer = answers.optJSONObject(index) ?: continue
                    if (answer.optInt("type") == type) answer.optString("data").takeIf { it.isNotBlank() }?.let(::add)
                }
            }
        } catch (_: Exception) {
            emptyList()
        } finally {
            connection.disconnect()
        }
    }

    private fun download(url: String): ByteArray? {
        val connection = open(url, "application/xml,text/xml") ?: return null
        return try {
            if (connection.responseCode !in 200..299) return null
            val output = java.io.ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(8192)
                var total = 0
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    total += read
                    if (total > MAX_SI_BYTES) return null
                    output.write(buffer, 0, read)
                }
            }
            output.toByteArray().takeIf { it.isNotEmpty() }
        } catch (_: Exception) {
            null
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
                XmlPullParser.START_TAG -> {
                    when (parser.name.substringAfter(':')) {
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
                                val width = parser.getAttributeValue(null, "width")?.toIntOrNull() ?: 0
                                val height = parser.getAttributeValue(null, "height")?.toIntOrNull() ?: 0
                                logos += RadioLogoCandidate(
                                    url = resolvedUrl,
                                    source = RadioLogoSource.RADIO_DNS,
                                    matchScore = 100,
                                    width = width,
                                    height = height,
                                    title = serviceName,
                                )
                            }
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

    private fun bearerMatches(actual: String, expected: String): Boolean {
        if (actual.equals(expected, ignoreCase = true)) return true
        val left = actual.lowercase(Locale.ROOT).split('.')
        val right = expected.lowercase(Locale.ROOT).split('.')
        if (left.size != 3 || right.size != 3) return false
        return left[0] == right[0] && left[1] == right[1] &&
            abs((left[2].toIntOrNull() ?: -1) - (right[2].toIntOrNull() ?: -2)) <= 1
    }

    private fun normaliseEcc(value: String?): String? =
        value?.trim()?.lowercase(Locale.ROOT)?.takeIf { it.matches(Regex("[0-9a-f]{2}")) }

    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    private fun open(url: String, accept: String): HttpURLConnection? =
        runCatching {
            (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 6_000
                readTimeout = 9_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", accept)
            }
        }.getOrNull()
}
