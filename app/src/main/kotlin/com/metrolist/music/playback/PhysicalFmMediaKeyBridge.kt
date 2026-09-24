package com.metrolist.music.playback

import android.content.Intent
import android.os.Build
import android.os.SystemClock
import android.view.KeyEvent

/**
 * Variant-neutral media-key bridge. The Dudu7 source set installs a handler for
 * physical FM; standard variants leave it unset and stay entirely on Media3.
 */
object PhysicalFmMediaKeyBridge {
    private const val DUPLICATE_WINDOW_MS = 280L

    @Volatile
    private var handler: ((Boolean) -> Boolean)? = null
    private val lock = Any()
    private var lastDirection: Boolean? = null
    private var lastHandledAt = 0L

    fun install(value: ((Boolean) -> Boolean)?) {
        handler = value
        synchronized(lock) {
            lastDirection = null
            lastHandledAt = 0L
        }
    }

    fun handleMediaButton(intent: Intent): Boolean {
        val event = intent.mediaKeyEvent() ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false
        val direction = when (event.keyCode) {
            KeyEvent.KEYCODE_MEDIA_NEXT,
            KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD,
            -> true
            KeyEvent.KEYCODE_MEDIA_PREVIOUS,
            KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD,
            -> false
            else -> return false
        }
        return handleDirection(direction)
    }

    fun handleDirection(next: Boolean): Boolean {
        val activeHandler = handler ?: return false
        val now = SystemClock.elapsedRealtime()
        synchronized(lock) {
            if (lastDirection == next && now - lastHandledAt <= DUPLICATE_WINDOW_MS) return true
            if (!activeHandler(next)) return false
            lastDirection = next
            lastHandledAt = now
            return true
        }
    }

    private fun Intent.mediaKeyEvent(): KeyEvent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(Intent.EXTRA_KEY_EVENT)
        }
}
