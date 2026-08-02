package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.jsoup.Jsoup
import org.jsoup.nodes.Element
import timber.log.Timber
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.nio.charset.Charset
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap

/**
 * Conservative fallback resolver for a known radio.at station slug.
 *
 * This is deliberately not a search engine. It only opens the exact station page and accepts
 * images that either have a matching station label or whose file name matches the known slug.
 */
internal object RadioAtPageLogoResolver {
    private const val TAG = "RadioAtPageLogo"
    private const val USER_AGENT = "MetrolistHU/13.7.47 (radio.at logo fallback)"
    private const val MAX_HTML_BYTES = 1_500_000
    private const val PAGE_MATCH_THRESHOLD = 72
    private const val IMAGE_MATCH_THRESHOLD = 72

    private data class HtmlPage(
        val html: String,
        val finalUrl: String,
    )

    private data class RankedImage(
        val url: String,
        val title: String,
        val width: Int,
        val height: Int,
        val score: Int,
        val matchScore: Int,
    )

    private val slugLocks = ConcurrentHashMap<String, Mutex>()

    suspend fun resolve(
        slug: String,
        expectedName: String,
    ): RadioLogoCandidate? =
        withContext(Dispatchers.IO) {
            val normalizedSlug = normalizeSlug(slug) ?: return@withContext null
            slugLocks.getOrPut(normalizedSlug) { Mutex() }.withLock {
                val pageUrl = "https://www.radio.at/s/$normalizedSlug"
                val page = readHtml(pageUrl)
                if (page == null) {
                    Timber.tag(TAG).w("radio.at fallback page failed slug=%s page=%s", normalizedSlug, pageUrl)
                    return@withLock null
                }
                val candidate = resolveFromHtml(page.html, page.finalUrl, normalizedSlug, expectedName)
                if (candidate == null) {
                    Timber.tag(TAG).w(
                        "radio.at fallback found no reliable image slug=%s page=%s station=%s",
                        normalizedSlug,
                        page.finalUrl,
                        expectedName,
                    )
                } else {
                    Timber.tag(TAG).i(
                        "radio.at fallback resolved slug=%s page=%s image=%s",
                        normalizedSlug,
                        page.finalUrl,
                        candidate.url,
                    )
                }
                candidate
            }
        }

    internal fun resolveFromHtml(
        html: String,
        pageUrl: String,
        slug: String,
        expectedName: String,
    ): RadioLogoCandidate? {
        val normalizedSlug = normalizeSlug(slug) ?: return null
        val document = Jsoup.parse(html, pageUrl)
        val pageName =
            document.selectFirst("h1")?.text()?.trim().orEmpty()
                .ifBlank { document.title().substringBefore('|').trim() }
        val pageMatch = RadioStationLogoSearch.stationMatchScore(expectedName, pageName)
        if (pageMatch < PAGE_MATCH_THRESHOLD) {
            Timber.tag(TAG).w(
                "radio.at fallback page mismatch slug=%s expected=%s actual=%s score=%d",
                normalizedSlug,
                expectedName,
                pageName,
                pageMatch,
            )
            return null
        }

        val candidates = mutableListOf<RankedImage>()

        fun addCandidate(
            rawUrl: String,
            title: String,
            width: Int = 0,
            height: Int = 0,
            sourceBonus: Int = 0,
        ) {
            val absolute = resolveUrl(pageUrl, rawUrl) ?: return
            val imageMatch = RadioStationLogoSearch.stationMatchScore(expectedName, title)
            val urlScore = slugUrlScore(absolute, normalizedSlug)
            if (imageMatch < IMAGE_MATCH_THRESHOLD && urlScore <= 0) return
            val genericPenalty = genericPenalty(absolute, title)
            val shapeBonus = if (width > 0 && height > 0 && kotlin.math.abs(width - height) <= maxOf(width, height) / 8) 35 else 0
            candidates +=
                RankedImage(
                    url = absolute,
                    title = title.ifBlank { pageName },
                    width = width,
                    height = height,
                    score = pageMatch * 4 + imageMatch * 6 + urlScore + sourceBonus + shapeBonus - genericPenalty,
                    matchScore = maxOf(pageMatch, imageMatch),
                )
        }

        document.select("meta[property], meta[name]").forEach { element ->
            val key = (element.attr("property").ifBlank { element.attr("name") }).lowercase(Locale.ROOT)
            if (key in setOf("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src")) {
                addCandidate(element.attr("content"), pageName, sourceBonus = 25)
            }
        }
        document.select("link[rel=image_src]").forEach { element ->
            addCandidate(element.attr("href"), pageName, sourceBonus = 20)
        }
        document.select("img").forEach { image ->
            val title = image.attr("alt").ifBlank { image.attr("title") }
            val width = image.intAttribute("width")
            val height = image.intAttribute("height")
            listOf("src", "data-src", "data-lazy-src", "data-original").forEach { attribute ->
                addCandidate(image.attr(attribute), title, width, height, sourceBonus = 45)
            }
            srcSetEntries(image.attr("srcset")).forEach { entry ->
                addCandidate(entry.first, title, maxOf(width, entry.second), height, sourceBonus = 50)
            }
            image.parent()?.select("source[srcset]")?.forEach { source ->
                srcSetEntries(source.attr("srcset")).forEach { entry ->
                    addCandidate(entry.first, title, maxOf(width, entry.second), height, sourceBonus = 55)
                }
            }
        }

        return candidates
            .distinctBy { it.url }
            .maxByOrNull(RankedImage::score)
            ?.let { best ->
                RadioLogoCandidate(
                    url = best.url,
                    source = RadioLogoSource.RADIO_AT,
                    matchScore = best.matchScore,
                    width = best.width,
                    height = best.height,
                    title = best.title,
                )
            }
    }

    private fun readHtml(url: String): HtmlPage? {
        val connection = open(url) ?: return null
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
        } catch (error: Exception) {
            Timber.tag(TAG).w(error, "radio.at fallback HTML read failed url=%s", url)
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun open(url: String): HttpURLConnection? =
        runCatching {
            (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 7_000
                readTimeout = 10_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", "text/html,application/xhtml+xml")
                setRequestProperty("Accept-Language", "de-AT,de;q=0.9,en;q=0.5")
            }
        }.getOrNull()

    private fun Element.intAttribute(name: String): Int =
        attr(name).trim().substringBefore('.').toIntOrNull()?.coerceAtLeast(0) ?: 0

    private fun srcSetEntries(value: String): List<Pair<String, Int>> =
        value.split(',').mapNotNull { part ->
            val pieces = part.trim().split(Regex("\\s+"), limit = 2)
            val url = pieces.firstOrNull().orEmpty()
            if (url.isBlank()) return@mapNotNull null
            val width = pieces.getOrNull(1)?.removeSuffix("w")?.toIntOrNull() ?: 0
            url to width
        }

    private fun slugUrlScore(
        value: String,
        slug: String,
    ): Int {
        val path = runCatching { URI(value).path.lowercase(Locale.ROOT) }.getOrDefault("")
        val fileName = path.substringAfterLast('/').substringBeforeLast('.').replace(Regex("[^a-z0-9-]+"), "")
        return when {
            fileName == slug -> 520
            fileName.startsWith("$slug-") || fileName.endsWith("-$slug") -> 360
            fileName.contains(slug) -> 250
            "/$slug." in path || "/$slug/" in path -> 180
            else -> 0
        }
    }

    private fun genericPenalty(
        url: String,
        title: String,
    ): Int {
        val value = "$url $title".lowercase(Locale.ROOT)
        return when {
            "qr" in value || "qrcode" in value || "app-store" in value || "play-store" in value -> 900
            "podcast" in value || "episode" in value || "cover" in value -> 700
            "radio-logo" in value || "placeholder" in value || "default" in value -> 550
            else -> 0
        }
    }

    private fun resolveUrl(
        baseUrl: String,
        candidate: String,
    ): String? =
        runCatching { URI(baseUrl).resolve(candidate.trim()).toString() }
            .getOrNull()
            ?.takeIf(::isHttpUrl)

    private fun isHttpUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true) || value.startsWith("http://", ignoreCase = true)

    private fun normalizeSlug(value: String): String? =
        value.trim().lowercase(Locale.ROOT).takeIf { it.matches(Regex("[a-z0-9-]+")) }
}
