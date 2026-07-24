/**
 * Sender artwork discovery inspired by Transistor's local-first station image
 * handling (MIT License): https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.nio.charset.Charset
import java.util.ArrayDeque
import java.util.Locale

object RadioStationLogoResolver {
    private const val USER_AGENT = "MetrolistHU/13.6.9 (Android WebRadio)"
    private const val MAX_HTML_BYTES = 1_500_000
    private const val MAX_PAGES = 5

    private val genericStationWords =
        setOf("radio", "webradio", "web", "fm", "antenne", "the", "der", "die", "das")

    private data class Candidate(
        val url: String,
        val priority: Int,
        val declaredSize: Int = 0,
    )

    private data class HtmlPage(
        val html: String,
        val finalUrl: String,
    )

    suspend fun resolve(station: RadioStation): String? =
        withContext(Dispatchers.IO) {
            if (station.manualFavicon) return@withContext station.favicon.trim().takeIf(::isHttpUrl)
            val candidates = mutableListOf<Candidate>()
            val pageQueue = ArrayDeque<String>()
            val visitedPages = linkedSetOf<String>()
            val homepage = station.homepage.trim().takeIf(::isHttpUrl)
            val existingArtwork = station.favicon.trim().takeIf(::isHttpUrl)

            // Once a usable raster image has been persisted, keep it stable.
            // This prevents stations such as kronehit from alternating between
            // multiple equally valid logos discovered on the same homepage.
            if (existingArtwork != null && !isVectorUrl(existingArtwork)) {
                resolveUsableImage(existingArtwork)?.let { return@withContext it }
            }

            existingArtwork?.let {
                candidates += Candidate(it, priority = if (isVectorUrl(it)) 120 else 520)
            }

            homepage?.let {
                pageQueue.add(it)
                regionalHomepageCandidates(it, station.name).forEach(pageQueue::add)
            }

            while (pageQueue.isNotEmpty() && visitedPages.size < MAX_PAGES) {
                val requestedPage = pageQueue.removeFirst()
                if (!visitedPages.add(requestedPage)) continue
                val page = readHtml(requestedPage) ?: continue
                candidates += extractCandidates(page.html, page.finalUrl, station.name)
                extractStationLinks(page.html, page.finalUrl, station.name)
                    .filterNot(visitedPages::contains)
                    .take(3)
                    .forEach(pageQueue::add)
                commonIconCandidates(page.finalUrl).forEach { candidates += it }
            }

            var vectorFallback: String? = null
            candidates
                .distinctBy { it.url }
                .sortedByDescending(::candidateScore)
                .take(30)
                .forEach { candidate ->
                    val resolved = resolveUsableImage(candidate.url) ?: return@forEach
                    if (isVectorUrl(resolved)) {
                        if (vectorFallback == null) vectorFallback = resolved
                    } else {
                        return@withContext resolved
                    }
                }

            // Coil in this build does not consistently decode SVG station favicons.
            // Prefer a clean initials fallback over persisting a known-broken vector URL.
            null
        }

    private fun candidateScore(candidate: Candidate): Int =
        candidate.priority + candidate.declaredSize.coerceAtMost(1024) / 16 -
            if (isVectorUrl(candidate.url)) 600 else 0

    private fun stationTokens(name: String): List<String> =
        name
            .lowercase(Locale.ROOT)
            .replace(Regex("[^a-z0-9äöüß]+"), " ")
            .split(' ')
            .map(String::trim)
            .filter { it.length >= 3 && it !in genericStationWords }
            .distinct()

    private fun regionalHomepageCandidates(homepage: String, stationName: String): List<String> {
        val uri = runCatching { URI(homepage) }.getOrNull() ?: return emptyList()
        val host = uri.host ?: return emptyList()
        val slug = stationTokens(stationName).joinToString("-")
        if (slug.isBlank()) return emptyList()
        val scheme = if (uri.scheme.equals("http", ignoreCase = true)) "https" else uri.scheme ?: "https"
        return listOf("$scheme://$host/$slug/")
    }

    private fun extractCandidates(
        html: String,
        baseUrl: String,
        stationName: String,
    ): List<Candidate> {
        val candidates = mutableListOf<Candidate>()
        val tagRegex = Regex("""<(meta|link|img|source)\b[^>]*>""", RegexOption.IGNORE_CASE)
        val attributeRegex =
            Regex(
                """([A-Za-z_:][A-Za-z0-9_:\-]*)\s*=\s*(['\"])(.*?)\2""",
                setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
            )
        val tokens = stationTokens(stationName)

        tagRegex.findAll(html).forEach { match ->
            val tag = match.groupValues[1].lowercase(Locale.ROOT)
            val attributes =
                attributeRegex
                    .findAll(match.value)
                    .associate { it.groupValues[1].lowercase(Locale.ROOT) to it.groupValues[3].trim() }

            when (tag) {
                "link" -> {
                    val rel = attributes["rel"].orEmpty().lowercase(Locale.ROOT)
                    val href = attributes["href"]?.takeIf { it.isNotBlank() } ?: return@forEach
                    val resolved = resolveUrl(baseUrl, href) ?: return@forEach
                    val size = parseDeclaredSize(attributes["sizes"])
                    when {
                        "apple-touch-icon" in rel -> candidates += Candidate(resolved, 650, size)
                        "icon" in rel && size >= 128 -> candidates += Candidate(resolved, 580, size)
                        "icon" in rel -> candidates += Candidate(resolved, 390, size)
                    }
                }

                "meta" -> {
                    val key =
                        (attributes["property"] ?: attributes["name"])
                            ?.lowercase(Locale.ROOT)
                            .orEmpty()
                    val content = attributes["content"]?.takeIf { it.isNotBlank() } ?: return@forEach
                    val resolved = resolveUrl(baseUrl, content) ?: return@forEach
                    when (key) {
                        "og:image", "og:image:url", "og:image:secure_url" ->
                            candidates += Candidate(resolved, 560)
                        "twitter:image", "twitter:image:src" -> candidates += Candidate(resolved, 520)
                    }
                }

                "img", "source" -> {
                    val rawSources =
                        listOfNotNull(
                            attributes["src"],
                            attributes["data-src"],
                            attributes["data-lazy-src"],
                            attributes["srcset"]?.substringBefore(',')?.substringBefore(' '),
                        )
                    val context =
                        listOfNotNull(attributes["alt"], attributes["title"], attributes["class"])
                            .joinToString(" ")
                    rawSources.forEach { source ->
                        val resolved = resolveUrl(baseUrl, source) ?: return@forEach
                        imageAssetPriority(resolved, context, tokens)
                            .takeIf { it > 0 }
                            ?.let { candidates += Candidate(resolved, it) }
                    }
                }
            }
        }

        val absoluteImageRegex =
            Regex(
                """https?://[^\s\"'<>]+\.(?:png|jpe?g|webp|gif|avif|svg)(?:\?[^\s\"'<>]*)?""",
                RegexOption.IGNORE_CASE,
            )
        absoluteImageRegex.findAll(html).forEach { match ->
            val url = match.value.replace("&amp;", "&")
            imageAssetPriority(url, "", tokens)
                .takeIf { it > 0 }
                ?.let { candidates += Candidate(url, it) }
        }
        return candidates
    }

    private fun imageAssetPriority(
        url: String,
        context: String,
        stationTokens: List<String>,
    ): Int {
        val haystack = "$url $context".lowercase(Locale.ROOT)
        return when {
            "logo" in haystack -> 820
            stationTokens.any(haystack::contains) && ("cover" in haystack || "live" in haystack) -> 760
            "media-assets" in haystack && ("button" in haystack || "live" in haystack) -> 710
            stationTokens.any(haystack::contains) -> 620
            else -> 0
        }
    }

    private fun extractStationLinks(
        html: String,
        baseUrl: String,
        stationName: String,
    ): List<String> {
        val tokens = stationTokens(stationName)
        if (tokens.isEmpty()) return emptyList()
        val anchorRegex =
            Regex(
                """<a\b[^>]*href\s*=\s*(['\"])(.*?)\1[^>]*>(.*?)</a>""",
                setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
            )
        return anchorRegex
            .findAll(html)
            .mapNotNull { match ->
                val href = match.groupValues[2]
                val text = match.groupValues[3].replace(Regex("<[^>]+>"), " ")
                val haystack = "$href $text".lowercase(Locale.ROOT)
                if (tokens.none(haystack::contains)) return@mapNotNull null
                resolveUrl(baseUrl, href)
            }.filter(::isHttpUrl)
            .distinct()
            .toList()
    }

    private fun commonIconCandidates(pageUrl: String): List<Candidate> {
        val uri = runCatching { URI(pageUrl) }.getOrNull() ?: return emptyList()
        val origin = "${uri.scheme}://${uri.authority}"
        return listOf(
            Candidate("$origin/apple-touch-icon.png", 610, 180),
            Candidate("$origin/android-chrome-512x512.png", 640, 512),
            Candidate("$origin/android-chrome-192x192.png", 600, 192),
            Candidate("$origin/favicon.png", 430),
            Candidate("$origin/favicon.ico", 360),
        )
    }

    private fun parseDeclaredSize(value: String?): Int =
        value
            ?.split(Regex("\\s+"))
            ?.mapNotNull { size ->
                val parts = size.lowercase(Locale.ROOT).split('x')
                if (parts.size != 2) null else minOf(parts[0].toIntOrNull() ?: 0, parts[1].toIntOrNull() ?: 0)
            }?.maxOrNull()
            ?: 0

    private fun resolveUrl(baseUrl: String, candidate: String): String? =
        runCatching { URI(baseUrl).resolve(candidate.trim()).toString() }
            .getOrNull()
            ?.takeIf(::isHttpUrl)

    private fun isHttpUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true) || value.startsWith("http://", ignoreCase = true)

    private fun isVectorUrl(value: String): Boolean =
        value.substringBefore('?').endsWith(".svg", ignoreCase = true)

    private fun readHtml(url: String): HtmlPage? {
        val connection = open(url, "text/html,application/xhtml+xml") ?: return null
        return try {
            val code = connection.responseCode
            if (code !in 200..299) return null
            val contentType = connection.contentType.orEmpty()
            if (!contentType.contains("html", ignoreCase = true)) return null
            val charsetName =
                contentType.substringAfter("charset=", "UTF-8").substringBefore(';').trim()
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

    private fun resolveUsableImage(url: String): String? {
        val connection = open(url, "image/avif,image/webp,image/*,*/*;q=0.8") ?: return null
        return try {
            val code = connection.responseCode
            if (code !in 200..299) return null
            val contentType = connection.contentType.orEmpty().lowercase(Locale.ROOT)
            val finalUrl = connection.url.toString()
            val path = connection.url.path.orEmpty().lowercase(Locale.ROOT)
            val vector = contentType.contains("svg") || path.endsWith(".svg")
            val typeLooksLikeImage = contentType.startsWith("image/")
            val pathLooksLikeImage =
                listOf(".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif")
                    .any(path::endsWith)
            if (!typeLooksLikeImage && !pathLooksLikeImage) return null
            connection.inputStream.use { if (it.read() < 0) return null }
            if (vector) finalUrl else finalUrl
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun open(url: String, accept: String): HttpURLConnection? =
        runCatching {
            (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 7_000
                readTimeout = 9_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", accept)
                setRequestProperty("Cache-Control", "no-cache")
            }
        }.getOrNull()
}
