package com.metrolist.music.playback

import android.content.Context
import android.content.Intent
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.view.KeyEvent
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/**
 * FYT head units route radio steering-wheel keys to a classic framework MediaSession.
 *
 * NavRadio+ 4.08 uses the same mechanism in QFService: an active session tagged
 * "FmRadioApp" with FLAG_HANDLES_MEDIA_BUTTONS and a callback that consumes the
 * raw key event before the stock FYT radio handler resets the preset index.
 *
 * Media3 remains the public playback/session representation. This session is active
 * only while the physical FM tuner is active and only handles the four radio keys.
 */
@Suppress("DEPRECATION")
internal class Dudu7FytLegacyMediaSession(
    context: Context,
) {
    private val appContext = context.applicationContext
    private val radio = FytPhysicalRadio.get(appContext)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val mainHandler = Handler(Looper.getMainLooper())
    private val seekLock = Any()

    private var released = false
    private var lastSeekDirection: Boolean? = null
    private var lastSeekAt = 0L

    private val session =
        MediaSession(appContext, SESSION_TAG).apply {
            setFlags(MediaSession.FLAG_HANDLES_MEDIA_BUTTONS)
            setPlaybackState(buildPlaybackState(active = false))
            setCallback(
                object : MediaSession.Callback() {
                    override fun onMediaButtonEvent(mediaButtonIntent: Intent): Boolean =
                        handleMediaButton(mediaButtonIntent)
                },
                mainHandler,
            )
        }

    init {
        scope.launch {
            radio.state
                .map { it.isActive }
                .distinctUntilChanged()
                .collect { active -> setFmActive(active) }
        }
    }

    fun release() {
        if (released) return
        released = true
        scope.cancel()
        runCatching {
            session.isActive = false
            session.setCallback(null as MediaSession.Callback?)
            session.release()
        }.onFailure { error ->
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_LEGACY_STATE",
                "releaseFailed=${error.javaClass.simpleName}:${error.message.orEmpty()}",
            )
        }
    }

    private fun setFmActive(active: Boolean) {
        if (released) return
        runCatching {
            session.setPlaybackState(buildPlaybackState(active))
            session.isActive = active
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_LEGACY_STATE",
                "tag=$SESSION_TAG active=$active fmActive=${radio.state.value.isActive}",
            )
        }.onFailure { error ->
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_LEGACY_STATE",
                "tag=$SESSION_TAG active=$active failed=${error.javaClass.simpleName}:${error.message.orEmpty()}",
            )
        }
    }

    private fun handleMediaButton(intent: Intent): Boolean {
        val event = intent.mediaKeyEvent() ?: return false
        val fmActive = radio.state.value.isActive
        val recognized = isFytLegacyRadioKey(event.keyCode)

        MediaKeyDiagnostics.recordMediaButton(
            appContext,
            stage = "FYT_LEGACY_SESSION",
            intent = intent,
            details = "tag=$SESSION_TAG fmActive=$fmActive recognized=$recognized",
        )

        if (!fmActive || !recognized) return false

        val action = fytLegacyMediaActionFor(
            action = event.action,
            keyCode = event.keyCode,
            repeatCount = event.repeatCount,
        )

        // Consume key-up and repeated events as well, but execute only the first down event.
        if (action == null) {
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_LEGACY_ROUTE",
                "keyCode=${event.keyCode} action=${KeyEvent.actionToString(event.action)} " +
                    "repeat=${event.repeatCount} decision=consumed_without_action",
            )
            return true
        }

        val handled =
            when (action) {
                FytLegacyMediaAction.NEXT_FAVOURITE -> PhysicalFmMediaKeyBridge.handleDirection(next = true)
                FytLegacyMediaAction.PREVIOUS_FAVOURITE -> PhysicalFmMediaKeyBridge.handleDirection(next = false)
                FytLegacyMediaAction.SEEK_FORWARD -> handleSeek(next = true)
                FytLegacyMediaAction.SEEK_BACKWARD -> handleSeek(next = false)
            }

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_LEGACY_ROUTE",
            "keyCode=${event.keyCode} action=$action handled=$handled consumed=true",
        )
        return true
    }

    private fun handleSeek(next: Boolean): Boolean {
        val now = SystemClock.elapsedRealtime()
        synchronized(seekLock) {
            if (lastSeekDirection == next && now - lastSeekAt <= DUPLICATE_WINDOW_MS) return true
            lastSeekDirection = next
            lastSeekAt = now
        }
        radio.seek(next)
        MediaKeyDiagnostics.record(
            appContext,
            "FYT_LEGACY_SEEK",
            "direction=${if (next) "FORWARD" else "BACKWARD"}",
        )
        return true
    }

    private fun buildPlaybackState(active: Boolean): PlaybackState =
        PlaybackState.Builder()
            .setActions(
                PlaybackState.ACTION_SKIP_TO_NEXT or
                    PlaybackState.ACTION_SKIP_TO_PREVIOUS or
                    PlaybackState.ACTION_FAST_FORWARD or
                    PlaybackState.ACTION_REWIND,
            ).setState(
                if (active) PlaybackState.STATE_PLAYING else PlaybackState.STATE_STOPPED,
                0L,
                if (active) 1f else 0f,
            ).build()

    private fun Intent.mediaKeyEvent(): KeyEvent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(Intent.EXTRA_KEY_EVENT)
        }

    companion object {
        private const val SESSION_TAG = "FmRadioApp"
        private const val DUPLICATE_WINDOW_MS = 280L
    }
}

internal enum class FytLegacyMediaAction {
    NEXT_FAVOURITE,
    PREVIOUS_FAVOURITE,
    SEEK_FORWARD,
    SEEK_BACKWARD,
}

internal fun isFytLegacyRadioKey(keyCode: Int): Boolean =
    keyCode == KeyEvent.KEYCODE_MEDIA_NEXT ||
        keyCode == KeyEvent.KEYCODE_MEDIA_PREVIOUS ||
        keyCode == KeyEvent.KEYCODE_MEDIA_FAST_FORWARD ||
        keyCode == KeyEvent.KEYCODE_MEDIA_REWIND

internal fun fytLegacyMediaActionFor(
    action: Int,
    keyCode: Int,
    repeatCount: Int,
): FytLegacyMediaAction? {
    if (action != KeyEvent.ACTION_DOWN || repeatCount != 0) return null
    return when (keyCode) {
        KeyEvent.KEYCODE_MEDIA_NEXT -> FytLegacyMediaAction.NEXT_FAVOURITE
        KeyEvent.KEYCODE_MEDIA_PREVIOUS -> FytLegacyMediaAction.PREVIOUS_FAVOURITE
        KeyEvent.KEYCODE_MEDIA_FAST_FORWARD -> FytLegacyMediaAction.SEEK_FORWARD
        KeyEvent.KEYCODE_MEDIA_REWIND -> FytLegacyMediaAction.SEEK_BACKWARD
        else -> null
    }
}
