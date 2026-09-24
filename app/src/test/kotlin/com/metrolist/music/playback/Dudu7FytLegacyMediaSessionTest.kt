package com.metrolist.music.playback

import android.view.KeyEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7FytLegacyMediaSessionTest {
    @Test
    fun `next and previous map to favourite navigation`() {
        assertEquals(
            FytLegacyMediaAction.NEXT_FAVOURITE,
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT, 0),
        )
        assertEquals(
            FytLegacyMediaAction.PREVIOUS_FAVOURITE,
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PREVIOUS, 0),
        )
    }

    @Test
    fun `fast forward and rewind remain separate tuner seek commands`() {
        assertEquals(
            FytLegacyMediaAction.SEEK_FORWARD,
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_FAST_FORWARD, 0),
        )
        assertEquals(
            FytLegacyMediaAction.SEEK_BACKWARD,
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_REWIND, 0),
        )
    }

    @Test
    fun `key up and repeats are consumed without another action`() {
        assertNull(
            fytLegacyMediaActionFor(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_MEDIA_NEXT, 0),
        )
        assertNull(
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_NEXT, 1),
        )
    }

    @Test
    fun `only the four NavRadio compatible FYT radio keys are recognized`() {
        assertTrue(isFytLegacyRadioKey(KeyEvent.KEYCODE_MEDIA_NEXT))
        assertTrue(isFytLegacyRadioKey(KeyEvent.KEYCODE_MEDIA_PREVIOUS))
        assertTrue(isFytLegacyRadioKey(KeyEvent.KEYCODE_MEDIA_FAST_FORWARD))
        assertTrue(isFytLegacyRadioKey(KeyEvent.KEYCODE_MEDIA_REWIND))
        assertNull(
            fytLegacyMediaActionFor(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE, 0),
        )
    }
}
