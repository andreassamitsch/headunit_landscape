package com.metrolist.music.playback

import android.view.KeyEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Dudu7FmMediaButtonRoutingTest {
    @Test
    fun `next and previous keys map to FM favourite direction`() {
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT)))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PREVIOUS)))
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD)))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD)))
    }

    @Test
    fun `key up repeat and unrelated media keys remain on Media3 path`() {
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_NEXT)))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent(1L, 1L, KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT, 1)))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(null))
    }
}
