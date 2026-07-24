#!/usr/bin/env python3
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:140]!r}")
    write(path, text.replace(old, new, 1))


def replace_nth(text: str, old: str, new: str, occurrence: int) -> str:
    start = -1
    for _ in range(occurrence):
        start = text.find(old, start + 1)
        if start < 0:
            raise SystemExit(f"Occurrence {occurrence} not found: {old[:120]!r}")
    return text[:start] + new + text[start + len(old):]


# Version and user agents.
replace_once(
    "app/build.gradle.kts",
    '        versionCode = 158\n        versionName = "13.6.9"',
    '        versionCode = 159\n        versionName = "13.7.0"',
)
for path in (
    "app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt",
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt",
):
    text = read(path).replace("MetrolistHU/13.6.9", "MetrolistHU/13.7.0")
    write(path, text)


# Fixed 50/50 split between player and right pane.
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
    "    val safePlayerWeight = Dudu7Layout.sanitizePlayerPaneWeight(playerPaneWeight)",
    "    val safePlayerWeight = 0.5f",
)


# Use the original Metrolist artist screen in the right pane, with its existing
# embedded sizing adaptations. This retains the original clickable section titles.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt",
    '''        if (embeddedInPlayer) {
            com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen(navController)
        } else {
            ArtistScreen(navController)
        }''',
    '''        ArtistScreen(
            navController = navController,
            embeddedInPlayer = embeddedInPlayer,
        )''',
)


# Radio favourites: darker list rows, tile drag handle at bottom-right and a
# grid/dot icon in tile mode while retaining the line handle in list mode.
radio_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
radio = read(radio_path)
radio = radio.replace(
    '.background(if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.48f) else MaterialTheme.colorScheme.surface)',
    '.background(if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.48f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f))',
    1,
)

drag_call = '''                                        RadioDragHandle(
                                            Modifier.draggableHandle(
                                                onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                            ),
                                        )'''
grid_drag_call = '''                                        RadioDragHandle(
                                            modifier =
                                                Modifier.draggableHandle(
                                                    onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                                ),
                                            icon = R.drawable.drag_indicator_grid,
                                        )'''
if grid_drag_call not in radio:
    radio = replace_nth(radio, drag_call, grid_drag_call, 2)

card_start = radio.index("@OptIn(ExperimentalFoundationApi::class)\n@Composable\nprivate fun RadioStationCard(")
card_end = radio.index("\n@Composable\nprivate fun RadioDragHandle", card_start)
new_card = '''@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun RadioStationCard(
    station: RadioStation,
    isSaved: Boolean,
    isActive: Boolean,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onSave: () -> Unit,
    onLongClick: () -> Unit,
    dragHandle: @Composable () -> Unit = {},
    onLogoResolved: (RadioStation) -> Unit = {},
) {
    Box(
        modifier =
            Modifier
                .fillMaxWidth()
                .aspectRatio(0.86f)
                .clip(RoundedCornerShape(14.dp))
                .background(
                    if (isActive) {
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f)
                    } else {
                        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
                    },
                ).combinedClickable(onClick = onPlay, onLongClick = onLongClick),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(start = 10.dp, top = 10.dp, end = 10.dp, bottom = if (isSaved) 42.dp else 10.dp),
        ) {
            Box(contentAlignment = Alignment.TopEnd) {
                RadioStationArtwork(station, 88, Modifier, onLogoResolved)
                if (!isSaved) {
                    IconButton(onClick = onSave, modifier = Modifier.align(Alignment.TopEnd).size(34.dp)) {
                        Icon(painterResource(R.drawable.add_circle), contentDescription = "Speichern")
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            Text(
                station.name,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (isActive) {
                Text(
                    if (isPlaying) "● LÄUFT" else "PAUSIERT",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
            } else {
                StationDetails(station, compact = true)
            }
        }
        if (isSaved) {
            Box(
                modifier =
                    Modifier
                        .align(Alignment.BottomEnd)
                        .padding(end = 2.dp, bottom = 2.dp),
            ) {
                dragHandle()
            }
        }
    }
}
'''
radio = radio[:card_start] + new_card + radio[card_end:]

drag_start = radio.index("@Composable\nprivate fun RadioDragHandle(")
drag_end = radio.index("\n@Composable\nprivate fun RadioStationArtwork", drag_start)
new_drag = '''@Composable
private fun RadioDragHandle(
    modifier: Modifier,
    icon: Int = R.drawable.drag_handle,
) {
    IconButton(
        onClick = {},
        modifier = modifier.size(42.dp),
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = "Sender verschieben",
        )
    }
}
'''
radio = radio[:drag_start] + new_drag + radio[drag_end:]
write(radio_path, radio)

write(
    "app/src/main/res/drawable/drag_indicator_grid.xml",
    '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FF000000"
        android:pathData="M6,3h4v4H6zM14,3h4v4h-4zM6,10h4v4H6zM14,10h4v4h-4zM6,17h4v4H6zM14,17h4v4h-4z" />
</vector>
''',
)


# A fresh shuffle order is generated every time shuffle is switched on. Switching
# it off still returns Media3 to the original timeline order.
connection_path = "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt"
connection = read(connection_path)
if "import androidx.media3.exoplayer.source.ShuffleOrder" not in connection:
    connection = connection.replace(
        "import androidx.media3.exoplayer.ExoPlayer\n",
        "import androidx.media3.exoplayer.ExoPlayer\nimport androidx.media3.exoplayer.source.ShuffleOrder\n",
        1,
    )
shuffle_method = '''
    fun toggleShuffle() {
        if (!allowInternalSync && shouldBlockPlaybackChanges?.invoke() == true) return
        val activePlayer = getPlayerOrNull() ?: return
        if (activePlayer.shuffleModeEnabled) {
            activePlayer.shuffleModeEnabled = false
        } else {
            if (activePlayer.mediaItemCount > 1) {
                activePlayer.setShuffleOrder(
                    ShuffleOrder.DefaultShuffleOrder(
                        activePlayer.mediaItemCount,
                        System.nanoTime(),
                    ),
                )
            }
            activePlayer.shuffleModeEnabled = true
        }
    }
'''
if "fun toggleShuffle()" not in connection:
    marker = "\n    /**\n     * Start playback - handles Cast when active\n"
    if marker not in connection:
        raise SystemExit("PlayerConnection shuffle insertion marker missing")
    connection = connection.replace(marker, shuffle_method + marker, 1)
write(connection_path, connection)


# Manual radio recognition now reads the current radio stream directly. The normal
# recognition screen keeps its microphone behaviour for non-radio use cases.
player_path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
player = read(player_path)
for import_line in (
    "import androidx.activity.compose.rememberLauncherForActivityResult\n",
    "import androidx.activity.result.contract.ActivityResultContracts\n",
    "import android.Manifest\n",
):
    player = player.replace(import_line, "", 1)

old_recognition = '''    val scope = rememberCoroutineScope()
    var recognitionRequestedForRadio by remember { mutableStateOf(false) }
    val recordPermissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                scope.launch { MusicRecognitionService.recognize(context) }
            } else {
                recognitionRequestedForRadio = false
                Toast.makeText(context, "Mikrofonzugriff ist für die Musikerkennung erforderlich", Toast.LENGTH_SHORT).show()
            }
        }
    val recognitionInProgress =
        recognitionRequestedForRadio &&
            (recognitionStatus is RecognitionStatus.Listening || recognitionStatus is RecognitionStatus.Processing)

    fun startRadioRecognition() {
        recognitionRequestedForRadio = true
        MusicRecognitionService.reset()
        if (MusicRecognitionService.hasRecordPermission(context)) {
            scope.launch { MusicRecognitionService.recognize(context) }
        } else {
            recordPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
    }
'''
new_recognition = '''    val scope = rememberCoroutineScope()
    var recognitionRequestedForRadio by remember { mutableStateOf(false) }
    val recognitionInProgress =
        recognitionRequestedForRadio &&
            (recognitionStatus is RecognitionStatus.Listening || recognitionStatus is RecognitionStatus.Processing)

    fun startRadioRecognition() {
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
if new_recognition not in player:
    if old_recognition not in player:
        raise SystemExit("Radio recognition UI marker missing")
    player = player.replace(old_recognition, new_recognition, 1)

old_shuffle = '''                                onToggleShuffle = {
                                    playerConnection.player.shuffleModeEnabled =
                                        !playerConnection.player.shuffleModeEnabled
                                },'''
new_shuffle = '''                                onToggleShuffle = playerConnection::toggleShuffle,'''
if new_shuffle not in player:
    if old_shuffle not in player:
        raise SystemExit("Dudu7 shuffle callback marker missing")
    player = player.replace(old_shuffle, new_shuffle, 1)
write(player_path, player)


# Stream decoder and shared fingerprint pipeline.
write(
    "app/src/main/kotlin/com/metrolist/music/recognition/MusicRecognitionService.kt",
    r'''/**
 * Music Recognition Feature
 *
 * This feature is based on the original MusicRecognizer project by Aleksey Saenko.
 * Original project: https://github.com/aleksey-saenko/MusicRecognizer
 */
package com.metrolist.music.recognition

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaRecorder
import android.os.SystemClock
import androidx.core.content.ContextCompat
import com.metrolist.shazamkit.Shazam
import com.metrolist.shazamkit.models.RecognitionStatus
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import timber.log.Timber
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Music recognition from either microphone PCM or a directly decoded radio stream.
 */
object MusicRecognitionService {
    private const val RECORDING_SAMPLE_RATE = 44100
    private const val CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_MONO
    private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
    private const val RECORDING_DURATION_MS = 12000L
    private const val STREAM_DECODE_TIMEOUT_MS = 30000L
    private const val TAG = "MusicRecognitionService"

    private val _recognitionStatus = MutableStateFlow<RecognitionStatus>(RecognitionStatus.Ready)
    val recognitionStatus: StateFlow<RecognitionStatus> = _recognitionStatus.asStateFlow()

    var resultSavedExternally: Boolean = false

    fun hasRecordPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED

    /** Microphone recognition retained for the normal recognition screen/widget. */
    @SuppressLint("MissingPermission")
    suspend fun recognize(context: Context): RecognitionStatus =
        withContext(Dispatchers.IO) {
            if (!hasRecordPermission(context)) {
                return@withContext setError("Microphone permission not granted")
            }
            _recognitionStatus.value = RecognitionStatus.Listening
            try {
                val audioData = recordAudio()
                recognizeDecodedAudio(
                    DecodedAudio(
                        data = audioData,
                        channelCount = 1,
                        sampleRate = RECORDING_SAMPLE_RATE,
                        pcmEncoding = AUDIO_FORMAT,
                    ),
                )
            } catch (error: Exception) {
                Timber.tag(TAG).e(error, "Microphone recognition failed")
                setError(error.message ?: "Recognition failed")
            }
        }

    /**
     * Recognize the currently selected WebRadio source without using the microphone.
     * A second connection to the same resolved stream URL is decoded for twelve seconds.
     */
    suspend fun recognizeStream(streamUrl: String): RecognitionStatus =
        withContext(Dispatchers.IO) {
            if (streamUrl.isBlank()) return@withContext setError("Radiostream is unavailable")
            _recognitionStatus.value = RecognitionStatus.Listening
            try {
                val decoded = decodeRadioStream(streamUrl)
                recognizeDecodedAudio(decoded)
            } catch (error: Exception) {
                Timber.tag(TAG).e(error, "Direct radio-stream recognition failed")
                setError(error.message ?: "Radiostream could not be decoded")
            }
        }

    private suspend fun recognizeDecodedAudio(source: DecodedAudio): RecognitionStatus {
        _recognitionStatus.value = RecognitionStatus.Processing
        val mono = downmixToMono(source)
        val resampled =
            AudioResampler.resample(mono, VibraSignature.REQUIRED_SAMPLE_RATE).getOrElse { error ->
                Timber.tag(TAG).e(error, "Audio resampling failed")
                return setError("Failed to resample audio: ${error.message}")
            }

        require(
            resampled.channelCount == 1 &&
                resampled.sampleRate == VibraSignature.REQUIRED_SAMPLE_RATE &&
                resampled.pcmEncoding == AudioFormat.ENCODING_PCM_16BIT &&
                ByteOrder.nativeOrder() == ByteOrder.LITTLE_ENDIAN &&
                resampled.data.isNotEmpty() &&
                resampled.data.size % 2 == 0,
        ) { "Invalid audio format for fingerprint generation" }

        val signature =
            try {
                VibraSignature.fromI16(resampled.data)
            } catch (error: Exception) {
                Timber.tag(TAG).e(error, "Fingerprint generation failed")
                return setError("Failed to generate fingerprint: ${error.message}")
            }
        val sampleDurationMs =
            (resampled.data.size / 2) * 1000L / VibraSignature.REQUIRED_SAMPLE_RATE

        return Shazam.recognize(signature, sampleDurationMs).fold(
            onSuccess = { result ->
                Timber.tag(TAG).i("Recognition successful: '%s' by %s", result.title, result.artist)
                RecognitionStatus.Success(result).also { _recognitionStatus.value = it }
            },
            onFailure = { error ->
                val message = error.message ?: "Unknown error"
                val status =
                    if (message.contains("No match", ignoreCase = true)) {
                        RecognitionStatus.NoMatch("No matches found. Try again with clearer audio.")
                    } else {
                        RecognitionStatus.Error(message)
                    }
                _recognitionStatus.value = status
                status
            },
        )
    }

    private fun decodeRadioStream(streamUrl: String): DecodedAudio {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        var codecStarted = false
        try {
            extractor.setDataSource(
                streamUrl,
                mapOf(
                    "Icy-MetaData" to "0",
                    "User-Agent" to "MetrolistHU/13.7.0 (direct recognition)",
                ),
            )
            val trackIndex =
                (0 until extractor.trackCount).firstOrNull { index ->
                    extractor.getTrackFormat(index).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true
                } ?: error("No audio track found in radio stream")
            extractor.selectTrack(trackIndex)
            val inputFormat = extractor.getTrackFormat(trackIndex)
            val mime = inputFormat.getString(MediaFormat.KEY_MIME) ?: error("Radio audio format is unknown")
            var sampleRate = inputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channelCount = inputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var pcmEncoding = AudioFormat.ENCODING_PCM_16BIT

            codec = MediaCodec.createDecoderByType(mime)
            codec.configure(inputFormat, null, null, 0)
            codec.start()
            codecStarted = true

            val output = ByteArrayOutputStream()
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            var firstSampleTimeUs = Long.MIN_VALUE
            val deadline = SystemClock.elapsedRealtime() + STREAM_DECODE_TIMEOUT_MS

            while (!outputDone && SystemClock.elapsedRealtime() < deadline) {
                if (!inputDone) {
                    val inputIndex = codec.dequeueInputBuffer(10_000)
                    if (inputIndex >= 0) {
                        val inputBuffer = codec.getInputBuffer(inputIndex) ?: error("Decoder input buffer unavailable")
                        inputBuffer.clear()
                        val sampleSize = extractor.readSampleData(inputBuffer, 0)
                        val sampleTimeUs = extractor.sampleTime
                        if (firstSampleTimeUs == Long.MIN_VALUE && sampleTimeUs >= 0) {
                            firstSampleTimeUs = sampleTimeUs
                        }
                        val reachedDuration =
                            firstSampleTimeUs != Long.MIN_VALUE &&
                                sampleTimeUs >= 0 &&
                                sampleTimeUs - firstSampleTimeUs >= RECORDING_DURATION_MS * 1000L
                        if (sampleSize < 0 || reachedDuration) {
                            codec.queueInputBuffer(
                                inputIndex,
                                0,
                                0,
                                sampleTimeUs.coerceAtLeast(0L),
                                MediaCodec.BUFFER_FLAG_END_OF_STREAM,
                            )
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(inputIndex, 0, sampleSize, sampleTimeUs, extractor.sampleFlags)
                            extractor.advance()
                        }
                    }
                }

                when (val outputIndex = codec.dequeueOutputBuffer(info, 10_000)) {
                    MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val outputFormat = codec.outputFormat
                        sampleRate = outputFormat.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        channelCount = outputFormat.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        if (outputFormat.containsKey(MediaFormat.KEY_PCM_ENCODING)) {
                            pcmEncoding = outputFormat.getInteger(MediaFormat.KEY_PCM_ENCODING)
                        }
                    }

                    MediaCodec.INFO_TRY_AGAIN_LATER, MediaCodec.INFO_OUTPUT_BUFFERS_CHANGED -> Unit
                    else -> {
                        if (outputIndex >= 0) {
                            if (info.size > 0 && info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG == 0) {
                                val outputBuffer = codec.getOutputBuffer(outputIndex)
                                    ?: error("Decoder output buffer unavailable")
                                outputBuffer.position(info.offset)
                                outputBuffer.limit(info.offset + info.size)
                                val chunk = ByteArray(info.size)
                                outputBuffer.get(chunk)
                                output.write(chunk)
                            }
                            codec.releaseOutputBuffer(outputIndex, false)
                            val bytesPerSecond = sampleRate.toLong() * channelCount.coerceAtLeast(1) * 2L
                            if (bytesPerSecond > 0 && output.size().toLong() >= bytesPerSecond * 12L) {
                                outputDone = true
                            }
                            if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                                outputDone = true
                            }
                        }
                    }
                }
            }

            if (output.size() == 0) error("No audio samples could be decoded from the radio stream")
            if (pcmEncoding != AudioFormat.ENCODING_PCM_16BIT) {
                error("Unsupported decoded PCM format: $pcmEncoding")
            }
            return DecodedAudio(
                data = output.toByteArray(),
                channelCount = channelCount,
                sampleRate = sampleRate,
                pcmEncoding = pcmEncoding,
            )
        } finally {
            if (codecStarted) runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
        }
    }

    private fun downmixToMono(source: DecodedAudio): DecodedAudio {
        require(source.pcmEncoding == AudioFormat.ENCODING_PCM_16BIT) {
            "Only 16-bit PCM can be fingerprinted"
        }
        if (source.channelCount <= 1) return source.copy(channelCount = 1)

        val input = ByteBuffer.wrap(source.data).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val frames = input.remaining() / source.channelCount
        val output = ByteBuffer.allocate(frames * 2).order(ByteOrder.LITTLE_ENDIAN)
        repeat(frames) {
            var sum = 0L
            repeat(source.channelCount) { sum += input.get().toLong() }
            output.putShort((sum / source.channelCount).coerceIn(Short.MIN_VALUE.toLong(), Short.MAX_VALUE.toLong()).toShort())
        }
        return DecodedAudio(
            data = output.array(),
            channelCount = 1,
            sampleRate = source.sampleRate,
            pcmEncoding = source.pcmEncoding,
        )
    }

    @SuppressLint("MissingPermission")
    private suspend fun recordAudio(): ByteArray =
        withContext(Dispatchers.IO) {
            val bufferSize =
                AudioRecord.getMinBufferSize(RECORDING_SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT)
                    .coerceAtLeast(RECORDING_SAMPLE_RATE)
            val audioRecord =
                AudioRecord(
                    MediaRecorder.AudioSource.MIC,
                    RECORDING_SAMPLE_RATE,
                    CHANNEL_CONFIG,
                    AUDIO_FORMAT,
                    bufferSize,
                )
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(bufferSize)
            val startedAt = System.currentTimeMillis()
            try {
                audioRecord.startRecording()
                while (System.currentTimeMillis() - startedAt < RECORDING_DURATION_MS && isActive) {
                    val count = audioRecord.read(buffer, 0, buffer.size)
                    if (count > 0) output.write(buffer, 0, count)
                }
            } finally {
                runCatching { audioRecord.stop() }
                audioRecord.release()
            }
            output.toByteArray()
        }

    private fun setError(message: String): RecognitionStatus =
        RecognitionStatus.Error(message).also { _recognitionStatus.value = it }

    fun reset() {
        _recognitionStatus.value = RecognitionStatus.Ready
        resultSavedExternally = false
    }
}
''',
)

print("Metrolist 13.7.0 requested fixes applied")
