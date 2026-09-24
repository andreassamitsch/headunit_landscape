package com.metrolist.music.playback

import android.view.KeyEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Dudu7FmMediaButtonRoutingTest {
    @Test
    fun `next and previous keys map to FM favourite direction`() {
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT, 0))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PREVIOUS, 0))
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD, 0))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD, 0))
    }

    @Test
    fun `key up repeat and unrelated media keys remain on Media3 path`() {
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_NEXT, 0))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT, 1))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, 0))
    }
}
