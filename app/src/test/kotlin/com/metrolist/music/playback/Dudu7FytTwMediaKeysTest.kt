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
    fun `key messages require both MetroList and FYT radio ownership`() {
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 19, 1, fmActive = false),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(
                0x0201,
                19,
                1,
                fmActive = true,
                vendorRadioActive = false,
            ),
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

    @Test
    fun `event subscription exactly matches NavRadio 4 08 FYT path`() {
        assertEquals(
            listOf(0x0109, 0x010A, 0x0201, 0x0203, 0x0301, 0x0302, 0x0401, 0x0402, 0x0404, 0x0405, 0x0406, 0x9E00),
            Dudu7FytTwProtocol.EVENTS.map { it.toInt() and 0xFFFF },
        )
    }

    @Test
    fun `initialization writes exactly match NavRadio 4 08`() {
        assertEquals(
            listOf(
                FytTwWrite(0x0109, 0xFF),
                FytTwWrite(0x010A, 0xFF),
                FytTwWrite(0x010A, 0xFF, 1),
                FytTwWrite(0x0112, 0xFF),
                FytTwWrite(0x010A, 0xFF, 0),
                FytTwWrite(0x0301, 0xFF),
                FytTwWrite(0x0406, 0),
                FytTwWrite(0x0401, 0xFF),
                FytTwWrite(0x0404, 0xFF),
                FytTwWrite(0x0405, 0xFF),
                FytTwWrite(0x0203, 0xFF),
            ),
            Dudu7FytTwProtocol.INITIALIZATION_WRITES,
        )
    }

    @Test
    fun `FM ownership writes match NavRadio enter and exit logic`() {
        assertEquals(
            listOf(
                FytTwWrite(0x0301, 0xC0, 1),
                FytTwWrite(0x9E00, 1),
                FytTwWrite(0x9E11, 0xC0, 1),
            ),
            Dudu7FytTwProtocol.ENTER_FM_WRITES,
        )
        assertEquals(
            listOf(
                FytTwWrite(0x0301, 0xC0, 0),
                FytTwWrite(0x9E11, 0xC0, 0x81),
                FytTwWrite(0x9E00, 0x81),
                FytTwWrite(0x9E00, 0x81, 0),
            ),
            Dudu7FytTwProtocol.EXIT_FM_WRITES,
        )
    }
}
