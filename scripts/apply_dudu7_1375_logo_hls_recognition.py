#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


# Version only; keep the complete 13.7.4 Dudu7 source baseline.
build_path = "app/build.gradle.kts"
build = read(build_path)
build = build.replace("versionCode = 163", "versionCode = 164", 1)
build = build.replace('versionName = "13.7.4"', 'versionName = "13.7.5"', 1)
write(build_path, build)


# Persist selected and automatically resolved station artwork inside the app.
logo_cache_path = "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoCache.kt"
write(
    logo_cache_path,
    r'''package com.metrolist.music.radio

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

/** Stores station logos locally so playback metadata and network changes cannot remove them. */
object RadioStationLogoCache {
    private const val MAX_LOGO_BYTES = 8 * 1024 * 1024
    private const val USER_AGENT = "MetrolistHU/13.7.5 (station logo cache)"

    suspend fun cache(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? =
        withContext(Dispatchers.IO) {
            val value = source.trim()
            if (value.isBlank()) return@withContext null
            val directory = File(context.applicationContext.filesDir, "radio_logos").apply { mkdirs() }
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

            var connection: HttpURLConnection? = null
            var input: InputStream? = null
            try {
                var contentType: String? = null
                input =
                    when (sourceUri?.scheme?.lowercase(Locale.ROOT)) {
                        "content" -> {
                            contentType = context.contentResolver.getType(sourceUri)
                            context.contentResolver.openInputStream(sourceUri)
                        }
                        "file" -> existingFile?.let(::FileInputStream)
                        "http", "https" -> {
                            connection =
                                (URL(value).openConnection() as HttpURLConnection).apply {
                                    connectTimeout = 8_000
                                    readTimeout = 10_000
                                    instanceFollowRedirects = true
                                    setRequestProperty("User-Agent", USER_AGENT)
                                    setRequestProperty("Accept", "image/avif,image/webp,image/*,*/*;q=0.7")
                                }
                            if (connection!!.responseCode !in 200..299) return@withContext null
                            contentType = connection!!.contentType
                            connection!!.inputStream
                        }
                        else -> null
                    }
                val sourceInput = input ?: return@withContext null
                val extension = extensionFor(value, contentType)
                if (extension == "svg") return@withContext null
                val safeUuid = stationUuid.replace(Regex("[^A-Za-z0-9._-]"), "_")
                val target = File(directory, "$safeUuid.$extension")
                val temporary = File(directory, "$safeUuid.$extension.tmp")
                directory.listFiles()?.filter { it.name.startsWith("$safeUuid.") && it != temporary }?.forEach(File::delete)

                sourceInput.use { sourceStream ->
                    temporary.outputStream().use { output ->
                        val buffer = ByteArray(16 * 1024)
                        var total = 0
                        while (true) {
                            val count = sourceStream.read(buffer)
                            if (count <= 0) break
                            total += count
                            if (total > MAX_LOGO_BYTES) {
                                temporary.delete()
                                return@withContext null
                            }
                            output.write(buffer, 0, count)
                        }
                        if (total == 0) {
                            temporary.delete()
                            return@withContext null
                        }
                    }
                }
                if (!temporary.renameTo(target)) {
                    temporary.copyTo(target, overwrite = true)
                    temporary.delete()
                }
                Uri.fromFile(target).toString()
            } catch (_: Exception) {
                null
            } finally {
                runCatching { input?.close() }
                connection?.disconnect()
            }
        }

    fun isLocal(value: String): Boolean {
        val scheme = runCatching { Uri.parse(value.trim()).scheme }.getOrNull()
        return scheme.equals("file", ignoreCase = true) || scheme.equals("content", ignoreCase = true)
    }

    private fun extensionFor(source: String, contentType: String?): String {
        val mime = contentType.orEmpty().substringBefore(';').lowercase(Locale.ROOT)
        return when {
            "png" in mime -> "png"
            "jpeg" in mime || "jpg" in mime -> "jpg"
            "webp" in mime -> "webp"
            "gif" in mime -> "gif"
            "avif" in mime -> "avif"
            "svg" in mime -> "svg"
            else -> {
                val extension =
                    runCatching { Uri.parse(source).lastPathSegment.orEmpty().substringAfterLast('.', "") }
                        .getOrDefault("")
                        .substringBefore('?')
                        .lowercase(Locale.ROOT)
                extension.takeIf { it in setOf("png", "jpg", "jpeg", "webp", "gif", "avif", "svg") }
                    ?.replace("jpeg", "jpg")
                    ?: "png"
            }
        }
    }
}
''',
)


# Keep local logos stable and update the resolver user agent.
resolver_path = "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt"
resolver = read(resolver_path)
resolver = resolver.replace('private const val USER_AGENT = "MetrolistHU/13.7.1 (Android WebRadio)"', 'private const val USER_AGENT = "MetrolistHU/13.7.5 (Android WebRadio)"', 1)
resolver_marker = '''        withContext(Dispatchers.IO) {
            if (station.manualFavicon) return@withContext station.favicon.trim().takeIf(::isHttpUrl)
            val candidates = mutableListOf<Candidate>()
'''
resolver_replacement = '''        withContext(Dispatchers.IO) {
            val configuredArtwork = station.favicon.trim()
            if (RadioStationLogoCache.isLocal(configuredArtwork)) return@withContext configuredArtwork
            if (station.manualFavicon) return@withContext configuredArtwork.takeIf(::isHttpUrl)
            val candidates = mutableListOf<Candidate>()
'''
if resolver_marker not in resolver and "val configuredArtwork = station.favicon.trim()" not in resolver:
    raise SystemExit("RadioStationLogoResolver entry marker missing")
resolver = resolver.replace(resolver_marker, resolver_replacement, 1)
write(resolver_path, resolver)


# Make the existing logo editor reachable, add device selection and cache fixed logos.
web_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
web = read(web_path)
imports = {
    "import androidx.compose.foundation.ExperimentalFoundationApi\n": "import androidx.activity.compose.rememberLauncherForActivityResult\nimport androidx.activity.result.contract.ActivityResultContracts\nimport androidx.compose.foundation.ExperimentalFoundationApi\n",
    "import androidx.compose.foundation.layout.height\n": "import androidx.compose.foundation.layout.height\nimport androidx.compose.foundation.layout.heightIn\n",
    "import androidx.compose.foundation.lazy.rememberLazyListState\n": "import androidx.compose.foundation.lazy.rememberLazyListState\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n",
    "import com.metrolist.music.radio.RadioStationLogoResolver\n": "import com.metrolist.music.radio.RadioStationLogoCache\nimport com.metrolist.music.radio.RadioStationLogoResolver\n",
}
for marker, replacement in imports.items():
    if replacement.splitlines()[0] not in web:
        if marker not in web:
            raise SystemExit(f"WebRadio import marker missing: {marker.strip()}")
        web = web.replace(marker, replacement, 1)

# Cache every automatically resolved logo before it is persisted in station data.
artwork_old = '''    var artworkUrl by remember(station.uuid, station.favicon) { mutableStateOf(station.favicon) }
    LaunchedEffect(station.uuid, station.homepage) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->
            artworkUrl = resolved
            if (resolved != station.favicon) onLogoResolved(station.copy(favicon = resolved))
        }
    }
'''
artwork_new = '''    val context = LocalContext.current
    var artworkUrl by remember(station.uuid, station.favicon) { mutableStateOf(station.favicon) }
    LaunchedEffect(station.uuid, station.homepage, station.favicon, station.manualFavicon) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->
            val stable =
                if (RadioStationLogoCache.isLocal(resolved)) {
                    resolved
                } else {
                    RadioStationLogoCache.cache(context, station.uuid, resolved) ?: resolved
                }
            artworkUrl = stable
            if (stable != station.favicon) onLogoResolved(station.copy(favicon = stable))
        }
    }
'''
if artwork_old in web:
    web = web.replace(artwork_old, artwork_new, 1)
elif "RadioStationLogoCache.cache(context, station.uuid, resolved)" not in web:
    raise SystemExit("RadioStationArtwork marker missing")

editor_start = web.index("@Composable\nprivate fun RadioStationEditorDialog(")
editor_replacement = r'''@Composable
private fun RadioStationEditorDialog(
    initial: RadioStation?,
    onDismiss: () -> Unit,
    onSave: (RadioStation) -> Unit,
) {
    val context = LocalContext.current
    val stationUuid = remember(initial) { initial?.uuid ?: UUID.randomUUID().toString() }
    var name by remember(initial) { mutableStateOf(initial?.name.orEmpty()) }
    var streamUrl by remember(initial) { mutableStateOf(initial?.streamUrl.orEmpty()) }
    var favicon by remember(initial) { mutableStateOf(initial?.favicon.orEmpty()) }
    var manualFavicon by remember(initial) { mutableStateOf(initial?.manualFavicon == true) }
    var logoCandidates by remember(initial) { mutableStateOf<List<String>>(emptyList()) }
    var logoSearchLoading by remember(initial) { mutableStateOf(false) }
    var logoSaving by remember(initial) { mutableStateOf(false) }
    var logoSearchError by remember(initial) { mutableStateOf<String?>(null) }
    val scrollState = rememberScrollState()
    val scope = rememberCoroutineScope()

    fun selectFixedLogo(source: String) {
        if (source.isBlank() || logoSaving) return
        scope.launch {
            logoSaving = true
            logoSearchError = null
            val cached = RadioStationLogoCache.cache(context, stationUuid, source)
            if (cached != null) {
                favicon = cached
                manualFavicon = true
            } else {
                logoSearchError = "Logo konnte nicht lokal gespeichert werden"
            }
            logoSaving = false
        }
    }

    val imagePicker =
        rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            uri?.toString()?.let(::selectFixedLogo)
        }

    fun searchLogos() {
        if (name.isBlank() || logoSearchLoading) return
        scope.launch {
            logoSearchLoading = true
            logoSearchError = null
            RadioBrowserClient.search(name.trim())
                .onSuccess { stations ->
                    logoCandidates =
                        stations
                            .asSequence()
                            .map { it.favicon.trim() }
                            .filter { it.startsWith("https://") || it.startsWith("http://") }
                            .distinct()
                            .take(16)
                            .toList()
                    if (logoCandidates.isEmpty()) logoSearchError = "Keine passenden Logos gefunden"
                }.onFailure { logoSearchError = it.message ?: "Logosuche fehlgeschlagen" }
            logoSearchLoading = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "Radiosender hinzufügen" else "Radiosender bearbeiten") },
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .heightIn(max = 430.dp)
                        .verticalScroll(scrollState),
            ) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Sendername") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = streamUrl, onValueChange = { streamUrl = it }, label = { Text("Stream-, M3U- oder PLS-Adresse") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = favicon,
                    onValueChange = {
                        favicon = it
                        manualFavicon = it.isNotBlank()
                    },
                    label = { Text("Senderbild (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (favicon.isNotBlank()) {
                    AsyncImage(
                        model = favicon,
                        contentDescription = "Ausgewähltes Senderlogo",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.size(82.dp).clip(RoundedCornerShape(10.dp)),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedButton(onClick = ::searchLogos, enabled = name.isNotBlank() && !logoSearchLoading && !logoSaving) {
                        Text("Logos suchen")
                    }
                    OutlinedButton(onClick = { imagePicker.launch("image/*") }, enabled = !logoSaving) {
                        Text("Bild auswählen")
                    }
                    TextButton(
                        onClick = {
                            favicon = ""
                            manualFavicon = false
                            logoCandidates = emptyList()
                            logoSearchError = null
                        },
                    ) { Text("Automatisch") }
                    if (logoSearchLoading || logoSaving) CircularProgressIndicator(Modifier.size(24.dp))
                }
                if (logoCandidates.isNotEmpty()) {
                    Text("Logo auswählen", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(logoCandidates, key = { it }) { candidate ->
                            AsyncImage(
                                model = candidate,
                                contentDescription = "Logo auswählen",
                                contentScale = ContentScale.Fit,
                                modifier =
                                    Modifier
                                        .size(72.dp)
                                        .clip(RoundedCornerShape(10.dp))
                                        .clickable(enabled = !logoSaving) { selectFixedLogo(candidate) },
                            )
                        }
                    }
                }
                logoSearchError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (manualFavicon && favicon.isNotBlank()) {
                    Text("Dieses Logo ist lokal gespeichert und bleibt fest eingestellt.", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(
                enabled = name.isNotBlank() && streamUrl.isNotBlank() && !logoSaving,
                onClick = {
                    val saveDraft: (String, Boolean) -> Unit = { stableFavicon, stableManual ->
                        onSave(
                            (initial ?: RadioStation(stationUuid, name.trim(), streamUrl.trim()))
                                .copy(
                                    name = name.trim(),
                                    streamUrl = streamUrl.trim(),
                                    favicon = stableFavicon,
                                    manualFavicon = stableManual,
                                ),
                        )
                    }
                    if (manualFavicon && favicon.isNotBlank() && !RadioStationLogoCache.isLocal(favicon)) {
                        scope.launch {
                            logoSaving = true
                            val cached = RadioStationLogoCache.cache(context, stationUuid, favicon)
                            logoSaving = false
                            if (cached != null) {
                                saveDraft(cached, true)
                            } else {
                                logoSearchError = "Logo konnte nicht lokal gespeichert werden"
                            }
                        }
                    } else {
                        saveDraft(favicon.trim(), manualFavicon && favicon.isNotBlank())
                    }
                },
            ) { Text("Speichern") }
        },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
'''
web = web[:editor_start] + editor_replacement
write(web_path, web)


# HLS recognition uses a second, muted Media3 player and taps decoded PCM only.
hls_decoder_path = "app/src/main/kotlin/com/metrolist/music/recognition/HlsRecognitionDecoder.kt"
write(
    hls_decoder_path,
    r'''package com.metrolist.music.recognition

import android.content.Context
import android.media.AudioFormat
import androidx.annotation.OptIn
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.audio.AudioProcessor
import androidx.media3.common.util.UnstableApi
import androidx.media3.exoplayer.DefaultRenderersFactory
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.DefaultAudioSink
import androidx.media3.exoplayer.audio.TeeAudioProcessor
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

/** Decodes only the audio track of an HLS stream into PCM for fingerprinting. */
@OptIn(UnstableApi::class)
internal object HlsRecognitionDecoder {
    suspend fun decode(
        context: Context,
        streamUrl: String,
        durationMs: Long,
        timeoutMs: Long,
    ): DecodedAudio =
        withContext(Dispatchers.Main.immediate) {
            val capture = PcmCaptureSink(durationMs)
            val tee = TeeAudioProcessor(capture)
            val renderersFactory =
                object : DefaultRenderersFactory(context.applicationContext) {
                    override fun buildAudioSink(
                        context: Context,
                        enableFloatOutput: Boolean,
                        enableAudioOutputPlaybackParams: Boolean,
                    ): AudioSink =
                        DefaultAudioSink.Builder(context)
                            .setEnableFloatOutput(false)
                            .setAudioProcessors(arrayOf<AudioProcessor>(tee))
                            .build()
                }
            val player = ExoPlayer.Builder(context.applicationContext, renderersFactory).build()
            val listener =
                object : Player.Listener {
                    override fun onPlayerError(error: PlaybackException) {
                        capture.fail(error)
                    }
                }
            player.addListener(listener)
            player.volume = 0f
            player.setAudioAttributes(AudioAttributes.DEFAULT, false)
            player.trackSelectionParameters =
                player.trackSelectionParameters
                    .buildUpon()
                    .setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, true)
                    .build()
            player.setMediaItem(
                MediaItem.Builder()
                    .setUri(streamUrl)
                    .setMimeType(MimeTypes.APPLICATION_M3U8)
                    .build(),
            )
            player.prepare()
            player.playWhenReady = true
            try {
                withTimeout(timeoutMs) { capture.result.await() }
            } finally {
                player.removeListener(listener)
                player.stop()
                player.release()
            }
        }

    private class PcmCaptureSink(private val durationMs: Long) : TeeAudioProcessor.AudioBufferSink {
        val result = CompletableDeferred<DecodedAudio>()
        private val output = ByteArrayOutputStream()
        private var sampleRate = 0
        private var channelCount = 0
        private var encoding = C.ENCODING_INVALID

        @Synchronized
        override fun flush(sampleRateHz: Int, channelCount: Int, encoding: Int) {
            if (result.isCompleted) return
            this.sampleRate = sampleRateHz
            this.channelCount = channelCount
            this.encoding = encoding
            output.reset()
            if (encoding != C.ENCODING_PCM_16BIT) {
                fail(IllegalStateException("Unsupported HLS PCM format: $encoding"))
            }
        }

        @Synchronized
        override fun handleBuffer(buffer: ByteBuffer) {
            if (result.isCompleted || encoding != C.ENCODING_PCM_16BIT || sampleRate <= 0 || channelCount <= 0) return
            val copy = buffer.duplicate()
            val bytes = ByteArray(copy.remaining())
            copy.get(bytes)
            output.write(bytes)
            val required = (sampleRate.toLong() * channelCount * 2L * durationMs / 1000L).coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
            if (output.size() >= required) {
                result.complete(
                    DecodedAudio(
                        data = output.toByteArray().copyOf(required),
                        channelCount = channelCount,
                        sampleRate = sampleRate,
                        pcmEncoding = AudioFormat.ENCODING_PCM_16BIT,
                    ),
                )
            }
        }

        fun fail(error: Throwable) {
            result.completeExceptionally(error)
        }
    }
}
''',
)

recognition_path = "app/src/main/kotlin/com/metrolist/music/recognition/MusicRecognitionService.kt"
recognition = read(recognition_path)
recognition = recognition.replace(
    "    suspend fun recognizeStream(streamUrl: String): RecognitionStatus =\n        withContext(Dispatchers.IO) {",
    "    suspend fun recognizeStream(context: Context, streamUrl: String): RecognitionStatus =\n        withContext(Dispatchers.IO) {",
    1,
)
recognition = recognition.replace(
    "                val decoded = decodeRadioStream(streamUrl)\n",
    '''                val decoded =
                    if (streamUrl.isHlsStreamUrl()) {
                        HlsRecognitionDecoder.decode(
                            context = context.applicationContext,
                            streamUrl = streamUrl,
                            durationMs = RECORDING_DURATION_MS,
                            timeoutMs = STREAM_DECODE_TIMEOUT_MS,
                        )
                    } else {
                        decodeRadioStream(streamUrl)
                    }
''',
    1,
)
recognition = recognition.replace('"User-Agent" to "MetrolistHU/13.7.1 (direct recognition)",', '"User-Agent" to "MetrolistHU/13.7.5 (direct recognition)",', 1)
helper_marker = "    private fun decodeRadioStream(streamUrl: String): DecodedAudio {\n"
helper = '''    private fun String.isHlsStreamUrl(): Boolean {
        val normalized = substringBefore('#').substringBefore('?').lowercase()
        return normalized.endsWith(".m3u8") || normalized.contains("/playlist.m3u8") || normalized.contains("/manifest.m3u8")
    }

'''
if helper not in recognition:
    if helper_marker not in recognition:
        raise SystemExit("MusicRecognitionService decoder marker missing")
    recognition = recognition.replace(helper_marker, helper + helper_marker, 1)
write(recognition_path, recognition)


# Use the actual normalized playback URI for recognition, not the stored editor URL.
player_path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
player = read(player_path)
old_start = '''    fun startRadioRecognition() {
        val streamUrl = currentRadioStation?.streamUrl?.trim().orEmpty()
        if (streamUrl.isBlank()) {
            Toast.makeText(context, "Radiostream ist nicht verfügbar", Toast.LENGTH_SHORT).show()
            return
        }
        recognitionRequestedForRadio = true
        MusicRecognitionService.reset()
        scope.launch { MusicRecognitionService.recognizeStream(streamUrl) }
    }
'''
new_start = '''    fun startRadioRecognition() {
        val streamUrl =
            runCatching { playerConnection.player.currentMediaItem?.localConfiguration?.uri?.toString()?.trim() }
                .getOrNull()
                .takeUnless { it.isNullOrBlank() }
                ?: currentRadioStation?.streamUrl?.trim().orEmpty()
        if (streamUrl.isBlank()) {
            Toast.makeText(context, "Radiostream ist nicht verfügbar", Toast.LENGTH_SHORT).show()
            return
        }
        recognitionRequestedForRadio = true
        MusicRecognitionService.reset()
        scope.launch { MusicRecognitionService.recognizeStream(context.applicationContext, streamUrl) }
    }
'''
if old_start in player:
    player = player.replace(old_start, new_start, 1)
elif "recognizeStream(context.applicationContext, streamUrl)" not in player:
    raise SystemExit("Player radio recognition marker missing")
write(player_path, player)


# Always retain stored station artwork while ICY/HLS title metadata changes.
connection_path = "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt"
connection = read(connection_path)
helper_anchor = '''    private fun getPlayerOrNull(): ExoPlayer? =
        try {
            if (!playerReadinessFlow.value) return null
            service.player
        } catch (_: UninitializedPropertyAccessException) {
            null
        } catch (_: NullPointerException) {
            null
        }

'''
artwork_helper = '''    private fun withStoredRadioArtwork(
        metadata: com.metrolist.music.models.MediaMetadata?,
    ): com.metrolist.music.models.MediaMetadata? {
        if (metadata == null || !isRadioMediaId(metadata.id) || !metadata.thumbnailUrl.isNullOrBlank()) return metadata
        val storedArtwork =
            radioStationStore.stations.value
                .firstOrNull { it.mediaId == metadata.id }
                ?.favicon
                ?.takeIf { it.isNotBlank() }
        return if (storedArtwork == null) metadata else metadata.copy(thumbnailUrl = storedArtwork)
    }

'''
if artwork_helper not in connection:
    if helper_anchor not in connection:
        raise SystemExit("PlayerConnection helper anchor missing")
    connection = connection.replace(helper_anchor, helper_anchor + artwork_helper, 1)
connection = connection.replace(
    "    val mediaMetadata = MutableStateFlow(getPlayerOrNull()?.currentMetadata)",
    "    val mediaMetadata = MutableStateFlow(withStoredRadioArtwork(getPlayerOrNull()?.currentMetadata))",
    1,
)
connection = connection.replace("        mediaMetadata.value = mediaItem?.metadata\n", "        mediaMetadata.value = withStoredRadioArtwork(mediaItem?.metadata)\n", 1)
connection = connection.replace("        val base = currentItem.metadata ?: return\n", "        val base = withStoredRadioArtwork(currentItem.metadata) ?: return\n", 3)
collector_old = '''            radioStationStore.stations.collect {
                if (isRadioMediaId(getPlayerOrNull()?.currentMediaItem?.mediaId)) {
                    updateCanSkipPreviousAndNext()
                }
            }
'''
collector_new = '''            radioStationStore.stations.collect {
                if (isRadioMediaId(getPlayerOrNull()?.currentMediaItem?.mediaId)) {
                    val stableMetadata = withStoredRadioArtwork(mediaMetadata.value)
                    if (stableMetadata != mediaMetadata.value) mediaMetadata.value = stableMetadata
                    updateCanSkipPreviousAndNext()
                }
            }
'''
if collector_old in connection:
    connection = connection.replace(collector_old, collector_new, 1)
elif "val stableMetadata = withStoredRadioArtwork(mediaMetadata.value)" not in connection:
    raise SystemExit("PlayerConnection station collector marker missing")
write(connection_path, connection)


checks = {
    build_path: ["versionCode = 164", 'versionName = "13.7.5"'],
    logo_cache_path: ["object RadioStationLogoCache", 'File(context.applicationContext.filesDir, "radio_logos")'],
    web_path: [
        ".verticalScroll(scrollState)",
        'Text("Bild auswählen")',
        "rememberLauncherForActivityResult",
        "RadioStationLogoCache.cache(context, station.uuid, resolved)",
        "Dieses Logo ist lokal gespeichert und bleibt fest eingestellt.",
    ],
    resolver_path: ["RadioStationLogoCache.isLocal(configuredArtwork)", "MetrolistHU/13.7.5"],
    hls_decoder_path: [
        "TeeAudioProcessor",
        "setTrackTypeDisabled(C.TRACK_TYPE_VIDEO, true)",
        "player.volume = 0f",
        "MimeTypes.APPLICATION_M3U8",
    ],
    recognition_path: [
        "recognizeStream(context: Context, streamUrl: String)",
        "HlsRecognitionDecoder.decode",
        "decodeRadioStream(streamUrl)",
    ],
    player_path: ["currentMediaItem?.localConfiguration?.uri", "recognizeStream(context.applicationContext, streamUrl)"],
    connection_path: ["withStoredRadioArtwork", "val stableMetadata = withStoredRadioArtwork(mediaMetadata.value)"],
    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt": [
        "if (dataSpec.key == null)",
        'val mediaId = dataSpec.key ?: error("No media id")',
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt": [
        "rememberReorderableLazyListState",
        "VehicleTabOrderStore.persist",
        "VEHICLE_PHYSICAL_RADIO_ROUTE",
    ],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

print("Dudu7 13.7.5 logo, HLS recognition and artwork retention patch applied")
