from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker missing in {path}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/build.gradle.kts",
    '        versionCode = 166\n        versionName = "13.7.7"',
    '        versionCode = 167\n        versionName = "13.7.8"',
)
replace_once(
    "gradle/libs.versions.toml",
    'coil-network-okhttp = { module = "io.coil-kt.coil3:coil-network-okhttp", version.ref = "coil" }\n',
    'coil-network-okhttp = { module = "io.coil-kt.coil3:coil-network-okhttp", version.ref = "coil" }\ncoil-svg = { module = "io.coil-kt.coil3:coil-svg", version.ref = "coil" }\n',
)
replace_once(
    "app/build.gradle.kts",
    '    implementation(libs.coil)\n    implementation(libs.coil.network.okhttp)\n',
    '    implementation(libs.coil)\n    implementation(libs.coil.network.okhttp)\n    implementation(libs.coil.svg)\n',
)

logo_cache = r'''package com.metrolist.music.radio

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.RectF
import android.net.Uri
import coil3.imageLoader
import coil3.request.CachePolicy
import coil3.request.ImageRequest
import coil3.request.SuccessResult
import coil3.request.allowHardware
import coil3.request.diskCachePolicy
import coil3.request.memoryCachePolicy
import coil3.request.scale
import coil3.request.size
import coil3.size.Scale
import coil3.toBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.min

/**
 * Validates and normalises every selected station logo into one local 512 x 512
 * PNG. SVG, WebP, AVIF and normal raster images are decoded by Coil first, so a
 * URL is never persisted merely because its HTTP content type looked plausible.
 */
object RadioStationLogoCache {
    private const val TARGET_SIZE = 512
    private const val MIN_SOURCE_SIZE = 24

    suspend fun cache(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val value = source.trim()
            if (value.isBlank()) return@withContext null
            val directory = File(appContext.filesDir, "radio_logos").apply { mkdirs() }
            val sourceUri = runCatching { Uri.parse(value) }.getOrNull()
            val existingFile =
                sourceUri
                    ?.takeIf { it.scheme.equals("file", ignoreCase = true) }
                    ?.path
                    ?.let(::File)
                    ?.takeIf { it.isFile }
            if (existingFile != null && existingFile.parentFile?.canonicalFile == directory.canonicalFile) {
                return@withContext Uri.fromFile(existingFile).toString()
            }

            val request =
                ImageRequest
                    .Builder(appContext)
                    .data(value)
                    .size(TARGET_SIZE, TARGET_SIZE)
                    .scale(Scale.FIT)
                    .allowHardware(false)
                    .memoryCachePolicy(CachePolicy.DISABLED)
                    .diskCachePolicy(CachePolicy.DISABLED)
                    .build()
            val result = appContext.imageLoader.execute(request) as? SuccessResult ?: return@withContext null
            val decoded = runCatching { result.image.toBitmap() }.getOrNull() ?: return@withContext null
            if (decoded.width < MIN_SOURCE_SIZE || decoded.height < MIN_SOURCE_SIZE) return@withContext null

            val square = Bitmap.createBitmap(TARGET_SIZE, TARGET_SIZE, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(square)
            canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)
            val scale = min(TARGET_SIZE.toFloat() / decoded.width, TARGET_SIZE.toFloat() / decoded.height)
            val width = decoded.width * scale
            val height = decoded.height * scale
            val left = (TARGET_SIZE - width) / 2f
            val top = (TARGET_SIZE - height) / 2f
            canvas.drawBitmap(
                decoded,
                null,
                RectF(left, top, left + width, top + height),
                Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG),
            )

            val safeUuid = stationUuid.replace(Regex("[^A-Za-z0-9._-]"), "_")
            val target = File(directory, "$safeUuid.png")
            val temporary = File(directory, "$safeUuid.png.tmp")
            directory.listFiles()
                ?.filter { it.name.startsWith("$safeUuid.") && it != temporary && it != target }
                ?.forEach(File::delete)
            val written =
                runCatching {
                    temporary.outputStream().buffered().use { output ->
                        square.compress(Bitmap.CompressFormat.PNG, 100, output)
                    }
                }.getOrDefault(false)
            if (!written || temporary.length() <= 0L) {
                temporary.delete()
                return@withContext null
            }
            if (!temporary.renameTo(target)) {
                temporary.copyTo(target, overwrite = true)
                temporary.delete()
            }
            Uri.fromFile(target).toString()
        }

    fun isLocal(value: String): Boolean {
        val scheme = runCatching { Uri.parse(value.trim()).scheme }.getOrNull()
        return scheme.equals("file", ignoreCase = true) || scheme.equals("content", ignoreCase = true)
    }
}
'''
Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoCache.kt").write_text(logo_cache, encoding="utf-8")

logo_search = r'''package com.metrolist.music.radio

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
'''
Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoSearch.kt").write_text(logo_search, encoding="utf-8")

radio_dns = r'''package com.metrolist.music.radio

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
import kotlin.math.abs
import kotlin.math.roundToInt

/** RadioDNS Project Logo lookup for an FM bearer using RDS PI, frequency and GCC. */
object RadioDnsLogoResolver {
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
            val authoritative = dnsAnswers(lookup, 5).firstOrNull()?.trimEnd('.') ?: return@withContext emptyList()
            val srv = dnsAnswers("_radioepg._tcp.$authoritative", 33).mapNotNull(::parseSrv).minByOrNull { it.priority }
                ?: return@withContext emptyList()
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            serviceInformationUrls(srv).forEach { siUrl ->
                val xml = download(siUrl) ?: return@forEach
                val logos = parseServiceInformation(xml, siUrl, bearer)
                if (logos.isNotEmpty()) return@withContext logos.sortedByDescending { it.ranking }
            }
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
'''
Path("app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt").write_text(radio_dns, encoding="utf-8")

replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt",
    '''            // Coil in this build does not consistently decode SVG station favicons.\n            // Prefer a clean initials fallback over persisting a known-broken vector URL.\n            null\n''',
    '''            // SVG support is installed globally and the local logo cache rasterises\n            // vectors into the same square PNG format as all other station artwork.\n            vectorFallback\n''',
)

replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "import com.metrolist.music.radio.RadioBrowserClient\n",
    "import com.metrolist.music.radio.RadioBrowserClient\nimport com.metrolist.music.radio.RadioLogoCandidate\n",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "    var logoCandidates by remember(initial) { mutableStateOf<List<String>>(emptyList()) }\n",
    "    var logoCandidates by remember(initial) { mutableStateOf<List<RadioLogoCandidate>>(emptyList()) }\n",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    '''                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {\n                        items(logoCandidates, key = { it }) { candidate ->\n                            AsyncImage(\n                                model = candidate,\n                                contentDescription = "Logo auswählen",\n                                contentScale = ContentScale.Fit,\n                                modifier =\n                                    Modifier\n                                        .size(72.dp)\n                                        .clip(RoundedCornerShape(10.dp))\n                                        .clickable(enabled = !logoSaving) { selectFixedLogo(candidate) },\n                            )\n                        }\n                    }\n''',
    '''                    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {\n                        items(logoCandidates, key = { it.url }) { candidate ->\n                            Column(horizontalAlignment = Alignment.CenterHorizontally) {\n                                AsyncImage(\n                                    model = candidate.url,\n                                    contentDescription = "Logo auswählen: ${candidate.displayDetails}",\n                                    contentScale = ContentScale.Fit,\n                                    modifier =\n                                        Modifier\n                                            .size(82.dp)\n                                            .clip(RoundedCornerShape(10.dp))\n                                            .background(MaterialTheme.colorScheme.surfaceVariant)\n                                            .clickable(enabled = !logoSaving) { selectFixedLogo(candidate.url) },\n                                )\n                                Text(\n                                    candidate.displayDetails,\n                                    style = MaterialTheme.typography.labelSmall,\n                                    maxLines = 1,\n                                    overflow = TextOverflow.Ellipsis,\n                                )\n                            }\n                        }\n                    }\n''',
)

fm_artwork = r'''package com.metrolist.music.radio.fyt

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.metrolist.music.R
import com.metrolist.music.radio.RadioDnsLogoResolver
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationLogoCache
import com.metrolist.music.radio.RadioStationLogoResolver
import com.metrolist.music.radio.RadioStationLogoSearch
import com.metrolist.music.radio.RadioStationStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.roundToInt

/** Shared FM logo resolver: RadioDNS first, then fixed WebRadio artwork and multi-source search. */
object FmStationLogoResolver {
    private const val PREFS = "dudu7_fm_station_logos_v2"
    private const val CACHE_PREFIX = "logo_"
    private val unresolvedThisSession = ConcurrentHashMap.newKeySet<String>()

    fun cachedLogo(context: Context, stationName: String, frequency: Float, pi: Int = 0): String? =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(CACHE_PREFIX + cacheKey(stationName, frequency, pi), null)

    suspend fun resolve(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(stationName, frequency, pi)
            cachedLogo(appContext, stationName, frequency, pi)?.let { return@withContext it }
            if (!isUsefulStationName(stationName) || !unresolvedThisSession.add(key)) return@withContext null

            if (pi > 0) {
                RadioDnsLogoResolver.resolveFm(appContext, frequency, pi).forEach { candidate ->
                    cacheAndPersist(appContext, key, candidate.url)?.let { return@withContext it }
                }
            }

            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestMatch(stationName, localStations)
            val fixedLocal = localMatch?.let { station ->
                when {
                    station.manualFavicon && station.favicon.isNotBlank() -> station.favicon
                    else -> RadioStationLogoResolver.resolve(station) ?: station.favicon
                }
            }
            if (!fixedLocal.isNullOrBlank()) {
                cacheAndPersist(appContext, key, fixedLocal)?.let { return@withContext it }
            }

            RadioStationLogoSearch.search(stationName, localMatch).getOrDefault(emptyList()).forEach { candidate ->
                cacheAndPersist(appContext, key, candidate.url)?.let { return@withContext it }
            }
            null
        }

    fun invalidate(context: Context, stationName: String, frequency: Float, pi: Int = 0) {
        val key = cacheKey(stationName, frequency, pi)
        unresolvedThisSession.remove(key)
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(CACHE_PREFIX + key).apply()
    }

    private suspend fun cacheAndPersist(context: Context, key: String, source: String): String? {
        val stable = RadioStationLogoCache.cache(context, "fm_$key", source) ?: return null
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(CACHE_PREFIX + key, stable).apply()
        return stable
    }

    private fun bestMatch(requestedName: String, stations: List<RadioStation>): RadioStation? =
        stations.asSequence()
            .map { station -> station to matchScore(requestedName, station) }
            .filter { (_, score) -> score >= 70 }
            .maxByOrNull { (_, score) -> score }
            ?.first

    private fun matchScore(requestedName: String, station: RadioStation): Int {
        val requested = normalize(requestedName)
        val candidate = normalize(station.name)
        if (requested.isBlank() || candidate.isBlank()) return 0
        var score =
            when {
                requested == candidate -> 100
                candidate.startsWith(requested) || requested.startsWith(candidate) -> 92
                candidate.contains(requested) || requested.contains(candidate) -> 84
                else -> {
                    val left = requested.split(' ').filter { it.length >= 2 }.toSet()
                    val right = candidate.split(' ').filter { it.length >= 2 }.toSet()
                    if (left.isEmpty() || right.isEmpty()) 0 else left.intersect(right).size * 100 / maxOf(left.size, right.size)
                }
            }
        if (station.country.equals("Austria", true) || station.country.equals("Österreich", true)) score += 5
        if (station.manualFavicon) score += 4
        return score
    }

    private fun isUsefulStationName(value: String): Boolean {
        val normalized = normalize(value)
        if (normalized.isBlank() || normalized.matches(Regex("fm \\d{2,3} \\d"))) return false
        return normalized !in setOf("fm", "radio", "antennenempfang", "physischer antennenempfang")
    }

    private fun cacheKey(stationName: String, frequency: Float, pi: Int): String {
        val identity = if (pi > 0) "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}" else normalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace("&", " and ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}

@Composable
fun FmStationArtwork(
    stationName: String,
    frequency: Float,
    pi: Int = 0,
    size: Dp,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val artworkKey = remember(stationName, frequency, pi) { "${stationName.trim()}-${(frequency * 100f).roundToInt()}-$pi" }
    var artworkUrl by remember(artworkKey) { mutableStateOf(FmStationLogoResolver.cachedLogo(context, stationName, frequency, pi)) }
    LaunchedEffect(artworkKey) {
        if (artworkUrl.isNullOrBlank()) artworkUrl = FmStationLogoResolver.resolve(context, stationName, frequency, pi)
    }
    val shape = RoundedCornerShape((size.value / 7f).dp)
    if (!artworkUrl.isNullOrBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo $stationName",
            contentScale = ContentScale.Fit,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        )
    } else {
        Box(
            contentAlignment = Alignment.Center,
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size((size.value * 0.62f).dp),
            )
        }
    }
}
'''
Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmStationArtwork.kt").write_text(fm_artwork, encoding="utf-8")

replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '''    data class Preset(\n        val frequency: Float,\n        val name: String,\n    )\n''',
    '''    data class Preset(\n        val frequency: Float,\n        val name: String,\n        val pi: Int = 0,\n        val ecc: String = "",\n    )\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    "        val additions = results.map { Preset(it.frequency, it.name) }\n",
    "        val additions = results.map { Preset(it.frequency, it.name, it.pi) }\n",
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '        val preset = Preset(snapshot.frequency, snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" })\n',
    '        val preset = Preset(snapshot.frequency, snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" }, snapshot.pi)\n',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '''                14 -> _state.update { it.copy(pi = value1) }\n''',
    '''                14 -> {\n                    _state.update { it.copy(pi = value1) }\n                    updateCurrentPresetIdentity()\n                }\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '''        _state.update { current ->\n            current.copy(\n                ps = ps.ifBlank { current.ps },\n                rt = rt.ifBlank { current.rt },\n                rssi = rssi,\n                stereo = stereo,\n            )\n        }\n''',
    '''        _state.update { current ->\n            current.copy(\n                ps = ps.ifBlank { current.ps },\n                rt = rt.ifBlank { current.rt },\n                rssi = rssi,\n                stereo = stereo,\n            )\n        }\n        updateCurrentPresetIdentity()\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '''    private fun persistPresets(presets: List<Preset>) {\n        val encoded =\n            presets.joinToString("\\n") { preset ->\n                "${preset.frequency}\\t${preset.name.replace('\\n', ' ').replace('\\t', ' ')}"\n            }\n''',
    '''    private fun updateCurrentPresetIdentity() {\n        val snapshot = _state.value\n        if (snapshot.pi <= 0) return\n        var changed = false\n        val updated =\n            snapshot.presets.map { preset ->\n                if (abs(preset.frequency - snapshot.frequency) >= 0.05f) {\n                    preset\n                } else {\n                    val updatedName = snapshot.ps.trim().takeIf { it.isNotBlank() } ?: preset.name\n                    val updatedPreset = preset.copy(name = updatedName, pi = snapshot.pi)\n                    if (updatedPreset != preset) changed = true\n                    updatedPreset\n                }\n            }\n        if (changed) {\n            persistPresets(updated)\n            _state.update { it.copy(presets = updated) }\n        }\n    }\n\n    private fun persistPresets(presets: List<Preset>) {\n        val encoded =\n            presets.joinToString("\\n") { preset ->\n                "${preset.frequency}\\t${preset.name.replace('\\n', ' ').replace('\\t', ' ')}\\t${preset.pi}\\t${preset.ecc}"\n            }\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    '''                val parts = line.split('\\t', limit = 2)\n                val frequency = parts.firstOrNull()?.toFloatOrNull() ?: return@mapNotNull null\n                Preset(normalizeFrequency(frequency), parts.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" })\n''',
    '''                val parts = line.split('\\t', limit = 4)\n                val frequency = parts.firstOrNull()?.toFloatOrNull() ?: return@mapNotNull null\n                Preset(\n                    frequency = normalizeFrequency(frequency),\n                    name = parts.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" },\n                    pi = parts.getOrNull(2)?.toIntOrNull() ?: 0,\n                    ecc = parts.getOrNull(3).orEmpty(),\n                )\n''',
)

replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
    '''                                    preset = preset,\n                                    isActive = isActive,\n''',
    '''                                    preset = preset,\n                                    pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    isActive = isActive,\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
    '''private fun FmFavouriteRow(\n    preset: FytPhysicalRadio.Preset,\n    isActive: Boolean,\n''',
    '''private fun FmFavouriteRow(\n    preset: FytPhysicalRadio.Preset,\n    pi: Int,\n    isActive: Boolean,\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
    '''            stationName = preset.name,\n            frequency = preset.frequency,\n            size = 56.dp,\n''',
    '''            stationName = preset.name,\n            frequency = preset.frequency,\n            pi = pi,\n            size = 56.dp,\n''',
)
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt",
    '''                    stationName = state.displayStation,\n                    frequency = state.frequency,\n                    size = artworkSize,\n''',
    '''                    stationName = state.displayStation,\n                    frequency = state.frequency,\n                    pi = state.pi,\n                    size = artworkSize,\n''',
)

print("Applied Dudu7 13.7.8 unified radio logos and RadioDNS support")
