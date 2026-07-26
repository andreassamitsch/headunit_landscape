package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.text.Normalizer
import java.util.Locale

/** A logo result keeps its origin and quality metadata instead of losing it as a naked URL. */
data class RadioLogoCandidate(
    val url: String,
    val source: RadioLogoSource,
    val matchScore: Int,
    val width: Int = 0,
    val height: Int = 0,
    val title: String = "",
) {
    val displayDetails: String
        get() =
            buildList {
                add(source.label)
                if (width > 0 && height > 0) add("${width}×$height")
            }.joinToString(" · ")

    internal val ranking: Int
        get() {
            val squareBonus = if (width > 0 && height > 0 && kotlin.math.abs(width - height) <= maxOf(width, height) / 12) 120 else 0
            val resolutionBonus = minOf(width, height).coerceAtMost(800) / 8
            val haystack = "$url $title".lowercase(Locale.ROOT)
            val genericPenalty =
                when {
                    "radiothek" in haystack -> 750
                    "podcast" in haystack -> 650
                    "app-icon" in haystack || "appicon" in haystack -> 480
                    "#1" in haystack || "number-1" in haystack -> 350
                    "default" in haystack || "placeholder" in haystack -> 500
                    else -> 0
                }
            return source.basePriority + matchScore * 2 + squareBonus + resolutionBonus - genericPenalty
        }
}

enum class RadioLogoSource(
    val label: String,
    internal val basePriority: Int,
) {
    RADIO_DNS("RadioDNS · offiziell", 1300),
    STATION_WEBSITE("Senderwebsite", 1000),
    RADIO_AT("radio.at", 950),
    RADIO_BROWSER("Radio Browser", 700),
    WIKIMEDIA("Wikimedia", 680),
}

/**
 * Multi-source station-logo search. Exact station assets outrank generic platform
 * artwork, square high-resolution images outrank small favicons, and every result
 * remains attributable in the editor.
 */
object RadioStationLogoSearch {
    private const val USER_AGENT = "MetrolistHU/13.7.8 (station logo search)"
    private const val COMMONS_ENDPOINT = "https://commons.wikimedia.org/w/api.php"
    private const val MAX_HTML_BYTES = 1_500_000

    suspend fun search(
        query: String,
        current: RadioStation?,
    ): Result<List<RadioLogoCandidate>> =
        runCatching {
            val aliases = stationAliases(query)
            require(aliases.isNotEmpty()) { "Sendername fehlt" }
            coroutineScope {
                val stationJobs = aliases.map { alias -> async { RadioBrowserClient.search(alias).getOrDefault(emptyList()) } }
                val commonsJobs = aliases.map { alias -> async { searchCommons(alias) } }
                val radioAtJobs = aliases.map { alias -> async { searchRadioAt(alias) } }

                val stations =
                    stationJobs
                        .awaitAll()
                        .flatten()
                        .distinctBy { it.uuid }
                        .map { station -> aliases.maxOf { alias -> stationMatchScore(alias, station.name) } to station }
                        .filter { (score, _) -> score >= 55 }
                        .sortedByDescending { (score, _) -> score }
                        .take(18)

                val websiteCandidates =
                    buildList {
                        current?.let(::add)
                        addAll(stations.map { it.second })
                    }.distinctBy { "${it.name}|${it.homepage}|${it.favicon}" }
                        .map { station ->
                            async {
                                val match = aliases.maxOf { alias -> stationMatchScore(alias, station.name) }
                                withTimeoutOrNull(8_000L) {
                                    RadioStationLogoResolver.resolve(station)?.let { url ->
                                        RadioLogoCandidate(
                                            url = url,
                                            source = RadioLogoSource.STATION_WEBSITE,
                                            matchScore = match,
                                            title = station.name,
                                        )
                                    }
                                }
                            }
                        }.awaitAll()
                        .filterNotNull()

                val browserCandidates =
                    stations.mapNotNull { (match, station) ->
                        station.favicon.trim().takeIf(::isHttpUrl)?.let { url ->
                            RadioLogoCandidate(
                                url = url,
                                source = RadioLogoSource.RADIO_BROWSER,
                                matchScore = match,
                                title = station.name,
                            )
                        }
                    }

                buildList {
                    addAll(radioAtJobs.awaitAll().flatten())
                    addAll(websiteCandidates)
                    addAll(browserCandidates)
                    addAll(commonsJobs.awaitAll().flatten())
                }.filter { isHttpUrl(it.url) }
                    .distinctBy { it.url.substringBefore('#') }
                    .sortedByDescending { it.ranking }
                    .take(36)
            }
        }

    internal fun stationAliases(value: String): List<String> {
        val cleaned =
            value
                .replace(Regex("\\([^)]*\\)"), " ")
                .replace(
                    Regex("\\b(?:hq|hls|aac|mp3|ogg|opus|flac|stream|livestream|webradio)\\b", RegexOption.IGNORE_CASE),
                    " ",
                ).replace(Regex("\\b\\d{2,4}\\s*(?:kbps|kbit/s|kbit|k)\\b", RegexOption.IGNORE_CASE), " ")
                .replace(Regex("\\s+"), " ")
                .trim(' ', '-', '|')
        val aliases = linkedSetOf<String>()
        fun addAlias(candidate: String) {
            candidate.trim(' ', '-', '|').takeIf { it.length >= 2 }?.let(aliases::add)
        }
        addAlias(cleaned)
        val withoutOrf = cleaned.replace(Regex("^ORF\\s+", RegexOption.IGNORE_CASE), "").trim()
        addAlias(withoutOrf)
        val withoutOrfRadio = cleaned.replace(Regex("^ORF\\s+Radio\\s+", RegexOption.IGNORE_CASE), "").trim()
        addAlias(withoutOrfRadio)
        if (withoutOrf.startsWith("Hitradio ", ignoreCase = true)) addAlias(withoutOrf.substringAfter(' '))
        return aliases.toList()
    }

    private suspend fun searchRadioAt(query: String): List<RadioLogoCandidate> =
        withContext(Dispatchers.IO) {
            radioAtSlugs(query).take(6).forEach { slug ->
                val page = readHtml("https://www.radio.at/s/$slug") ?: return@forEach
                val pageName = extractPageName(page.html)
                val match = stationMatchScore(query, pageName)
                if (match < 72) return@forEach
                val images = extractMetaImages(page.html, page.finalUrl)
                if (images.isNotEmpty()) {
                    return@withContext images.map { url ->
                        RadioLogoCandidate(
                            url = url,
                            source = RadioLogoSource.RADIO_AT,
                            matchScore = match,
                            title = pageName,
                        )
                    }
                }
            }
            emptyList()
        }

    private fun radioAtSlugs(value: String): List<String> {
        val aliases = stationAliases(value)
        val slugs = linkedSetOf<String>()
        aliases.forEach { alias ->
            val transliterated =
                alias.lowercase(Locale.GERMAN)
                    .replace("ä", "ae")
                    .replace("ö", "oe")
                    .replace("ü", "ue")
                    .replace("ß", "ss")
            val compact = transliterated.replace(Regex("[^a-z0-9]+"), "")
            if (compact.isNotBlank()) slugs += compact
            val withoutRadio = transliterated.replace(Regex("^radio\\s+"), "").replace(Regex("[^a-z0-9]+"), "")
            if (withoutRadio.isNotBlank()) slugs += withoutRadio
            if ("ö3" in alias.lowercase(Locale.ROOT) || "oe3" in compact) slugs += "oe3"
        }
        return slugs.toList()
    }

    private suspend fun searchCommons(query: String): List<RadioLogoCandidate> =
        coroutineScope {
            val exact = async { queryCommonsTitles(query) }
            val searched = async { queryCommonsSearch(query) }
            (exact.await() + searched.await()).distinctBy { it.url }
        }

    private suspend fun queryCommonsTitles(query: String): List<RadioLogoCandidate> {
        val titles =
            listOf(
                "File:$query 2024.svg",
                "File:$query 2024.png",
                "File:Logo $query.svg",
                "File:$query.svg",
                "File:$query logo.svg",
            ).distinct()
        val endpoint =
            "$COMMONS_ENDPOINT?action=query" +
                "&titles=${encode(titles.joinToString("|"))}" +
                "&prop=imageinfo" +
                "&iiprop=url%7Cmime%7Csize" +
                "&iiurlwidth=600" +
                "&format=json" +
                "&formatversion=2"
        return readCommonsImages(endpoint, query, 55)
    }

    private suspend fun queryCommonsSearch(query: String): List<RadioLogoCandidate> {
        val endpoint =
            "$COMMONS_ENDPOINT?action=query" +
                "&generator=search" +
                "&gsrsearch=${encode("intitle:\"$query\" logo")}" +
                "&gsrnamespace=6" +
                "&gsrlimit=30" +
                "&prop=imageinfo" +
                "&iiprop=url%7Cmime%7Csize" +
                "&iiurlwidth=600" +
                "&format=json" +
                "&formatversion=2"
        return readCommonsImages(endpoint, query, 58)
    }

    private suspend fun readCommonsImages(
        endpoint: String,
        expectedName: String,
        minimumScore: Int,
    ): List<RadioLogoCandidate> =
        withContext(Dispatchers.IO) {
            withTimeoutOrNull(10_000L) {
                val connection = open(endpoint, "application/json") ?: return@withTimeoutOrNull emptyList()
                try {
                    if (connection.responseCode !in 200..299) return@withTimeoutOrNull emptyList()
                    val root = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                    val pages = root.optJSONObject("query")?.optJSONArray("pages") ?: return@withTimeoutOrNull emptyList()
                    buildList {
                        for (index in 0 until pages.length()) {
                            val page = pages.optJSONObject(index) ?: continue
                            if (page.optBoolean("missing")) continue
                            val title = page.optString("title").removePrefix("File:").substringBeforeLast('.')
                            val score = stationMatchScore(expectedName, title)
                            if (score < minimumScore) continue
                            val info = page.optJSONArray("imageinfo")?.optJSONObject(0) ?: continue
                            val mime = info.optString("mime")
                            if (mime.isNotBlank() && !mime.startsWith("image/")) continue
                            val url = info.optString("thumburl").ifBlank { info.optString("url") }
                            if (!isHttpUrl(url)) continue
                            add(
                                RadioLogoCandidate(
                                    url = url,
                                    source = RadioLogoSource.WIKIMEDIA,
                                    matchScore = score,
                                    width = info.optInt("thumbwidth", info.optInt("width", 0)),
                                    height = info.optInt("thumbheight", info.optInt("height", 0)),
                                    title = title,
                                ),
                            )
                        }
                    }
                } finally {
                    connection.disconnect()
                }
            }.orEmpty()
        }

    internal fun stationMatchScore(expected: String, candidate: String): Int {
        val left = normalize(expected)
        val right = normalize(candidate)
        if (left.isBlank() || right.isBlank()) return 0
        if (left == right) return 100
        if (right.contains(left) || left.contains(right)) return 90
        val expectedTokens = left.split(' ').filter { it.length >= 2 }.toSet()
        val candidateTokens = right.split(' ').filter { it.length >= 2 }.toSet()
        if (expectedTokens.isEmpty() || candidateTokens.isEmpty()) return 0
        return expectedTokens.intersect(candidateTokens).size * 100 / maxOf(expectedTokens.size, candidateTokens.size)
    }

    private data class HtmlPage(val html: String, val finalUrl: String)

    private fun readHtml(url: String): HtmlPage? {
        val connection = open(url, "text/html,application/xhtml+xml") ?: return null
        return try {
            if (connection.responseCode !in 200..299) return null
            val contentType = connection.contentType.orEmpty()
            if (!contentType.contains("html", ignoreCase = true)) return null
            val charsetName = contentType.substringAfter("charset=", "UTF-8").substringBefore(';').trim()
            val charset = runCatching { Charset.forName(charsetName) }.getOrDefault(Charsets.UTF_8)
            val output = ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(8192)
                var remaining = MAX_HTML_BYTES
                while (remaining > 0) {
                    val read = input.read(buffer, 0, minOf(buffer.size, remaining))
                    if (read <= 0) break
                    output.write(buffer, 0, read)
                    remaining -= read
                }
            }
            HtmlPage(output.toString(charset.name()), connection.url.toString())
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun extractPageName(html: String): String {
        val h1 = Regex("<h1[^>]*>(.*?)</h1>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
            .find(html)?.groupValues?.getOrNull(1)
        val title = Regex("<title[^>]*>(.*?)</title>", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
            .find(html)?.groupValues?.getOrNull(1)
        return (h1 ?: title).orEmpty().replace(Regex("<[^>]+>"), " ").replace("&amp;", "&").replace(Regex("\\s+"), " ").trim()
    }

    private fun extractMetaImages(html: String, baseUrl: String): List<String> {
        val tagRegex = Regex("<meta\\b[^>]*>", RegexOption.IGNORE_CASE)
        val attributeRegex = Regex("([A-Za-z_:][A-Za-z0-9_:\\-]*)\\s*=\\s*(['\"])(.*?)\\2", setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL))
        return tagRegex.findAll(html).mapNotNull { match ->
            val attributes = attributeRegex.findAll(match.value).associate { it.groupValues[1].lowercase(Locale.ROOT) to it.groupValues[3].trim() }
            val key = (attributes["property"] ?: attributes["name"]).orEmpty().lowercase(Locale.ROOT)
            if (key !in setOf("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src")) return@mapNotNull null
            resolveUrl(baseUrl, attributes["content"].orEmpty())
        }.filter(::isHttpUrl).distinct().take(4).toList()
    }

    private fun resolveUrl(baseUrl: String, candidate: String): String? =
        runCatching { URI(baseUrl).resolve(candidate.trim()).toString() }.getOrNull()?.takeIf(::isHttpUrl)

    private fun normalize(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()

    private fun encode(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    private fun isHttpUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true) || value.startsWith("http://", ignoreCase = true)

    private fun open(url: String, accept: String): HttpURLConnection? =
        runCatching {
            (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 7_000
                readTimeout = 10_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", accept)
                setRequestProperty("Accept-Language", "de-AT,de;q=0.9,en;q=0.5")
            }
        }.getOrNull()
}
