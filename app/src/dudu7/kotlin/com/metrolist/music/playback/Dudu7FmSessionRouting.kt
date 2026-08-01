package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.util.UnstableApi
import com.metrolist.music.radio.fyt.FytPhysicalRadio

/** Installs the single Dudu7 hardware-radio player into MusicService's MediaSession. */
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
            PhysicalFmSessionBridge.install(
                PhysicalFmSessionBridge.Controller(
                    player = player,
                    // This flow intentionally represents session ownership, not only the
                    // already-active tuner. NavRadio+ owns the MediaSession before it claims
                    // the Dudu7 RadioProxy/FmNative source, so steering keys follow the app.
                    isActive = player.isActive,
                    deactivate = { FytPhysicalRadio.powerOff() },
                    release = {
                        Dudu7FmSessionOwnership.release()
                        player.release()
                    },
                ),
            )
            installed = true
        }
    }
}
