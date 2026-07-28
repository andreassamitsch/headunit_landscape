package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FmStationIdentityTest {
    @Test
    fun antennaAndStmkShareCanonicalIdentityOnSteiermarkFrequencies() {
        val frequencies = listOf(99.7f, 106.8f)
        val antenna = FmStationIdentity.resolve("ANTENNE", null, frequencies)
        val stmk = FmStationIdentity.resolve("STMK", "ANTENNE", frequencies)

        assertEquals("Antenne Steiermark", antenna.canonicalName)
        assertEquals(antenna.stableId, stmk.stableId)
        assertEquals("station:antenne_steiermark", antenna.stableId)
    }

    @Test
    fun shortStmkIsNotBlindlyAssignedOutsideAntenneFrequencies() {
        val identity = FmStationIdentity.resolve("STMK", null, listOf(88.2f))

        assertFalse(identity.recognized)
        assertEquals("STMK", identity.canonicalName)
    }

    @Test
    fun orderAliasesSurviveNameAndPiTransitions() {
        val frequencies = listOf(99.7f, 106.8f)
        val beforePi = FmStationIdentity.orderKeys("ANTENNE", "ANTENNE", frequencies)
        val afterPi = FmStationIdentity.orderKeys("STMK", "Antenne Steiermark", frequencies, 0xA123, "e0")

        assertTrue(beforePi.intersect(afterPi).isNotEmpty())
        assertTrue(afterPi.contains("name:antenne"))
        assertTrue(afterPi.contains("name:stmk"))
    }

    @Test
    fun specificUserNameIsDisplayedButCatalogIdentityStaysStable() {
        val identity = FmStationIdentity.resolve("STMK", "Meine Antenne", listOf(99.7f))

        assertEquals("Meine Antenne", identity.canonicalName)
        assertEquals("station:antenne_steiermark", identity.stableId)
    }
}
