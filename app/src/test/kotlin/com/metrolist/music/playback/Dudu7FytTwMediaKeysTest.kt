package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Test

class Dudu7FytTwMediaKeysTest {
    @Test
    fun `short FYT key presses navigate FM favourites`() {
        assertEquals(
            FytTwKeyAction.NEXT_FAVOURITE,
            resolveFytTwKeyAction(0x0201, 19, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.PREVIOUS_FAVOURITE,
            resolveFytTwKeyAction(0x0201, 21, 1, fmActive = true),
        )
    }

    @Test
    fun `long FYT key presses start seek in matching direction`() {
        assertEquals(
            FytTwKeyAction.SEEK_UP,
            resolveFytTwKeyAction(0x0201, 19, 2, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.SEEK_DOWN,
            resolveFytTwKeyAction(0x0201, 21, 2, fmActive = true),
        )
    }

    @Test
    fun `key messages are ignored outside active FM`() {
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 19, 1, fmActive = false),
        )
    }

    @Test
    fun `unrelated TW events keys and press types are ignored`() {
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0203, 19, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 20, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 19, 0, fmActive = true),
        )
    }
}
