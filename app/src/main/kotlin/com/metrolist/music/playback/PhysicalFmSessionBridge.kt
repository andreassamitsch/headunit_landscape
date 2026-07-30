package com.metrolist.music.playback

import androidx.media3.common.Player
import kotlinx.coroutines.flow.StateFlow
import java.util.concurrent.CopyOnWriteArraySet

/**
 * Variant-neutral bridge between [MusicService] and a hardware-radio Player.
 *
 * Standard builds never install a controller. The Dudu7 source set installs a
 * Media3 player that mirrors the FYT tuner and its ordered FM favourites.
 */
object PhysicalFmSessionBridge {
    data class Controller(
        val player: Player,
        val isActive: StateFlow<Boolean>,
        val deactivate: () -> Unit,
        val release: () -> Unit,
    )

    private val listeners = CopyOnWriteArraySet<(Controller?) -> Unit>()

    @Volatile
    private var controller: Controller? = null

    fun install(value: Controller?) {
        val previous = controller
        if (previous === value) return
        controller = value
        if (previous != null && previous !== value) {
            runCatching(previous.release)
        }
        listeners.forEach { listener -> listener(value) }
    }

    fun current(): Controller? = controller

    fun owns(player: Player): Boolean = controller?.player === player

    fun isActive(): Boolean = controller?.isActive?.value == true

    fun deactivate() {
        controller?.deactivate?.invoke()
    }

    /** Returns a function that removes the observer. */
    fun observe(listener: (Controller?) -> Unit): () -> Unit {
        listeners += listener
        listener(controller)
        return { listeners -= listener }
    }
}
