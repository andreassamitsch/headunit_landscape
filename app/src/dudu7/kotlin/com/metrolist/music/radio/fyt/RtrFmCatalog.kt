package com.metrolist.music.radio.fyt

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.text.Normalizer
import java.util.Locale
import kotlin.math.PI
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sqrt
import kotlin.math.tan

data class FmGeoPoint(
    val latitude: Double,
    val longitude: Double,
    val accuracyMeters: Float = Float.NaN,
    val timestamp: Long = 0L,
)

data class RtrCoverageBounds(
    val south: Double,
    val west: Double,
    val north: Double,
    val east: Double,
) {
    fun contains(point: FmGeoPoint): Boolean =
        point.latitude in south..north && point.longitude in west..east
}

data class RtrFmStation(
    val id: String,
    val program: String,
    val broadcaster: String,
    val stationName: String,
    val stationLocation: String,
    val stateCode: String,
    val latitude: Double,
    val longitude: Double,
    val frequency: Float,
    val powerKw: Double,
    val pi: Int,
    val coverageCode: String,
    val coverageName: String,
    val coverageImageUrl: String,
    val coverageBounds: RtrCoverageBounds?,
) {
    val stableProgramId: String
        get() = "rtr:${RtrFmText.key(program)}"
}

data class RtrCatalogSnapshot(
    val stations: List<RtrFmStation>,
    val parsedAt: Long,
)

data class RtrFmMatch(
    val stableId: String,
    val canonicalName: String,
    val confidence: Int,
    val score: Int,
    val source: String,
    val stationSite: String,
    val coverageCode: String,
    val coverageName: String,
    val coverageStrength: Int,
    val distanceKm: Double?,
    val frequencies: List<Float>,
)

data class RtrAfPrediction(
    val frequency: Float,
    val coverageStrength: Int,
    val distanceKm: Double?,
    val score: Int,
    val source: String,
)

object RtrFmCatalogParser {
    private val json = Json { ignoreUnknownKeys = true }

    fun parse(payload: String, parsedAt: Long = System.currentTimeMillis()): RtrCatalogSnapshot {
        val outer = json.parseToJsonElement(payload).jsonObject
        val programs = embeddedArray(outer["programs"])
        val boundsByCode =
            embeddedArray(outer["bounds"])
                .mapNotNull { element ->
                    val row = element.jsonObject
                    val code = row.string("name")
                    val bounds = parseBounds(row.string("rtr_bounds"))
                    if (code.isBlank() || bounds == null) null else code to bounds
                }.toMap()

        val stations =
            programs.mapNotNull { element ->
                val row = element.jsonObject
                if (!row.string("rtr_programm_typ").equals("UKW", ignoreCase = true)) return@mapNotNull null
                val frequency = row.string("rtr_funkst_frequenz").decimalOrNull()?.toFloat() ?: return@mapNotNull null
                if (frequency !in 87.5f..108.0f) return@mapNotNull null
                val latitude = row.string("rtr_funkst_nord").decimalOrNull() ?: return@mapNotNull null
                val longitude = row.string("rtr_funkst_ost").decimalOrNull() ?: return@mapNotNull null
                val program = row.string("rtr_programm").trim()
                if (program.isBlank()) return@mapNotNull null
                val code = row.string("rtr_gebiet_code").trim()
                val jsonPath = row.string("rtr_json").trim()
                RtrFmStation(
                    id = row.string("id").ifBlank { "${RtrFmText.key(program)}_${(frequency * 10).roundToInt()}_${latitude}_${longitude}" },
                    program = program,
                    broadcaster = row.string("rtr_veranstalter_name"),
                    stationName = row.string("rtr_funkst_name"),
                    stationLocation = row.string("rtr_funkst_standort"),
                    stateCode = row.string("rtr_funkst_bundesland"),
                    latitude = latitude,
                    longitude = longitude,
                    frequency = frequency,
                    powerKw = row.string("rtr_funkst_leistung_kw").decimalOrNull() ?: 0.0,
                    pi = parseExactPi(row.string("rtr_funkst_rds")),
                    coverageCode = code,
                    coverageName = row.string("rtr_gebiet_name"),
                    coverageImageUrl = coverageImageUrl(jsonPath),
                    coverageBounds = boundsByCode[code],
                )
            }

        return RtrCatalogSnapshot(
            stations = stations,
            parsedAt = parsedAt,
        )
    }

    private fun embeddedArray(element: JsonElement?): JsonArray {
        if (element == null) return JsonArray(emptyList())
        return when (element) {
            is JsonArray -> element
            is JsonPrimitive -> {
                val embedded = element.contentOrNull.orEmpty()
                if (embedded.isBlank()) JsonArray(emptyList()) else json.parseToJsonElement(embedded).jsonArray
            }
            else -> JsonArray(emptyList())
        }
    }

    private fun parseBounds(value: String): RtrCoverageBounds? {
        if (value.isBlank()) return null
        return runCatching {
            val array = json.parseToJsonElement(value).jsonArray
            val southWest = array.getOrNull(0)?.jsonArray ?: return null
            val northEast = array.getOrNull(1)?.jsonArray ?: return null
            RtrCoverageBounds(
                south = southWest.getOrNull(0)?.jsonPrimitive?.doubleOrNull ?: return null,
                west = southWest.getOrNull(1)?.jsonPrimitive?.doubleOrNull ?: return null,
                north = northEast.getOrNull(0)?.jsonPrimitive?.doubleOrNull ?: return null,
                east = northEast.getOrNull(1)?.jsonPrimitive?.doubleOrNull ?: return null,
            )
        }.getOrNull()
    }

    private fun JsonObject.string(name: String): String =
        (get(name) as? JsonPrimitive)?.contentOrNull.orEmpty()

    private fun String.decimalOrNull(): Double? = trim().replace(',', '.').toDoubleOrNull()

    private fun parseExactPi(value: String): Int =
        value.trim().takeIf { it.matches(Regex("[0-9A-Fa-f]{4}")) }?.toIntOrNull(16) ?: 0

    private fun coverageImageUrl(path: String): String {
        if (path.isBlank()) return ""
        val png = if (path.endsWith(".json", ignoreCase = true)) path.dropLast(5) + ".png" else path
        return when {
            png.startsWith("https://") -> png
            png.startsWith("http://") -> png.replaceFirst("http://", "https://")
            png.startsWith("/") -> "https://senderkataster.rtr.at$png"
            else -> "https://senderkataster.rtr.at/$png"
        }
    }
}

object RtrFmMatcher {
    private data class ScoredStation(
        val station: RtrFmStation,
        val score: Int,
        val coverageStrength: Int,
        val distanceKm: Double?,
        val nameScore: Int,
        val piExact: Boolean,
    )

    fun candidateCoverageCodes(
        snapshot: RtrCatalogSnapshot,
        frequency: Float,
        rawPs: String,
        storedName: String?,
        pi: Int,
        location: FmGeoPoint?,
        limit: Int = 5,
    ): List<String> =
        scoreStations(snapshot, frequency, rawPs, storedName, pi, location, emptyMap())
            .asSequence()
            .map { it.station.coverageCode }
            .filter(String::isNotBlank)
            .distinct()
            .take(limit)
            .toList()

    fun resolve(
        snapshot: RtrCatalogSnapshot,
        frequency: Float,
        rawPs: String,
        storedName: String?,
        pi: Int,
        location: FmGeoPoint?,
        coverageStrengths: Map<String, Int> = emptyMap(),
    ): RtrFmMatch? {
        val scored = scoreStations(snapshot, frequency, rawPs, storedName, pi, location, coverageStrengths)
        if (scored.isEmpty()) return null

        val groups =
            scored.groupBy { it.station.stableProgramId }
                .map { (stableId, entries) ->
                    val best = entries.maxBy { it.score }
                    val frequencies =
                        snapshot.stations.asSequence()
                            .filter { it.stableProgramId == stableId }
                            .map { it.frequency }
                            .distinctBy { (it * 10f).roundToInt() }
                            .sorted()
                            .toList()
                    Triple(stableId, best, frequencies)
                }.sortedByDescending { it.second.score }

        val winner = groups.first()
        val runnerUp = groups.getOrNull(1)
        val best = winner.second
        val margin = best.score - (runnerUp?.second?.score ?: 0)
        val reliable =
            best.score >= 175 &&
                (best.piExact || best.nameScore >= 70 || best.coverageStrength >= 2 ||
                    (best.distanceKm != null && best.distanceKm <= 45.0 && margin >= 25))
        if (!reliable) return null

        val confidence =
            (40 + (best.score - 150).coerceIn(0, 45) +
                if (margin >= 40) 10 else if (margin >= 20) 5 else 0 +
                if (best.piExact) 10 else 0).coerceIn(0, 100)

        return RtrFmMatch(
            stableId = winner.first,
            canonicalName = best.station.program,
            confidence = confidence,
            score = best.score,
            source = buildString {
                append("RTR Frequenzbuch")
                if (location != null) append(" + GPS")
                if (best.coverageStrength > 0) append(" + Versorgungsprognose")
                if (best.piExact) append(" + PI")
            },
            stationSite = best.station.stationName.ifBlank { best.station.stationLocation },
            coverageCode = best.station.coverageCode,
            coverageName = best.station.coverageName,
            coverageStrength = best.coverageStrength,
            distanceKm = best.distanceKm,
            frequencies = winner.third,
        )
    }

    fun candidateCoverageCodesForProgram(
        snapshot: RtrCatalogSnapshot,
        stableId: String,
        location: FmGeoPoint?,
        limit: Int = 8,
    ): List<String> =
        snapshot.stations.asSequence()
            .filter { it.stableProgramId == stableId }
            .map { station -> station to location?.let { haversineKm(it.latitude, it.longitude, station.latitude, station.longitude) } }
            .sortedBy { it.second ?: 0.0 }
            .map { it.first.coverageCode }
            .filter(String::isNotBlank)
            .distinct()
            .take(limit)
            .toList()

    fun alternatives(
        snapshot: RtrCatalogSnapshot,
        match: RtrFmMatch,
        currentFrequency: Float,
        location: FmGeoPoint?,
        coverageStrengths: Map<String, Int> = emptyMap(),
    ): List<RtrAfPrediction> =
        snapshot.stations.asSequence()
            .filter { it.stableProgramId == match.stableId }
            .filter { kotlin.math.abs(it.frequency - currentFrequency) >= 0.05f }
            .groupBy { (it.frequency * 10f).roundToInt() }
            .map { (_, stations) ->
                stations.map { station ->
                    val distance = location?.let { haversineKm(it.latitude, it.longitude, station.latitude, station.longitude) }
                    val coverage = coverageStrengths[station.coverageCode] ?: 0
                    val score = coverage * 100 + distanceScore(distance) + powerScore(station.powerKw)
                    RtrAfPrediction(
                        frequency = station.frequency,
                        coverageStrength = coverage,
                        distanceKm = distance,
                        score = score,
                        source = when {
                            coverage > 0 -> "RTR Versorgungsprognose $coverage/7"
                            distance != null -> "RTR Standort ${"%.0f".format(Locale.GERMAN, distance)} km"
                            else -> "RTR Frequenzbuch"
                        },
                    )
                }.maxBy { it.score }
            }.sortedWith(compareByDescending<RtrAfPrediction> { it.coverageStrength }.thenByDescending { it.score }.thenBy { it.frequency })

    private fun scoreStations(
        snapshot: RtrCatalogSnapshot,
        frequency: Float,
        rawPs: String,
        storedName: String?,
        pi: Int,
        location: FmGeoPoint?,
        coverageStrengths: Map<String, Int>,
    ): List<ScoredStation> {
        val names = listOf(rawPs, storedName.orEmpty()).filter(String::isNotBlank)
        return snapshot.stations.asSequence()
            .filter { kotlin.math.abs(it.frequency - frequency) < 0.06f }
            .map { station ->
                val exactPi = pi > 0 && station.pi > 0 && (pi and 0xffff) == (station.pi and 0xffff)
                val wrongPi = pi > 0 && station.pi > 0 && !exactPi
                val nameScore = names.maxOfOrNull { nameScore(it, station.program) } ?: 0
                val distance = location?.let { haversineKm(it.latitude, it.longitude, station.latitude, station.longitude) }
                val coverage = coverageStrengths[station.coverageCode] ?: 0
                val outsideKnownCoverage = location != null && station.coverageBounds?.contains(location) == true &&
                    station.coverageCode in coverageStrengths && coverage == 0
                val score = 145 + (if (exactPi) 170 else 0) + (if (wrongPi) -220 else 0) + nameScore +
                    distanceScore(distance) + powerScore(station.powerKw) + (if (coverage > 0) coverage * 20 else 0) +
                    (if (outsideKnownCoverage) -100 else 0)
                ScoredStation(station, score, coverage, distance, nameScore, exactPi)
            }.sortedByDescending { it.score }
            .toList()
    }

    private fun nameScore(observed: String, program: String): Int {
        val left = RtrFmText.normalize(observed)
        val right = RtrFmText.normalize(program)
        if (left.isBlank() || right.isBlank()) return 0
        if (left == right) return 120
        val compactLeft = left.replace(" ", "")
        val compactRight = right.replace(" ", "")
        if (compactLeft == compactRight) return 120
        if (compactRight.contains(compactLeft) && compactLeft.length >= 4) return 85
        if (compactLeft.contains(compactRight) && compactRight.length >= 4) return 75
        val leftTokens = left.split(' ').filter { it.length >= 3 }.toSet()
        val rightTokens = right.split(' ').filter { it.length >= 3 }.toSet()
        if (leftTokens.isEmpty() || rightTokens.isEmpty()) return 0
        return (leftTokens.intersect(rightTokens).size * 70 / max(leftTokens.size, rightTokens.size)).coerceAtMost(70)
    }

    private fun distanceScore(distanceKm: Double?): Int = when {
        distanceKm == null -> 0
        distanceKm <= 10.0 -> 70
        distanceKm <= 25.0 -> 60
        distanceKm <= 45.0 -> 48
        distanceKm <= 70.0 -> 32
        distanceKm <= 110.0 -> 16
        distanceKm <= 170.0 -> 4
        else -> -55
    }

    private fun powerScore(powerKw: Double): Int = when {
        powerKw >= 50.0 -> 20
        powerKw >= 10.0 -> 16
        powerKw >= 1.0 -> 11
        powerKw >= 0.1 -> 6
        else -> 1
    }

    internal fun haversineKm(firstLatitude: Double, firstLongitude: Double, secondLatitude: Double, secondLongitude: Double): Double {
        val earthRadiusKm = 6371.0088
        val firstLat = Math.toRadians(firstLatitude)
        val secondLat = Math.toRadians(secondLatitude)
        val deltaLat = secondLat - firstLat
        val deltaLon = Math.toRadians(secondLongitude - firstLongitude)
        val a = sin(deltaLat / 2).pow(2) + cos(firstLat) * cos(secondLat) * sin(deltaLon / 2).pow(2)
        return 2 * earthRadiusKm * asin(sqrt(a.coerceIn(0.0, 1.0)))
    }
}

object RtrCoverageProjection {
    private val colorsWeakToStrong = listOf(
        Triple(254, 217, 217), Triple(254, 181, 181), Triple(254, 145, 145),
        Triple(254, 108, 108), Triple(254, 72, 72), Triple(234, 0, 0), Triple(202, 0, 0),
    )

    fun pixelFor(bounds: RtrCoverageBounds, width: Int, height: Int, point: FmGeoPoint): Pair<Int, Int>? {
        if (width <= 0 || height <= 0 || !bounds.contains(point)) return null
        val xRatio = (point.longitude - bounds.west) / (bounds.east - bounds.west)
        val north = mercatorY(bounds.north)
        val south = mercatorY(bounds.south)
        val value = mercatorY(point.latitude)
        val yRatio = (north - value) / (north - south)
        val x = (xRatio * (width - 1)).roundToInt().coerceIn(0, width - 1)
        val y = (yRatio * (height - 1)).roundToInt().coerceIn(0, height - 1)
        return x to y
    }

    fun strengthFromArgb(argb: Int): Int {
        val alpha = (argb ushr 24) and 0xff
        if (alpha < 32) return 0
        val red = (argb ushr 16) and 0xff
        val green = (argb ushr 8) and 0xff
        val blue = argb and 0xff
        val nearest = colorsWeakToStrong.mapIndexed { index, color ->
            val distance = (red - color.first).toDouble().pow(2) + (green - color.second).toDouble().pow(2) +
                (blue - color.third).toDouble().pow(2)
            index + 1 to distance
        }.minBy { it.second }
        return if (nearest.second <= 55.0.pow(2)) nearest.first else 0
    }

    private fun mercatorY(latitude: Double): Double {
        val limited = latitude.coerceIn(-85.05112878, 85.05112878)
        val radians = limited * PI / 180.0
        return ln(tan(PI / 4.0 + radians / 2.0))
    }
}

internal object RtrFmText {
    fun key(value: String): String = normalize(value).replace(' ', '_').ifBlank { "unknown" }

    fun normalize(value: String): String {
        val transliterated = value.lowercase(Locale.GERMAN).replace("ä", "ae").replace("ö", "oe")
            .replace("ü", "ue").replace("ß", "ss")
        return Normalizer.normalize(transliterated, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "").replace("&", " und ")
            .replace(Regex("[^a-z0-9]+"), " ").trim()
    }
}
