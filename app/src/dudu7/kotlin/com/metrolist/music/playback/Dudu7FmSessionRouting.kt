package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.util.UnstableApi
import com.metrolist.music.radio.fyt.FytPhysicalRadio

/** Installs the Dudu7 hardware-radio Player into the variant-neutral bridge. */
@UnstableApi
internal object Dudu7FmSessionRouting {
    @Volatile
    private var installed = false

    fun install(context: Context) {
        if (installed) return
        synchronized(this) {
            if (installed) return
            val player = Dudu7FmSessionPlayer(context.applicationContext)
            PhysicalFmSessionBridge.install(
                PhysicalFmSessionBridge.Controller(
                    player = player,
                    isActive = player.isActive,
                    deactivate = { FytPhysicalRadio.powerOff() },
                    release = { player.release() },
                ),
            )
            installed = true
        }
    }
}
