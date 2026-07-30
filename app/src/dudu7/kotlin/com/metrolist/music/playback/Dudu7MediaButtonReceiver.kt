package com.metrolist.music.playback

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.view.KeyEvent
import androidx.media3.session.MediaButtonReceiver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.tuneAdjacentFavourite

/**
 * Routes steering-wheel/CAN media keys to FM favourites while physical FM is active.
 * Every other media key and every non-FM mode stays on the normal Media3 path.
 */
class Dudu7MediaButtonReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        Dudu7FmMediaButtonRouting.install(context.applicationContext)
        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return
        MediaButtonReceiver().onReceive(context, intent)
    }

    private fun Intent.mediaKeyEvent(): KeyEvent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(Intent.EXTRA_KEY_EVENT)
        }
}

internal object Dudu7FmMediaButtonRouting {
    @Volatile
    private var installed = false

    fun install(context: Context) {
        if (installed) return
        synchronized(this) {
            if (installed) return
            val appContext = context.applicationContext
            PhysicalFmMediaKeyBridge.install { next ->
                if (!FytPhysicalRadio.state.value.isActive) return@install false
                FytPhysicalRadio.tuneAdjacentFavourite(appContext, next)
                true
            }
            installed = true
        }
    }

    /** Returns true for next, false for previous and null when Media3 should handle the key. */
    fun directionFor(
        action: Int,
        keyCode: Int,
        repeatCount: Int,
    ): Boolean? {
        if (action != KeyEvent.ACTION_DOWN || repeatCount != 0) return null
        return when (keyCode) {
            KeyEvent.KEYCODE_MEDIA_NEXT,
            KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD,
            -> true

            KeyEvent.KEYCODE_MEDIA_PREVIOUS,
            KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD,
            -> false

            else -> null
        }
    }
}
