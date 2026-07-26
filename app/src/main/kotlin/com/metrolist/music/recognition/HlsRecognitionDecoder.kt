package com.metrolist.music.recognition

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
