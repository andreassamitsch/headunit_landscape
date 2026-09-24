package com.metrolist.music.radio.fyt

import kotlin.math.abs

data class FmAfCandidate(
    val frequency: Float,
    val trustedPresetFrequency: Boolean,
    val predictedCoverage: Int = 0,
    val source: String = "Tuner",
)

data class FmAfMeasurement(
    val frequency: Float,
    val rssi: Int,
    val pi: Int,
    val trustedPresetFrequency: Boolean,
    val predictedCoverage: Int = 0,
    val source: String = "Tuner",
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
            .maxWithOrNull(
                compareBy<FmAfMeasurement> { it.rssi }
                    .thenBy { it.predictedCoverage }
                    .thenByDescending { it.frequency },
            )

    /**
     * RTR and a cached reception path may propose a frequency, but neither is proof that the
     * frequency currently carries the same station. Every accepted target therefore needs a
     * fresh, non-zero PI that exactly matches the source PI.
     */
    fun compatiblePi(
        expectedPi: Int,
        receivedPi: Int,
        @Suppress("UNUSED_PARAMETER") trustedPresetFrequency: Boolean,
    ): Boolean =
        expectedPi > 0 &&
            receivedPi > 0 &&
            (expectedPi and 0xffff) == (receivedPi and 0xffff)
}
