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
 * Commons. Commons thumbnails are rasterized server-side, so SVG station logos
 * remain usable by the app's normal image loader and local logo cache.
 */
object RadioStationLogoSearch {
    private const val USER_AGENT = "MetrolistHU/13.7.6 (station logo search)"
    private const val COMMONS_ENDPOINT = "https://commons.wikimedia.org/w/api.php"

    suspend fun search(
        query: String,
        current: RadioStation?,
    ): Result<List<String>> =
        runCatching {
            val cleaned = query.trim()
            require(cleaned.isNotBlank()) { "Sendername fehlt" }
            coroutineScope {
                val stationResults = async { RadioBrowserClient.search(cleaned).getOrDefault(emptyList()) }
                val commonsResults = async { searchCommons(cleaned) }
                val stations =
                    stationResults
                        .await()
                        .sortedByDescending { stationMatchScore(cleaned, it.name) }
                        .take(12)
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
                buildList {
                    current?.favicon?.trim()?.takeIf(::isHttpUrl)?.let(::add)
                    addAll(resolvedHomepageLogos)
                    addAll(commonsResults.await())
                    addAll(directFavicons)
                }.filter(::isHttpUrl)
                    .distinct()
                    .take(24)
            }
        }

    private suspend fun searchCommons(query: String): List<String> =
        withContext(Dispatchers.IO) {
            withTimeoutOrNull(10_000L) {
                val searchText = "\"$query\" logo"
                val endpoint =
                    "$COMMONS_ENDPOINT?action=query" +
                        "&generator=search" +
                        "&gsrsearch=${encode(searchText)}" +
                        "&gsrnamespace=6" +
                        "&gsrlimit=20" +
                        "&prop=imageinfo" +
                        "&iiprop=url%7Cmime" +
                        "&iiurlwidth=512" +
                        "&format=json" +
                        "&formatversion=2"
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
                            val score = stationMatchScore(query, title)
                            if (score < 45) continue
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
