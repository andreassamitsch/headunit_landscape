/**
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
    suspend fun recognizeStream(context: Context, streamUrl: String): RecognitionStatus =
        withContext(Dispatchers.IO) {
            if (streamUrl.isBlank()) return@withContext setError("Radiostream is unavailable")
            _recognitionStatus.value = RecognitionStatus.Listening
            try {
                val decoded =
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
                Timber.tag(TAG).i(
                    "Direct radio stream decoded: bytes=%d sampleRate=%d channels=%d",
                    decoded.data.size,
                    decoded.sampleRate,
                    decoded.channelCount,
                )
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

    private fun String.isHlsStreamUrl(): Boolean {
        val normalized = substringBefore('#').substringBefore('?').lowercase()
        return normalized.endsWith(".m3u8") || normalized.contains("/playlist.m3u8") || normalized.contains("/manifest.m3u8")
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
                    "User-Agent" to "MetrolistHU/13.7.5 (direct recognition)",
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
