package com.metrolist.music.radio.fyt

import java.text.Normalizer
import java.util.Locale
import kotlin.math.abs

data class FmStationEvidence(
    val frequencies: List<Float>,
    val name: String,
    val pi: Int = 0,
    val stationId: String = "",
    val confirmed: Boolean = true,
)

/**
 * Conservative station association rules. A single PI, AF entry or stale name is
 * never sufficient to join two different programmes.
 */
object FmStationAssociation {
    fun sameStation(first: FmStationEvidence, second: FmStationEvidence): Boolean {
        val firstExplicit = first.stationId.trim()
        val secondExplicit = second.stationId.trim()
        if (firstExplicit.isNotBlank() && secondExplicit.isNotBlank()) {
            return firstExplicit == secondExplicit
        }

        val firstResolved = resolvedStationId(first)
        val secondResolved = resolvedStationId(second)
        if (firstExplicit.isNotBlank() && secondResolved != null && firstExplicit != secondResolved) return false
        if (secondExplicit.isNotBlank() && firstResolved != null && secondExplicit != firstResolved) return false
        if (firstResolved != null && secondResolved != null && firstResolved != secondResolved) return false
        if (firstResolved != null && firstResolved == secondResolved) return true

        val frequencyOverlap = first.frequencies.any { left ->
            second.frequencies.any { right -> abs(left - right) < 0.05f }
        }
        if (frequencyOverlap && compatibleNames(first, second)) return true

        val confirmedPiMatch =
            first.confirmed && second.confirmed && first.pi > 0 && second.pi > 0 &&
                samePi(first.pi, second.pi) && usefulName(first.name) && usefulName(second.name)
        return confirmedPiMatch && compatibleNames(first, second)
    }

    fun selectCurrentIndex(
        presets: List<FmStationEvidence>,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Int {
        val exact = presets.indices.filter { index ->
            presets[index].frequencies.any { abs(it - frequency) < 0.05f }
        }
        if (exact.size == 1) return exact.first()
        if (exact.isNotEmpty()) {
            stationId.takeIf(String::isNotBlank)?.let { id ->
                exact.firstOrNull { presets[it].stationId == id }?.let { return it }
            }
            return exact.first()
        }

        if (stationId.isNotBlank()) {
            val matches = presets.indices.filter { presets[it].stationId == stationId }
            if (matches.size == 1) return matches.first()
        }

        if (rdsConfirmed && pi > 0) {
            val matches = presets.indices.filter { index ->
                val preset = presets[index]
                preset.confirmed && preset.pi > 0 && samePi(preset.pi, pi) &&
                    (stationId.isBlank() || preset.stationId.isBlank() || preset.stationId == stationId)
            }
            if (matches.size == 1) return matches.first()
        }
        return -1
    }

    fun compatibleNames(first: FmStationEvidence, second: FmStationEvidence): Boolean {
        val left = normalizedName(first.name)
        val right = normalizedName(second.name)
        if (left.isBlank() || right.isBlank()) return true
        if (left == right) return true
        val compactLeft = left.replace(" ", "")
        val compactRight = right.replace(" ", "")
        if (compactLeft.length >= 4 && compactRight.contains(compactLeft)) return true
        if (compactRight.length >= 4 && compactLeft.contains(compactRight)) return true
        val firstResolved = resolvedStationId(first)
        val secondResolved = resolvedStationId(second)
        return firstResolved != null && firstResolved == secondResolved
    }

    fun usefulName(value: String): Boolean {
        val normalized = normalizedName(value)
        if (normalized.isBlank()) return false
        if (normalized.matches(Regex("fm \\d{2,3}(?: \\d)?(?: mhz)?"))) return false
        return normalized.replace(" ", "") !in setOf(
            "fm",
            "radio",
            "antennenempfang",
            "physischerantennenempfang",
        )
    }

    private fun resolvedStationId(evidence: FmStationEvidence): String? {
        evidence.stationId.trim().takeIf(String::isNotBlank)?.let { return it }
        return FmStationIdentity.resolve(
            rawPs = evidence.name,
            storedName = evidence.name,
            frequencies = evidence.frequencies,
            pi = evidence.pi,
            ecc = null,
        ).takeIf { it.recognized }?.stableId
    }

    private fun samePi(first: Int, second: Int): Boolean =
        (first and 0xffff) == (second and 0xffff)

    private fun normalizedName(value: String): String {
        val transliterated =
            value.lowercase(Locale.GERMAN)
                .replace("ä", "ae")
                .replace("ö", "oe")
                .replace("ü", "ue")
                .replace("ß", "ss")
        return Normalizer.normalize(transliterated, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace("&", " und ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
    }
}

data class FmRdsSample(
    val ps: String,
    val pi: Int,
    val ecc: String = "",
    val pty: Int = 0,
    val tp: Boolean = false,
)

data class FmFreshRdsObservation(
    val ps: String = "",
    val pi: Int = 0,
    val ecc: String = "",
    val pty: Int = 0,
    val tp: Boolean = false,
    val confirmed: Boolean = false,
)

/** Requires repeated post-tune evidence and never falls back to the previous frequency. */
object FmRdsFreshness {
    fun consolidate(samples: Collection<FmRdsSample>): FmFreshRdsObservation {
        if (samples.isEmpty()) return FmFreshRdsObservation()
        val list = samples.toList()
        val stablePi =
            list.asSequence()
                .map { it.pi and 0xffff }
                .filter { it > 0 }
                .groupingBy { it }
                .eachCount()
                .filterValues { it >= 2 }
                .maxByOrNull { it.value }
                ?.key ?: 0

        val stableNameGroup =
            list.asSequence()
                .filter { FmStationAssociation.usefulName(it.ps) }
                .groupBy { normalize(it.ps) }
                .filterValues { it.size >= 2 }
                .maxWithOrNull(compareBy<Map.Entry<String, List<FmRdsSample>>> { it.value.size }.thenBy { it.key.length })
        val stableName = stableNameGroup?.value?.lastOrNull()?.ps?.trim().orEmpty()
        val confirmed = stablePi > 0 || stableName.isNotBlank()
        if (!confirmed) return FmFreshRdsObservation()

        val matching = list.filter { sample ->
            (stablePi > 0 && (sample.pi and 0xffff) == stablePi) ||
                (stableNameGroup != null && normalize(sample.ps) == stableNameGroup.key)
        }
        val last = matching.lastOrNull() ?: list.last()
        return FmFreshRdsObservation(
            ps = stableName,
            pi = stablePi,
            ecc = matching.asReversed().firstOrNull { it.ecc.isNotBlank() }?.ecc.orEmpty(),
            pty = last.pty,
            tp = last.tp,
            confirmed = true,
        )
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value.lowercase(Locale.GERMAN), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}
