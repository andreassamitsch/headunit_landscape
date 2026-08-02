package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class FmAlternativeFrequencySelectorTest {
    @Test
    fun choosesStrongestMatchingPi() {
        val selected =
            FmAlternativeFrequencySelector.choose(
                currentFrequency = 99.7f,
                currentRssi = 18,
                expectedPi = 0xA123,
                measurements =
                    listOf(
                        FmAfMeasurement(106.8f, 42, 0xA123, true),
                        FmAfMeasurement(95.5f, 35, 0xA123, false),
                    ),
                minimumImprovement = 1,
            )

        assertEquals(106.8f, selected?.frequency)
    }

    @Test
    fun rejectsForeignPiEvenWhenSignalIsStrong() {
        val selected =
            FmAlternativeFrequencySelector.choose(
                currentFrequency = 99.7f,
                currentRssi = 18,
                expectedPi = 0xA123,
                measurements = listOf(FmAfMeasurement(106.8f, 60, 0xB456, true)),
                minimumImprovement = 1,
            )

        assertNull(selected)
    }

    @Test
    fun rejectsUnknownPiEvenForCachedOrRtrTrustedFrequency() {
        val cached =
            FmAlternativeFrequencySelector.choose(
                currentFrequency = 99.7f,
                currentRssi = 18,
                expectedPi = 0xA123,
                measurements = listOf(FmAfMeasurement(106.8f, 40, 0, true)),
                minimumImprovement = 1,
            )
        val rtrOnly =
            FmAlternativeFrequencySelector.choose(
                currentFrequency = 99.7f,
                currentRssi = 18,
                expectedPi = 0xA123,
                measurements = listOf(FmAfMeasurement(106.8f, 40, 0, false)),
                minimumImprovement = 1,
            )

        assertNull(cached)
        assertNull(rtrOnly)
    }
}
