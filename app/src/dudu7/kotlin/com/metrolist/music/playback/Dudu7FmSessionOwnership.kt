package com.metrolist.music.playback

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Dudu7/UIS7870 MediaSession ownership gate.
 *
 * NavRadio+ creates its MediaSessionService player/session before claiming the physical
 * FM source. On Dudu7 this ordering is important: com.syu.ms routes steering-wheel
 * transport keys to the media owner that is active when RadioProxy/FmNative takes over.
 */
internal object Dudu7FmSessionOwnership {
    private val _claimed = MutableStateFlow(false)
    val claimed: StateFlow<Boolean> = _claimed.asStateFlow()

    fun claim(): Boolean {
        val changed = !_claimed.value
        _claimed.value = true
        return changed
    }

    fun release(): Boolean {
        val changed = _claimed.value
        _claimed.value = false
        return changed
    }
}
