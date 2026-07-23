from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
build_path = Path("app/build.gradle.kts")
build = build_path.read_text(encoding="utf-8")
build = replace_once(build, "versionCode = 153", "versionCode = 154", "versionCode")
build = replace_once(build, 'versionName = "13.6.4"', 'versionName = "13.6.5"', "versionName")
build_path.write_text(build, encoding="utf-8")


# ---------------------------------------------------------------------------
# Sender logo discovery: Radio Browser favicon first, then homepage icons.
# Inspired by Transistor's local-first station artwork approach, implemented
# independently for Metrolist's existing RadioStation model.
# ---------------------------------------------------------------------------
logo_resolver_path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt")
logo_resolver_path.write_text(
    r'''/**
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
''',
    encoding="utf-8",
)


# ---------------------------------------------------------------------------
# WebRadio UI: resolve and persist logos for saved and visible search stations.
# ---------------------------------------------------------------------------
radio_screen_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt")
radio_screen = radio_screen_path.read_text(encoding="utf-8")
radio_screen = replace_once(
    radio_screen,
    "import androidx.compose.foundation.combinedClickable\n",
    "import androidx.compose.foundation.background\nimport androidx.compose.foundation.combinedClickable\n",
    "WebRadio background import",
)
radio_screen = replace_once(
    radio_screen,
    "import androidx.compose.runtime.Composable\n",
    "import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.LaunchedEffect\n",
    "WebRadio LaunchedEffect import",
)
radio_screen = replace_once(
    radio_screen,
    "import com.metrolist.music.radio.RadioStation\n",
    "import com.metrolist.music.radio.RadioStation\nimport com.metrolist.music.radio.RadioStationLogoResolver\n",
    "WebRadio logo resolver import",
)
radio_screen = replace_once(
    radio_screen,
    "    var showAddDialog by remember { mutableStateOf(false) }\n\n",
    '''    var showAddDialog by remember { mutableStateOf(false) }

    // Resolve missing or broken artwork in the background as soon as the saved
    // station library is visible. The resolved URL is persisted, so later starts
    // do not have to rediscover the logo.
    LaunchedEffect(savedStations.map { Triple(it.uuid, it.favicon, it.homepage) }) {
        savedStations.forEach { station ->
            RadioStationLogoResolver.resolve(station)?.let { logo ->
                if (logo != station.favicon) {
                    store.addOrUpdate(station.copy(favicon = logo))
                }
            }
        }
    }

''',
    "WebRadio saved logo prefetch",
)
radio_screen = replace_once(
    radio_screen,
    '''                                onMoveDown = { store.move(station.uuid, 1) },
                            )
''',
    '''                                onMoveDown = { store.move(station.uuid, 1) },
                                onLogoResolved = store::addOrUpdate,
                            )
''',
    "saved station logo callback",
)
radio_screen = replace_once(
    radio_screen,
    '''                                    onSave = {
                                        store.addOrUpdate(station)
                                    },
                                )
''',
    '''                                    onSave = {
                                        store.addOrUpdate(station)
                                    },
                                    onLogoResolved = { enriched ->
                                        results = results.map { current ->
                                            if (current.uuid == enriched.uuid) enriched else current
                                        }
                                        if (savedStations.any { it.uuid == enriched.uuid }) {
                                            store.addOrUpdate(enriched)
                                        }
                                    },
                                )
''',
    "search station logo callback",
)
radio_screen = replace_once(
    radio_screen,
    '''    onMoveDown: (() -> Unit)? = null,
) {
    Row(
''',
    '''    onMoveDown: (() -> Unit)? = null,
    onLogoResolved: (RadioStation) -> Unit = {},
) {
    var artworkUrl by remember(station.uuid, station.favicon) { mutableStateOf(station.favicon) }

    LaunchedEffect(station.uuid, station.favicon, station.homepage) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->
            artworkUrl = resolved
            if (resolved != station.favicon) {
                onLogoResolved(station.copy(favicon = resolved))
            }
        }
    }

    Row(
''',
    "RadioStationRow signature",
)
radio_screen = replace_once(
    radio_screen,
    '''        if (station.favicon.isNotBlank()) {
            AsyncImage(
                model = station.favicon,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(54.dp).clip(RoundedCornerShape(10.dp)),
            )
        } else {
            Box(
                Modifier.size(54.dp).clip(RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(R.drawable.radio), contentDescription = null)
            }
        }
''',
    '''        if (artworkUrl.isNotBlank()) {
            AsyncImage(
                model = artworkUrl,
                contentDescription = "Senderlogo ${station.name}",
                contentScale = ContentScale.Crop,
                error = painterResource(R.drawable.radio),
                fallback = painterResource(R.drawable.radio),
                modifier = Modifier.size(54.dp).clip(RoundedCornerShape(10.dp)),
            )
        } else {
            val initials =
                remember(station.name) {
                    station.name
                        .trim()
                        .split(' ')
                        .filter { it.isNotBlank() }
                        .take(2)
                        .joinToString("") { it.first().uppercaseChar().toString() }
                        .ifBlank { "R" }
                }
            Box(
                Modifier
                    .size(54.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center,
            ) {
                Text(initials, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
        }
''',
    "RadioStation artwork rendering",
)
radio_screen_path.write_text(radio_screen, encoding="utf-8")


# ---------------------------------------------------------------------------
# Radio cache isolation and reliable queue replacement.
# ---------------------------------------------------------------------------
service_path = Path("app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt")
service = service_path.read_text(encoding="utf-8")
service = replace_once(
    service,
    "import androidx.media3.datasource.DataSource\n",
    "import androidx.media3.datasource.DataSource\nimport androidx.media3.datasource.DataSpec\n",
    "DataSpec import",
)
service = replace_once(
    service,
    "    fun playQueue(\n        queue: Queue,\n",
    '''    private fun resetForExplicitQueueReplacement(items: List<MediaItem>) {
        val currentWasRadio = isRadioMediaId(player.currentMediaItem?.mediaId)
        val nextContainsRadio = items.any { isRadioMediaId(it.mediaId) }

        // A manual queue change must cancel every pending operation associated
        // with the previous stream. This is especially important when crossing
        // the YouTube/live-radio boundary or replacing one live stream by another.
        crossfadeTriggerJob?.cancel()
        crossfadeTriggerJob = null
        crossfadeJob?.cancel()
        crossfadeJob = null

        secondaryPlayer?.let { secondary ->
            secondary.removeListener(secondaryPlayerListener)
            playerNormalizationProcessors.remove(secondary)
            runCatching { secondary.stop() }
            runCatching { secondary.clearMediaItems() }
            runCatching { secondary.release() }
        }
        secondaryPlayer = null
        if (fadingPlayer != null || isCrossfading) {
            cleanupCrossfade()
        }

        retryJob?.cancel()
        retryJob = null
        waitingForNetworkConnection.value = false
        pausedDueToNetworkError = false
        retryCount = 0
        consecutivePlaybackErr = 0

        items.forEach { item ->
            currentMediaIdRetryCount.remove(item.mediaId)
            recentlyFailedSongs.remove(item.mediaId)
            if (isRadioMediaId(item.mediaId)) {
                songUrlCache.remove(item.mediaId)
                // Remove cache fragments created by older builds. Live streams
                // are endless and must never be reused from the normal song cache.
                runCatching { playerCache.removeResource(item.mediaId) }
            }
        }

        if (nextContainsRadio) {
            currentStreamClient.value = null
        }

        if (currentWasRadio || nextContainsRadio || player.playerError != null) {
            player.stop()
        }
    }

    fun playQueue(
        queue: Queue,
''',
    "queue reset helper",
)
service = replace_once(
    service,
    '''            if (initialStatus.items.isEmpty()) return@launch
            // Track original queue size for shuffle playlist first feature
''',
    '''            if (initialStatus.items.isEmpty()) return@launch
            resetForExplicitQueueReplacement(initialStatus.items)
            // Track original queue size for shuffle playlist first feature
''',
    "queue reset invocation",
)
service = replace_once(
    service,
    '''            if (isRadioMediaId(mediaId)) {
                return@Factory dataSpec.withRequestHeaders(
                    dataSpec.httpRequestHeaders +
                        mapOf(
                            "Icy-MetaData" to "1",
                            "User-Agent" to "MetrolistHU/13.6.2",
                        ),
                )
            }
''',
    '''            if (isRadioMediaId(mediaId)) {
                // Keep the mediaId only long enough to identify this as radio.
                // The upstream DataSpec deliberately has no cache key and carries
                // FLAG_DONT_CACHE_IF_LENGTH_UNKNOWN, preventing an endless live
                // stream from poisoning the finite-song cache after the first play.
                return@Factory dataSpec
                    .withRequestHeaders(
                        dataSpec.httpRequestHeaders +
                            mapOf(
                                "Icy-MetaData" to "1",
                                "User-Agent" to "MetrolistHU/13.6.5",
                                "Cache-Control" to "no-cache",
                            ),
                    ).buildUpon()
                    .setKey(null)
                    .setFlags(dataSpec.flags or DataSpec.FLAG_DONT_CACHE_IF_LENGTH_UNKNOWN)
                    .build()
            }
''',
    "radio DataSpec cache isolation",
)
service_path.write_text(service, encoding="utf-8")


# ---------------------------------------------------------------------------
# Strict artist/title recognition and high-resolution cover matching.
# ---------------------------------------------------------------------------
connection_path = Path("app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt")
connection = connection_path.read_text(encoding="utf-8")
connection = replace_once(
    connection,
    "import com.metrolist.music.utils.reportException\n",
    "import com.metrolist.music.utils.reportException\nimport com.metrolist.music.ui.utils.resize\n",
    "resize import",
)
connection = replace_once(
    connection,
    '''        parsed.first?.takeIf { it.isNotBlank() }?.let { artist ->
            lookupRadioCover(base, artist, parsed.second)
        }
''',
    '''        val artist = parsed.first
        if (isClearRadioTrackMetadata(artist, parsed.second, stationName)) {
            lookupRadioCover(base, artist!!, parsed.second)
        } else {
            Timber.tag(TAG).d("Skipping radio cover lookup for ambiguous metadata: %s", rawTitle)
        }
''',
    "strict cover lookup invocation",
)
old_lookup = '''    private fun lookupRadioCover(
        base: com.metrolist.music.models.MediaMetadata,
        artist: String,
        title: String,
    ) {
        val key = "$artist|$title".lowercase()
        if (radioCoverCache.containsKey(key)) {
            radioCoverCache[key]?.let { url ->
                val current = mediaMetadata.value
                if (current?.id == base.id && current.title == title) {
                    mediaMetadata.value = current.copy(thumbnailUrl = url)
                }
            }
            return
        }

        radioCoverLookupJob?.cancel()
        radioCoverLookupJob =
            scope.launch {
                val cover =
                    runCatching {
                        YouTube.search("$artist $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull()
                            ?.thumbnail
                    }.getOrNull()
                radioCoverCache[key] = cover
                val current = mediaMetadata.value
                if (!cover.isNullOrBlank() && current?.id == base.id && current.title == title) {
                    mediaMetadata.value = current.copy(thumbnailUrl = cover)
                }
            }
    }
'''
new_lookup = '''    private fun isClearRadioTrackMetadata(
        artist: String?,
        title: String,
        stationName: String,
    ): Boolean {
        if (artist.isNullOrBlank() || title.isBlank()) return false
        val normalizedArtist = normalizeTrackText(artist)
        val normalizedTitle = normalizeTrackText(title)
        val normalizedStation = normalizeTrackText(stationName)
        if (normalizedArtist.length < 2 || normalizedTitle.length < 2) return false
        if (normalizedArtist == normalizedStation || normalizedTitle == normalizedStation) return false
        if ("http" in normalizedArtist || "http" in normalizedTitle || "www" in normalizedArtist || "www" in normalizedTitle) return false

        val generic =
            setOf(
                "radio",
                "webradio",
                "live",
                "stream",
                "unknown",
                "unbekannt",
                "station identification",
                "jingle",
                "promo",
                "advertisement",
                "commercial",
                "werbung",
                "news",
                "nachrichten",
            )
        return normalizedArtist !in generic && normalizedTitle !in generic
    }

    private fun normalizeTrackText(value: String): String =
        value
            .lowercase()
            .replace(
                Regex("""[\\(\\[][^(\\[]*(official|music video|video|audio|lyrics?|remaster(?:ed)?|live)[^\\)\\]]*[\\)\\]]"""),
                " ",
            ).replace(Regex("""\\b(feat|ft)\\.?\\b.*"""), " ")
            .replace(Regex("""[^\\p{L}\\p{N}]+"""), " ")
            .trim()
            .replace(Regex("""\\s+"""), " ")

    private fun tokenCoverage(expected: String, actual: String): Double {
        if (expected.isBlank() || actual.isBlank()) return 0.0
        if (actual.contains(expected) || expected.contains(actual)) return 1.0
        val expectedTokens = expected.split(' ').filter { it.length > 1 }.toSet()
        val actualTokens = actual.split(' ').filter { it.length > 1 }.toSet()
        if (expectedTokens.isEmpty()) return 0.0
        return expectedTokens.intersect(actualTokens).size.toDouble() / expectedTokens.size
    }

    private fun isStrongRadioCoverMatch(
        song: SongItem,
        artist: String,
        title: String,
    ): Boolean {
        val expectedTitle = normalizeTrackText(title)
        val actualTitle = normalizeTrackText(song.title)
        val expectedArtist = normalizeTrackText(artist)
        val actualArtist = normalizeTrackText(song.artists.joinToString(" ") { it.name })
        return tokenCoverage(expectedTitle, actualTitle) >= 0.80 &&
            tokenCoverage(expectedArtist, actualArtist) >= 0.70
    }

    private fun lookupRadioCover(
        base: com.metrolist.music.models.MediaMetadata,
        artist: String,
        title: String,
    ) {
        val key = "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        if (radioCoverCache.containsKey(key)) {
            radioCoverCache[key]?.let { url ->
                val current = mediaMetadata.value
                if (current?.id == base.id && current.title == title) {
                    mediaMetadata.value = current.copy(thumbnailUrl = url)
                }
            }
            return
        }

        radioCoverLookupJob?.cancel()
        radioCoverLookupJob =
            scope.launch {
                val cover =
                    runCatching {
                        YouTube.search("$artist - $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { candidate -> isStrongRadioCoverMatch(candidate, artist, title) }
                            ?.thumbnail
                            ?.resize(1200, 1200)
                    }.getOrNull()
                radioCoverCache[key] = cover
                val current = mediaMetadata.value
                if (!cover.isNullOrBlank() && current?.id == base.id && current.title == title) {
                    Timber.tag(TAG).d(
                        "Applied high-resolution radio cover for %s - %s: %s",
                        artist,
                        title,
                        cover,
                    )
                    mediaMetadata.value = current.copy(thumbnailUrl = cover)
                } else if (cover.isNullOrBlank()) {
                    Timber.tag(TAG).d("No sufficiently matching radio cover for %s - %s", artist, title)
                }
            }
    }
'''
connection = replace_once(connection, old_lookup, new_lookup, "radio cover matching")
connection_path.write_text(connection, encoding="utf-8")


# ---------------------------------------------------------------------------
# Radio Browser client version.
# ---------------------------------------------------------------------------
client_path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt")
client = client_path.read_text(encoding="utf-8")
client = client.replace("MetrolistHU/13.6.4 (Android WebRadio)", "MetrolistHU/13.6.5 (Android WebRadio)")
client_path.write_text(client, encoding="utf-8")


# ---------------------------------------------------------------------------
# Deterministic three-station ICY server with homepage logo discovery.
# ---------------------------------------------------------------------------
server_path = Path("scripts/icy_test_server.py")
server = server_path.read_text(encoding="utf-8")
server = replace_once(server, 'server_version = "MetrolistRadioTest/1.0"', 'server_version = "MetrolistRadioTest/2.0"', "server version")
server = replace_once(
    server,
    '''        if self.path == "/logo2.png":
            self._bytes(200, LOGO_2, "image/png")
            return
''',
    '''        if self.path == "/logo2.png":
            self._bytes(200, LOGO_2, "image/png")
            return
        if self.path == "/logo3.png":
            self._bytes(200, self.server.logo3, "image/png")
            return
        if self.path == "/station3-home":
            self._bytes(
                200,
                b'<html><head><link rel="apple-touch-icon" sizes="512x512" href="/logo3.png"></head><body>Test Radio Three</body></html>',
                "text/html; charset=utf-8",
            )
            return
''',
    "server logo3 endpoints",
)
server = replace_once(
    server,
    '''        if self.path == "/station1":
            self._stream("Test Radio One", "Test Artist One - Test Track One", self.server.audio1)
            return
        if self.path == "/station2":
            self._stream("Test Radio Two", "Test Artist Two - Test Track Two", self.server.audio2)
            return
''',
    '''        if self.path == "/station1":
            self._stream("Test Radio One", "Rick Astley - Never Gonna Give You Up", self.server.audio1)
            return
        if self.path == "/station2":
            self._stream("Test Radio Two", "Test Artist Two - Test Track Two", self.server.audio2)
            return
        if self.path == "/station3":
            self._stream("Test Radio Three", "Station identification", self.server.audio3)
            return
''',
    "server station streams",
)
server = replace_once(
    server,
    '''    parser.add_argument("--audio2", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.audio1 = args.audio1.read_bytes()
    server.audio2 = args.audio2.read_bytes()
''',
    '''    parser.add_argument("--audio2", type=Path, required=True)
    parser.add_argument("--audio3", type=Path, required=True)
    parser.add_argument("--logo3", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.audio1 = args.audio1.read_bytes()
    server.audio2 = args.audio2.read_bytes()
    server.audio3 = args.audio3.read_bytes()
    server.logo3 = args.logo3.read_bytes()
''',
    "server arguments",
)
server_path.write_text(server, encoding="utf-8")


# ---------------------------------------------------------------------------
# Extended reliability smoke test.
# ---------------------------------------------------------------------------
old_test_path = Path("scripts/dudu7_webradio_smoke.sh")
test = old_test_path.read_text(encoding="utf-8")
test = replace_once(
    test,
    ''' {"uuid":"test-radio-one","name":"Test Radio One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"http://10.0.2.2:8000/logo1.png","country":"Austria","language":"German","tags":"Test,Rock","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-two","name":"Test Radio Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"http://10.0.2.2:8000/logo2.png","country":"Austria","language":"German","tags":"Test,Pop","codec":"MP3","bitrate":96}
''',
    ''' {"uuid":"test-radio-one","name":"Test Radio One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"http://10.0.2.2:8000/logo1.png","country":"Austria","language":"German","tags":"Test,Rock","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-two","name":"Test Radio Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"http://10.0.2.2:8000/logo2.png","country":"Austria","language":"German","tags":"Test,Pop","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-three","name":"Test Radio Three","streamUrl":"http://10.0.2.2:8000/station3","homepage":"http://10.0.2.2:8000/station3-home","favicon":"","country":"Austria","language":"German","tags":"Test,Indie","codec":"MP3","bitrate":96}
''',
    "three radio seeds",
)
insert_after = '''assert_absent_right() {
    local label="$1"; shift
    if find_coords 1 "$@" >/dev/null; then
        echo "FAIL: $label unexpectedly visible" >&2
        return 1
    fi
    echo "PASS: $label absent"
}
'''
if insert_after not in test:
    raise SystemExit("Missing assert_absent_right helper")
test = test.replace(
    insert_after,
    insert_after + '''
assert_absent_anywhere() {
    local label="$1"; shift
    if find_coords 0 "$@" >/dev/null; then
        echo "FAIL: $label unexpectedly visible" >&2
        capture "unexpected-$label"
        return 1
    fi
    echo "PASS: $label absent"
}
''',
    1,
)
start_marker = "# Open embedded WebRadio and verify the right-pane library.\n"
end_marker = "# Verify URL/M3U editor exists.\n"
start = test.index(start_marker)
end = test.index(end_marker)
new_sequence = r'''# Open embedded WebRadio and verify three favorites plus homepage logo discovery.
tap_tab "WebRadio" "=WebRadio"
assert_text "saved radio section" 1 "=Gespeichert"
assert_text "first saved station" 1 "=Test Radio One"
assert_text "second saved station" 1 "=Test Radio Two"
assert_text "third saved station" 1 "=Test Radio Three"
sleep 10
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/radio-prefs-after-logo.xml"
grep -q 'logo3.png' "$RESULTS_DIR/radio-prefs-after-logo.xml"
echo "PASS: missing sender logo discovered from station homepage and persisted"
capture "webradio-three-favorites"

# Start favorite two, then replace it directly with favorite one.
tap_text "station two favorite" 1 "=Test Radio Two"
sleep 10
assert_text "favorite two title" 0 "Test Track Two"
assert_text "favorite two artist" 0 "Test Artist Two"
assert_text "favorite two live" 0 "LIVE"
assert_text "favorite two queue" 1 "=Test Radio Two"

tap_tab "WebRadio" "=WebRadio"
tap_text "station one favorite" 1 "=Test Radio One"
sleep 14
assert_text "favorite one title" 0 "=Never Gonna Give You Up"
assert_text "favorite one artist" 0 "=Rick Astley"
assert_text "favorite one live" 0 "LIVE"
adb logcat -d -v threadtime > "$RESULTS_DIR/cover-log.txt" 2>&1 || true
grep -E 'Applied high-resolution radio cover.*Rick Astley.*Never Gonna Give You Up.*1200' "$RESULTS_DIR/cover-log.txt"
echo "PASS: clear artist/title received a strongly matched 1200px cover"

# Start a third favorite with ambiguous metadata. It must play, but must not run cover search.
tap_tab "WebRadio" "=WebRadio"
tap_text "station three favorite" 1 "=Test Radio Three"
sleep 10
assert_text "favorite three ambiguous title" 0 "=Station identification"
assert_text "favorite three station artist" 0 "=Test Radio Three"
adb logcat -d -v threadtime > "$RESULTS_DIR/ambiguous-cover-log.txt" 2>&1 || true
grep -q 'Skipping radio cover lookup for ambiguous metadata: Station identification' "$RESULTS_DIR/ambiguous-cover-log.txt"
echo "PASS: ambiguous metadata skipped cover lookup"

# Exercise the rotated three-favorite queue in both directions.
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 10
assert_text "next from third reaches first" 0 "=Never Gonna Give You Up"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 10
assert_text "next reaches second" 0 "=Test Track Two"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous returns to first" 0 "=Never Gonna Give You Up"

# Switch radio -> YouTube. LIVE must disappear and normal song playback must be active.
echo "Switching from radio to YouTube"
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/radio-to-youtube.txt" || true
sleep 20
try_dialogs
assert_text "YouTube title after radio" 0 "=Never Gonna Give You Up"
assert_absent_anywhere "LIVE after switching to YouTube" "=LIVE"
capture "youtube-after-radio"

# Switch YouTube -> favorite two, then restart the same favorite again.
tap_tab "WebRadio" "=WebRadio"
tap_text "favorite two after YouTube" 1 "=Test Radio Two"
sleep 10
assert_text "radio after YouTube title" 0 "=Test Track Two"
assert_text "radio after YouTube live" 0 "=LIVE"

tap_tab "WebRadio" "=WebRadio"
tap_text "restart same favorite two" 1 "=Test Radio Two"
sleep 10
assert_text "same favorite restarts" 0 "=Test Track Two"
assert_text "same favorite remains live" 0 "=LIVE"

# Switch back to YouTube a second time, then start favorite one again.
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/radio-to-youtube-second.txt" || true
sleep 18
assert_text "second YouTube return" 0 "=Never Gonna Give You Up"
assert_absent_anywhere "LIVE after second YouTube return" "=LIVE"

tap_tab "WebRadio" "=WebRadio"
tap_text "favorite one final restart" 1 "=Test Radio One"
sleep 10
assert_text "final radio restart title" 0 "=Never Gonna Give You Up"
assert_text "final radio restart live" 0 "=LIVE"
capture "radio-final-restart"

'''
test = test[:start] + new_sequence + test[end:]
test = test.replace(
    'assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Track One" "Test Track Two"',
    'assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Radio Three" "Test Track Two" "Station identification"',
)
test = test.replace(
    '''- Saved stations visible in the right pane
- ICY artist/title metadata visible in the left player
- Previous/next switches the saved radio queue
''',
    '''- Three saved stations repeatedly started and replaced
- Radio -> YouTube -> Radio -> YouTube -> Radio transitions passed
- ICY artist/title metadata visible in the left player
- Previous/next switches the three-station saved queue
- Missing station logo discovered from homepage and persisted
- Ambiguous metadata skipped cover search
- Clear metadata received a strongly matched 1200px cover
''',
)
new_test_path = Path("scripts/dudu7_webradio_reliability_smoke.sh")
new_test_path.write_text(test, encoding="utf-8")


# Static safeguards.
checks = {
    build_path: ['versionCode = 154', 'versionName = "13.6.5"'],
    service_path: [
        'resetForExplicitQueueReplacement(initialStatus.items)',
        'DataSpec.FLAG_DONT_CACHE_IF_LENGTH_UNKNOWN',
        '.setKey(null)',
        'playerCache.removeResource(item.mediaId)',
    ],
    connection_path: [
        'isClearRadioTrackMetadata',
        'isStrongRadioCoverMatch',
        '.resize(1200, 1200)',
        'Applied high-resolution radio cover',
    ],
    radio_screen_path: [
        'RadioStationLogoResolver.resolve',
        'onLogoResolved',
        'Senderlogo ${station.name}',
    ],
    logo_resolver_path: [
        'apple-touch-icon',
        'og:image',
        'isUsableImage',
    ],
    new_test_path: [
        'radio -> YouTube',
        'restart same favorite two',
        'logo3.png',
    ],
}
for path, needles in checks.items():
    content = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in content:
            raise SystemExit(f"Missing {needle!r} in {path}")
