package com.metrolist.music.radio.fyt

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

/** Resolves public programme names from RTR's MedienFrequenzbuch without guessing ambiguous rows. */
class RtrOfficialProgramIndex private constructor(
    private val byFrequency: Map<Int, List<Entry>>,
    val recordCount: Int,
) {
    data class Entry(
        val publicName: String,
        val frequency: Float,
        val stationCode: String,
        val pi: Int,
        val stationName: String,
        val stationLocation: String,
        val broadcaster: String,
        val latitude: Double?,
        val longitude: Double?,
    )

    fun resolve(
        frequency: Float,
        stationCode: String,
        pi: Int,
        stationName: String,
        stationLocation: String,
        broadcaster: String,
        latitude: Double,
        longitude: Double,
    ): String? {
        val candidates = byFrequency[frequencyKey(frequency)].orEmpty()
        if (candidates.isEmpty()) return null

        val strategies = listOf(
            candidates.filter { stationCode.isNotBlank() && it.stationCode.equals(stationCode, ignoreCase = true) },
            candidates.filter { pi > 0 && it.pi == pi },
            candidates.filter { sameText(it.stationName, stationName) && sameText(it.stationLocation, stationLocation) },
            candidates.filter { sameText(it.stationName, stationName) || sameText(it.stationLocation, stationLocation) },
            candidates.filter {
                it.latitude != null && it.longitude != null &&
                    abs(it.latitude - latitude) <= 0.002 && abs(it.longitude - longitude) <= 0.002
            },
            candidates.filter { sameText(it.broadcaster, broadcaster) },
        )
        strategies.forEach { matches -> uniquePublicName(matches)?.let { return it } }
        return uniquePublicName(candidates.takeIf { it.size == 1 }.orEmpty())
    }

    private fun uniquePublicName(entries: List<Entry>): String? {
        if (entries.isEmpty()) return null
        val names = entries.map(Entry::publicName).filter(String::isNotBlank).distinctBy(RtrFmText::key)
        return names.singleOrNull()
    }

    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        private val EMPTY = RtrOfficialProgramIndex(emptyMap(), 0)

        fun parseOrEmpty(payload: String?): RtrOfficialProgramIndex {
            if (payload.isNullOrBlank()) return EMPTY
            return runCatching {
                val root = json.parseToJsonElement(payload).jsonObject
                val rows = root["data"]?.jsonArray ?: JsonArray(emptyList())
                val entries = rows.mapNotNull { element ->
                    val row = element.jsonObject
                    val rawProgram = row.string("programm_liste").trim()
                    val frequency = row.string("funkst_frequenz").decimalOrNull()?.toFloat() ?: return@mapNotNull null
                    if (rawProgram.isBlank() || frequency !in 87.5f..108.0f) return@mapNotNull null
                    val broadcaster = row.string("veranstalter_name")
                    val coverageName = row.string("versorgungsgebiet").ifBlank { row.string("gebiet_name") }
                    Entry(
                        publicName = RtrPublicProgramName.resolve(rawProgram, broadcaster, coverageName),
                        frequency = frequency,
                        stationCode = row.string("funkst_code").trim(),
                        pi = parsePi(row.string("funkst_rds")),
                        stationName = row.string("funkst_name"),
                        stationLocation = row.string("funkst_standort"),
                        broadcaster = broadcaster,
                        latitude = parseCoordinate(row.string("funkst_nord")),
                        longitude = parseCoordinate(row.string("funkst_ost")),
                    )
                }
                RtrOfficialProgramIndex(entries.groupBy { frequencyKey(it.frequency) }, entries.size)
            }.getOrElse { EMPTY }
        }

        internal fun parseCoordinate(value: String): Double? {
            val normalized = value.trim().uppercase(Locale.ROOT).replace(',', '.')
            normalized.toDoubleOrNull()?.let { return it }
            val prefixDirection = Regex("""^([0-9]{1,3})\s*([NSEW])\s*([0-9]{1,2})(?:\s+|[^0-9.]+)([0-9]{1,2}(?:\.[0-9]+)?)$""")
            val suffixDirection = Regex("""^([0-9]{1,3})(?:\s+|[^0-9.]+)([0-9]{1,2})(?:\s+|[^0-9.]+)([0-9]{1,2}(?:\.[0-9]+)?)\s*([NSEW])$""")
            val first = prefixDirection.matchEntire(normalized)
            val second = suffixDirection.matchEntire(normalized)
            val degrees: Double
            val minutes: Double
            val seconds: Double
            val direction: String
            when {
                first != null -> {
                    degrees = first.groupValues[1].toDouble()
                    direction = first.groupValues[2]
                    minutes = first.groupValues[3].toDouble()
                    seconds = first.groupValues[4].toDouble()
                }
                second != null -> {
                    degrees = second.groupValues[1].toDouble()
                    minutes = second.groupValues[2].toDouble()
                    seconds = second.groupValues[3].toDouble()
                    direction = second.groupValues[4]
                }
                else -> return null
            }
            if (minutes !in 0.0..<60.0 || seconds !in 0.0..<60.0) return null
            val decimal = degrees + minutes / 60.0 + seconds / 3600.0
            return if (direction == "S" || direction == "W") -decimal else decimal
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
