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

object RadioStationLogoResolver {
    private const val USER_AGENT = "MetrolistHU/13.6.5 (Android WebRadio)"
    private const val MAX_HTML_BYTES = 512 * 1024

    private data class Candidate(
        val url: String,
        val priority: Int,
        val declaredSize: Int = 0,
    )

    suspend fun resolve(station: RadioStation): String? =
        withContext(Dispatchers.IO) {
            val candidates = mutableListOf<Candidate>()
            val homepage = station.homepage.trim().takeIf(::isHttpUrl)

            if (homepage != null) {
                readHtml(homepage)?.let { html ->
                    candidates += extractCandidates(html, homepage)
                }
            }

            station.favicon.trim().takeIf(::isHttpUrl)?.let {
                candidates += Candidate(it, priority = 420)
            }

            homepage?.let { base ->
                resolveUrl(base, "/favicon.ico")?.let {
                    candidates += Candidate(it, priority = 100)
                }
            }

            candidates
                .sortedWith(
                    compareByDescending<Candidate> { it.priority }
                        .thenByDescending { it.declaredSize },
                ).distinctBy { it.url }
                .take(8)
                .firstOrNull { isUsableImage(it.url) }
                ?.url
        }

    private fun extractCandidates(html: String, baseUrl: String): List<Candidate> {
        val candidates = mutableListOf<Candidate>()
        val tagRegex = Regex("""<(meta|link)\b[^>]*>""", RegexOption.IGNORE_CASE)
        val attributeRegex =
            Regex(
                """([A-Za-z_:][A-Za-z0-9_:\-]*)\s*=\s*(['\"])(.*?)\2""",
                setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
            )

        tagRegex.findAll(html).forEach { match ->
            val tag = match.groupValues[1].lowercase()
            val attributes =
                attributeRegex
                    .findAll(match.value)
                    .associate { it.groupValues[1].lowercase() to it.groupValues[3].trim() }

            when (tag) {
                "link" -> {
                    val rel = attributes["rel"].orEmpty().lowercase()
                    val href = attributes["href"]?.takeIf { it.isNotBlank() } ?: return@forEach
                    val resolved = resolveUrl(baseUrl, href) ?: return@forEach
                    val size = parseDeclaredSize(attributes["sizes"])
                    when {
                        "apple-touch-icon" in rel -> candidates += Candidate(resolved, 600, size)
                        "icon" in rel && size >= 128 -> candidates += Candidate(resolved, 540, size)
                        "icon" in rel -> candidates += Candidate(resolved, 360, size)
                    }
                }

                "meta" -> {
                    val key =
                        (attributes["property"] ?: attributes["name"])
                            ?.lowercase()
                            .orEmpty()
                    val content = attributes["content"]?.takeIf { it.isNotBlank() } ?: return@forEach
                    val resolved = resolveUrl(baseUrl, content) ?: return@forEach
                    when (key) {
                        "og:image", "og:image:url" -> candidates += Candidate(resolved, 320)
                        "twitter:image", "twitter:image:src" -> candidates += Candidate(resolved, 300)
                    }
                }
            }
        }
        return candidates
    }

    private fun parseDeclaredSize(value: String?): Int =
        value
            ?.split(Regex("\\s+"))
            ?.mapNotNull { size ->
                val parts = size.lowercase().split('x')
                if (parts.size != 2) null else minOf(parts[0].toIntOrNull() ?: 0, parts[1].toIntOrNull() ?: 0)
            }?.maxOrNull()
            ?: 0

    private fun resolveUrl(baseUrl: String, candidate: String): String? =
        runCatching { URI(baseUrl).resolve(candidate.trim()).toString() }
            .getOrNull()
            ?.takeIf(::isHttpUrl)

    private fun isHttpUrl(value: String): Boolean =
        value.startsWith("https://", ignoreCase = true) || value.startsWith("http://", ignoreCase = true)

    private fun readHtml(url: String): String? {
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
            output.toString(charset.name())
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun isUsableImage(url: String): Boolean {
        val connection = open(url, "image/avif,image/webp,image/svg+xml,image/*,*/*;q=0.8") ?: return false
        return try {
            val code = connection.responseCode
            if (code !in 200..299) return false
            val contentType = connection.contentType.orEmpty().lowercase()
            val path = connection.url.path.orEmpty().lowercase()
            val typeLooksLikeImage = contentType.startsWith("image/")
            val pathLooksLikeImage =
                listOf(".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".avif")
                    .any(path::endsWith)
            if (!typeLooksLikeImage && !pathLooksLikeImage) return false
            connection.inputStream.use { it.read() >= 0 }
        } catch (_: Exception) {
            false
        } finally {
            connection.disconnect()
        }
    }

    private fun open(url: String, accept: String): HttpURLConnection? =
        runCatching {
            (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = 6_000
                readTimeout = 7_000
                instanceFollowRedirects = true
                setRequestProperty("User-Agent", USER_AGENT)
                setRequestProperty("Accept", accept)
                setRequestProperty("Cache-Control", "no-cache")
            }
        }.getOrNull()
}
