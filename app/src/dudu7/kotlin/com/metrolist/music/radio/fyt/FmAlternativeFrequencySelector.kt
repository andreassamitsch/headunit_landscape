package com.metrolist.music.radio.fyt

import kotlin.math.abs

data class FmAfCandidate(
    val frequency: Float,
    val trustedPresetFrequency: Boolean,
)

data class FmAfMeasurement(
    val frequency: Float,
    val rssi: Int,
    val pi: Int,
    val trustedPresetFrequency: Boolean,
)

/** Pure AF decision logic, separated from the FYT hardware calls for regression testing. */
object FmAlternativeFrequencySelector {
    fun choose(
        currentFrequency: Float,
        currentRssi: Int,
        expectedPi: Int,
        measurements: Collection<FmAfMeasurement>,
        minimumImprovement: Int,
    ): FmAfMeasurement? =
        measurements
            .asSequence()
            .filter { abs(it.frequency - currentFrequency) >= 0.05f }
            .filter { it.rssi > 0 }
            .filter { compatiblePi(expectedPi, it.pi, it.trustedPresetFrequency) }
            .filter { currentRssi <= 0 || it.rssi >= currentRssi + minimumImprovement }
            .maxWithOrNull(compareBy<FmAfMeasurement> { it.rssi }.thenByDescending { it.frequency })

    fun compatiblePi(
        expectedPi: Int,
        receivedPi: Int,
        trustedPresetFrequency: Boolean,
    ): Boolean =
        when {
            expectedPi <= 0 -> trustedPresetFrequency
            receivedPi <= 0 -> trustedPresetFrequency
            else -> (expectedPi and 0xffff) == (receivedPi and 0xffff)
        }
}
