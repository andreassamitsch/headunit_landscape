package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.util.UnstableApi
import com.metrolist.music.radio.fyt.FytPhysicalRadio

/** Installs the Dudu7 hardware-radio players and media-button routes. */
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
            val player = Dudu7FmSessionPlayer(appContext)
            val legacyMediaSession = Dudu7FytLegacyMediaSession(appContext)
            PhysicalFmSessionBridge.install(
                PhysicalFmSessionBridge.Controller(
                    player = player,
                    isActive = player.isActive,
                    deactivate = { FytPhysicalRadio.powerOff() },
                    release = {
                        legacyMediaSession.release()
                        com.metrolist.music.radio.fyt.Dudu7FytTwController.get(appContext).close()
                        player.release()
                    },
                ),
            )
            installed = true
        }
    }
}
