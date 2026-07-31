package com.metrolist.music.playback

import android.view.KeyEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Dudu7MediaButtonRoutingTest {
    @Test
    fun `next and previous media keys map to one direction`() {
        assertEquals(
            true,
            Dudu7FmMediaButtonRouting.directionFor(
                KeyEvent.ACTION_DOWN,
                KeyEvent.KEYCODE_MEDIA_NEXT,
                0,
            ),
        )
        assertEquals(
            false,
            Dudu7FmMediaButtonRouting.directionFor(
                KeyEvent.ACTION_DOWN,
                KeyEvent.KEYCODE_MEDIA_PREVIOUS,
                0,
            ),
        )
    }

    @Test
    fun `key up repeat and unrelated keys are ignored`() {
        assertNull(
            Dudu7FmMediaButtonRouting.directionFor(
                KeyEvent.ACTION_UP,
                KeyEvent.KEYCODE_MEDIA_NEXT,
                0,
            ),
        )
        assertNull(
            Dudu7FmMediaButtonRouting.directionFor(
                KeyEvent.ACTION_DOWN,
                KeyEvent.KEYCODE_MEDIA_NEXT,
                1,
            ),
        )
        assertNull(
            Dudu7FmMediaButtonRouting.directionFor(
                KeyEvent.ACTION_DOWN,
                KeyEvent.KEYCODE_VOLUME_UP,
                0,
            ),
        )
    }
}
