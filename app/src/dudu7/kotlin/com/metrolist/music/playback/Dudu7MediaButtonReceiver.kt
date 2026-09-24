package com.metrolist.music.playback

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.view.KeyEvent
import androidx.media3.session.MediaButtonReceiver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.tuneAdjacentFavourite

class Dudu7MediaButtonReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val appContext = context.applicationContext
        Dudu7FmMediaButtonRouting.install(appContext)
        Dudu7FmSessionRouting.install(appContext)
        MediaKeyDiagnostics.recordMediaButton(
            appContext,
            stage = "RECEIVER",
            intent = intent,
            details = "fmActive=${PhysicalFmSessionBridge.isActive()}",
        )

        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) {
            MediaKeyDiagnostics.record(appContext, "ROUTE", "receiver -> direct FM favourite; consumed=true")
            return
        }

        MediaKeyDiagnostics.record(appContext, "ROUTE", "receiver -> Media3 MediaButtonReceiver")
        MediaButtonReceiver().onReceive(context, intent)
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
                MediaKeyDiagnostics.record(
                    appContext,
                    "FM_DIRECT",
                    "direction=${if (next) "NEXT" else "PREVIOUS"}",
                )
                FytPhysicalRadio.tuneAdjacentFavourite(appContext, next)
                true
            }
            installed = true
        }
    }

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
