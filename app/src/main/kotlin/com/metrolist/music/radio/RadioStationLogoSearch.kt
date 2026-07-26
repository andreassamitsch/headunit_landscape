package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.text.Normalizer
import java.util.Locale

/**
 * Finds station artwork from Radio Browser, station homepages and Wikimedia
 * Commons. Technical suffixes such as HQ/HLS/AAC are removed before searching,
 * and likely exact Commons file titles are queried in addition to free search.
 */
object RadioStationLogoSearch {
    private const val USER_AGENT = "MetrolistHU/13.7.7 (station logo search)"
    private const val COMMONS_ENDPOINT = "https://commons.wikimedia.org/w/api.php"

    suspend fun search(
        query: String,
        current: RadioStation?,
    ): Result<List<String>> =
        runCatching {
            val aliases = stationAliases(query)
            require(aliases.isNotEmpty()) { "Sendername fehlt" }

            coroutineScope {
                val stationJobs =
                    aliases.map { alias ->
                        async { RadioBrowserClient.search(alias).getOrDefault(emptyList()) }
                    }
                val commonsJobs = aliases.map { alias -> async { searchCommons(alias) } }

                val stations =
                    stationJobs
                        .awaitAll()
                        .flatten()
                        .distinctBy { it.uuid }
                        .map { station ->
                            aliases.maxOf { alias -> stationMatchScore(alias, station.name) } to station
                        }.filter { (score, _) -> score >= 45 }
                        .sortedByDescending { (score, _) -> score }
                        .map { (_, station) -> station }
                        .take(16)

                val resolverSeeds =
                    buildList {
                        current?.let(::add)
                        addAll(stations)
                    }.distinctBy { "${it.name}|${it.homepage}|${it.favicon}" }

                val resolvedHomepageLogos =
                    resolverSeeds
                        .map { station ->
                            async {
                                withTimeoutOrNull(8_000L) {
                                    RadioStationLogoResolver.resolve(station)
                                }
                            }
                        }.awaitAll()
                        .filterNotNull()

                val directFavicons =
                    stations
                        .map { it.favicon.trim() }
                        .filter(::isHttpUrl)

                // Exact Commons matches come first. For example,
                // "ORF Radio Steiermark HQ" yields the aliases
                // "ORF Radio Steiermark" and "Radio Steiermark", which directly
                // resolves File:Radio Steiermark 2024.svg instead of only showing
                // the generic ORF Radiothek artwork from the station homepage.
                buildList {
                    addAll(commonsJobs.awaitAll().flatten())
                    addAll(directFavicons)
                    addAll(resolvedHomepageLogos)
                    current?.favicon?.trim()?.takeIf(::isHttpUrl)?.let(::add)
                }.filter(::isHttpUrl)
                    .distinct()
                    .take(32)
            }
        }

    private fun stationAliases(value: String): List<String> {
        val cleaned =
            value
                .replace(Regex("\\([^)]*\\)"), " ")
                .replace(
                    Regex(
                        "\\b(?:hq|hls|aac|mp3|ogg|opus|flac|stream|livestream|webradio)\\b",
                        RegexOption.IGNORE_CASE,
                    ),
                    " ",
                ).replace(
                    Regex("\\b\\d{2,4}\\s*(?:kbps|kbit/s|kbit|k)\\b", RegexOption.IGNORE_CASE),
                    " ",
                ).replace(Regex("\\s+"), " ")
                .trim(' ', '-', '|')

        val aliases = linkedSetOf<String>()
        fun addAlias(candidate: String) {
            candidate.trim(' ', '-', '|').takeIf { it.length >= 3 }?.let(aliases::add)
        }

        addAlias(cleaned)
        val withoutOrf = cleaned.replace(Regex("^ORF\\s+", RegexOption.IGNORE_CASE), "").trim()
        addAlias(withoutOrf)
        if (withoutOrf.startsWith("Hitradio ", ignoreCase = true)) {
            addAlias(withoutOrf.substringAfter(' '))
        }
        return aliases.toList()
    }

    private suspend fun searchCommons(query: String): List<String> =
        coroutineScope {
            val exactTitles = async { queryCommonsTitles(query) }
            val titleSearch = async { queryCommonsSearch(query) }
            (exactTitles.await() + titleSearch.await()).distinct()
        }

    private suspend fun queryCommonsTitles(query: String): List<String> {
        val titles =
            listOf(
                "File:$query 2024.svg",
                "File:Logo $query.svg",
                "File:$query.svg",
                "File:$query logo.svg",
            ).distinct()
        val endpoint =
            "$COMMONS_ENDPOINT?action=query" +
                "&titles=${encode(titles.joinToString("|"))}" +
                "&prop=imageinfo" +
                "&iiprop=url%7Cmime" +
                "&iiurlwidth=512" +
                "&format=json" +
                "&formatversion=2"
        return readCommonsImages(endpoint, query, minimumScore = 45)
    }

    private suspend fun queryCommonsSearch(query: String): List<String> {
        val endpoint =
            "$COMMONS_ENDPOINT?action=query" +
                "&generator=search" +
                "&gsrsearch=${encode("intitle:\"$query\"")}" +
                "&gsrnamespace=6" +
                "&gsrlimit=30" +
                "&prop=imageinfo" +
                "&iiprop=url%7Cmime" +
                "&iiurlwidth=512" +
                "&format=json" +
                "&formatversion=2"
        return readCommonsImages(endpoint, query, minimumScore = 45)
    }

    private suspend fun readCommonsImages(
        endpoint: String,
        expectedName: String,
        minimumScore: Int,
    ): List<String> =
        withContext(Dispatchers.IO) {
            withTimeoutOrNull(10_000L) {
                val connection =
                    (URL(endpoint).openConnection() as HttpURLConnection).apply {
                        connectTimeout = 6_000
                        readTimeout = 8_000
                        instanceFollowRedirects = true
                        setRequestProperty("User-Agent", USER_AGENT)
                        setRequestProperty("Accept", "application/json")
                    }
                try {
                    val code = connection.responseCode
                    if (code !in 200..299) return@withTimeoutOrNull emptyList()
                    val root = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                    val pages = root.optJSONObject("query")?.optJSONArray("pages")
                        ?: return@withTimeoutOrNull emptyList()
                    buildList<Pair<Int, String>> {
                        for (index in 0 until pages.length()) {
                            val page = pages.optJSONObject(index) ?: continue
                            val title =
                                page.optString("title")
                                    .removePrefix("File:")
                                    .substringBeforeLast('.')
                            val score = stationMatchScore(expectedName, title)
                            if (score < minimumScore) continue
                            val info = page.optJSONArray("imageinfo")?.optJSONObject(0) ?: continue
                            val mime = info.optString("mime")
                            if (mime.isNotBlank() && !mime.startsWith("image/")) continue
                            val url = info.optString("thumburl").ifBlank { info.optString("url") }
                            if (isHttpUrl(url)) add(score to url)
                        }
                    }.sortedByDescending { it.first }
                        .map { it.second }
                        .distinct()
                } finally {
                    connection.disconnect()
                }
            }.orEmpty()
        }

    private fun stationMatchScore(expected: String, candidate: String): Int {
        val left = normalize(expected)
        val right = normalize(candidate)
        if (left.isBlank() || right.isBlank()) return 0
        if (left == right) return 100
        if (right.contains(left) || left.contains(right)) return 90
        val expectedTokens = left.split(' ').filter { it.length >= 2 }.toSet()
        val candidateTokens = right.split(' ').filter { it.length >= 2 }.toSet()
        if (expectedTokens.isEmpty() || candidateTokens.isEmpty()) return 0
        return expectedTokens.intersect(candidateTokens).size * 100 / expectedTokens.size
    }

    private fun normalize(value: String): String =
        Normalizer
            .normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    private fun isHttpUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true) ||
            value.startsWith("http://", ignoreCase = true)
}
