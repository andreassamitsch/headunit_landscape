package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RadioStationLogoSearchTest {
    @Test
    fun `radio at slug variants include Partyhitmix spelling used by station page`() {
        val slugs = RadioStationLogoSearch.radioAtSlugs("Antenne Kärnten Party Hitmix")

        assertTrue("antennekaerntenpartyhitmix" in slugs)
        assertTrue("antennekaerntenpartymix" in slugs)
    }

    @Test
    fun `radio at station image uses resolved page slug`() {
        assertEquals(
            "https://www.radio.at/300/antennekaerntenpartymix.png?version=",
            RadioStationLogoSearch.radioAtStationImageUrl(
                "https://www.radio.at/s/antennekaerntenpartymix",
            ),
        )
    }

    @Test
    fun `station matching tolerates Party Hitmix spacing`() {
        assertEquals(
            100,
            RadioStationLogoSearch.stationMatchScore(
                "Antenne Kärnten Party Hitmix",
                "Antenne Kärnten Partyhitmix",
            ),
        )
    }
}
