package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.util.UnstableApi
import com.metrolist.music.radio.fyt.FytPhysicalRadio

/** Installs the Dudu7 hardware-radio player and the diagnostic Syu radio-source client. */
@UnstableApi
internal object Dudu7FmSessionRouting {
    @Volatile
    private var installed = false

    fun install(context: Context) {
        if (installed) return
        synchronized(this) {
            if (installed) return
            val appContext = context.applicationContext
            Dudu7FmMediaButtonRouting.install(appContext)
            Dudu7SyuRadioIpc.install(appContext)
            val player = Dudu7FmSessionPlayer(appContext)
            PhysicalFmSessionBridge.install(
                PhysicalFmSessionBridge.Controller(
                    player = player,
                    // This flow intentionally represents session ownership, not only the
                    // already-active tuner. The additional Syu client claims the Dudu7 radio
                    // source before FmNative is opened and logs all MAIN-module callbacks.
                    isActive = player.isActive,
                    deactivate = { FytPhysicalRadio.powerOff() },
                    release = {
                        Dudu7SyuRadioIpc.releaseFmSource()
                        Dudu7SyuRadioIpc.release()
                        Dudu7FmSessionOwnership.release()
                        player.release()
                    },
                ),
            )
            installed = true
        }
    }
}
