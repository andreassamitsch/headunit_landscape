package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FmStationAssociationTest {
    @Test
    fun conflictingRtrIdsNeverMergeEvenWithSamePiAndFrequency() {
        val first = FmStationEvidence(listOf(94.2f), "Kronehit", 0xA123, "rtr:kronehit")
        val second = FmStationEvidence(listOf(94.2f), "Radio Velenje", 0xA123, "rtr:radio_velenje")

        assertFalse(FmStationAssociation.sameStation(first, second))
    }

    @Test
    fun samePiWithDifferentNamesDoesNotMerge() {
        val first = FmStationEvidence(listOf(93.1f), "Ö3", 0xA203, confirmed = true)
        val second = FmStationEvidence(listOf(94.2f), "Kronehit", 0xA203, confirmed = true)

        assertFalse(FmStationAssociation.sameStation(first, second))
    }

    @Test
    fun regionalPsSegmentsStillMergeForKnownStation() {
        val first = FmStationEvidence(listOf(99.7f), "ANTENNE", 0xA501, confirmed = true)
        val second = FmStationEvidence(listOf(106.8f), "STMK", 0xA501, confirmed = true)

        assertTrue(FmStationAssociation.sameStation(first, second))
    }

    @Test
    fun exactFrequencyWinsBeforeDuplicatedPi() {
        val presets = listOf(
            FmStationEvidence(listOf(87.6f), "FM4", 0xA111, "rtr:fm4"),
            FmStationEvidence(listOf(94.2f), "Kronehit", 0xA111, "rtr:kronehit"),
        )

        assertEquals(
            1,
            FmStationAssociation.selectCurrentIndex(
                presets = presets,
                frequency = 94.2f,
                pi = 0xA111,
                rdsConfirmed = true,
                stationId = "",
            ),
        )
    }

    @Test
    fun ambiguousPiWithoutFrequencyDoesNotSelectAnyPreset() {
        val presets = listOf(
            FmStationEvidence(listOf(87.6f), "FM4", 0xA111),
            FmStationEvidence(listOf(94.2f), "Kronehit", 0xA111),
        )

        assertEquals(
            -1,
            FmStationAssociation.selectCurrentIndex(
                presets = presets,
                frequency = 107.8f,
                pi = 0xA111,
                rdsConfirmed = true,
                stationId = "",
            ),
        )
    }

    @Test
    fun singleStaleRdsSampleIsRejected() {
        val observation = FmRdsFreshness.consolidate(
            listOf(
                FmRdsSample("Ö3", 0xA203),
                FmRdsSample("", 0),
                FmRdsSample("", 0),
            ),
        )

        assertFalse(observation.confirmed)
        assertEquals(0, observation.pi)
        assertEquals("", observation.ps)
    }

    @Test
    fun repeatedPostTunePiAndNameAreAccepted() {
        val observation = FmRdsFreshness.consolidate(
            listOf(
                FmRdsSample("KRONEHIT", 0xA123, "E0", 10, true),
                FmRdsSample("KRONEHIT", 0xA123, "E0", 10, true),
                FmRdsSample("KRONEHIT", 0xA123, "E0", 10, true),
            ),
        )

        assertTrue(observation.confirmed)
        assertEquals(0xA123, observation.pi)
        assertEquals("KRONEHIT", observation.ps)
        assertEquals("E0", observation.ecc)
    }
}
