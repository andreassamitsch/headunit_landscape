package com.metrolist.music.radio.fyt

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Resolves the official public programme name from RTR's MedienFrequenzbuch.
 * The Senderkataster remains responsible for coordinates and coverage maps.
 */
class RtrOfficialProgramIndex private constructor(
    private val byFrequency: Map<Int, List<Entry>>,
) {
    data class Entry(
        val publicName: String,
        val frequency: Float,
        val coverageCode: String,
        val pi: Int,
        val stationName: String,
        val stationLocation: String,
        val broadcaster: String,
        val latitude: Double?,
        val longitude: Double?,
    )

    fun resolve(
        frequency: Float,
        coverageCode: String,
        pi: Int,
        stationName: String,
        stationLocation: String,
        broadcaster: String,
        latitude: Double,
        longitude: Double,
    ): String? {
        val candidates = byFrequency[frequencyKey(frequency)].orEmpty()
        if (candidates.isEmpty()) return null
        val scored = candidates.map { entry ->
            var score = 0
            if (coverageCode.isNotBlank() && entry.coverageCode.equals(coverageCode, ignoreCase = true)) score += 150
            if (pi > 0 && entry.pi == pi) score += 100
            if (sameText(entry.stationName, stationName)) score += 70
            if (sameText(entry.stationLocation, stationLocation)) score += 45
            if (sameText(entry.broadcaster, broadcaster)) score += 35
            if (entry.latitude != null && entry.longitude != null &&
                abs(entry.latitude - latitude) <= 0.002 && abs(entry.longitude - longitude) <= 0.002
            ) score += 120
            entry to score
        }.sortedByDescending { it.second }
        val winner = scored.first()
        val runnerUp = scored.getOrNull(1)
        val margin = winner.second - (runnerUp?.second ?: 0)
        return winner.first.publicName.takeIf {
            it.isNotBlank() && winner.second >= 100 && (runnerUp == null || margin >= 25 || winner.first.publicName == runnerUp.first.publicName)
        }
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        private val EMPTY = RtrOfficialProgramIndex(emptyMap())

        fun parseOrEmpty(payload: String?): RtrOfficialProgramIndex {
            if (payload.isNullOrBlank()) return EMPTY
            return runCatching {
                val root = json.parseToJsonElement(payload).jsonObject
                val rows = root["data"]?.jsonArray ?: JsonArray(emptyList())
                val entries = rows.mapNotNull { element ->
                    val row = element.jsonObject
                    val publicName = row.string("programm_liste").trim()
                    val frequency = row.string("funkst_frequenz").decimalOrNull()?.toFloat() ?: return@mapNotNull null
                    if (publicName.isBlank() || frequency !in 87.5f..108.0f) return@mapNotNull null
                    Entry(
                        publicName = publicName,
                        frequency = frequency,
                        coverageCode = row.string("funkst_code").trim(),
                        pi = parsePi(row.string("funkst_rds")),
                        stationName = row.string("funkst_name"),
                        stationLocation = row.string("funkst_standort"),
                        broadcaster = row.string("veranstalter_name"),
                        latitude = row.string("funkst_nord").decimalOrNull(),
                        longitude = row.string("funkst_ost").decimalOrNull(),
                    )
                }
                RtrOfficialProgramIndex(entries.groupBy { frequencyKey(it.frequency) })
            }.getOrElse { EMPTY }
        }

        private fun frequencyKey(value: Float): Int = (value * 10f).roundToInt()
        private fun parsePi(value: String): Int =
            value.trim().takeIf { it.matches(Regex("[0-9A-Fa-f]{4}")) }?.toIntOrNull(16) ?: 0
        private fun sameText(first: String, second: String): Boolean =
            first.isNotBlank() && second.isNotBlank() && RtrFmText.key(first) == RtrFmText.key(second)
        private fun JsonObject.string(name: String): String =
            (get(name) as? JsonPrimitive)?.contentOrNull.orEmpty()
        private fun String.decimalOrNull(): Double? = trim().replace(',', '.').toDoubleOrNull()
    }
}
