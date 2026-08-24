package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RadioTrackMetadataTest {
    @Test
    fun `station branding formatted as artist and title is ambiguous`() {
        val (artist, title) = parseRadioStreamTitle("Antenne - Partyhitmix")

        assertFalse(
            isClearRadioTrackMetadata(
                artist = artist,
                title = title,
                stationName = "Antenne Kärnten Party Hitmix",
            ),
        )
    }

    @Test
    fun `real artist and title remain clear metadata`() {
        val (artist, title) = parseRadioStreamTitle("Purple Disco Machine - Hypnotized")

        assertTrue(
            isClearRadioTrackMetadata(
                artist = artist,
                title = title,
                stationName = "Antenne Kärnten Party Hitmix",
            ),
        )
    }

    @Test
    fun `title without an artist remains eligible for fingerprint recognition`() {
        val (artist, title) = parseRadioStreamTitle("Antenne Partyhitmix")

        assertFalse(
            isClearRadioTrackMetadata(
                artist = artist,
                title = title,
                stationName = "Antenne Kärnten Party Hitmix",
            ),
        )
    }

    @Test
    fun `utf8 decoded as latin1 is repaired before parsing`() {
        val mojibake = "Schritt f" + '\u00c3' + '\u00bcr Schritt"

        val (_, title) = parseRadioStreamTitle(mojibake)

        assertEquals("Schritt für Schritt", title)
    }

    @Test
    fun `artist and title mojibake are both repaired`() {
        val mojibake = "Gr" + '\u00c3' + '\u00bc' + "ße aus " + '\u00c3' + '\u0096' + "sterreich - f" + '\u00c3' + '\u00bc' + "r dich"

        val (artist, title) = parseRadioStreamTitle(mojibake)

        assertEquals("Grüße aus Österreich", artist)
        assertEquals("für dich", title)
    }

    @Test
    fun `correct unicode and ascii remain unchanged`() {
        assertEquals("Grüße aus Österreich", repairRadioStreamMojibake("Grüße aus Österreich"))
        assertEquals("Simple ASCII Title", repairRadioStreamMojibake("Simple ASCII Title"))
    }

    @Test
    fun `suspicious but invalid latin1 roundtrip remains unchanged`() {
        val legitimate = "Ãlvaro Soler"

        assertEquals(legitimate, repairRadioStreamMojibake(legitimate))
    }
}
