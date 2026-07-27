package com.metrolist.music.radio

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
}
