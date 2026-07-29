from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Expected anchor not found in {path}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


catalog = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmCatalog.kt"
replace(
    catalog,
    "fun parse(payload: String, parsedAt: Long = System.currentTimeMillis()): RtrCatalogSnapshot {\n        val outer = json.parseToJsonElement(payload).jsonObject",
    "fun parse(\n        payload: String,\n        parsedAt: Long = System.currentTimeMillis(),\n        officialPayload: String? = null,\n    ): RtrCatalogSnapshot {\n        val outer = json.parseToJsonElement(payload).jsonObject\n        val officialNames = RtrOfficialProgramIndex.parseOrEmpty(officialPayload)",
)
replace(
    catalog,
    '''                val rawProgram = row.string("rtr_programm").trim()
                if (rawProgram.isBlank()) return@mapNotNull null
                val program = RtrPublicProgramName.resolve(
                    rawProgram = rawProgram,
                    broadcaster = row.string("rtr_veranstalter_name"),
                    coverageName = row.string("rtr_gebiet_name"),
                )
                val code = row.string("rtr_gebiet_code").trim()
                val jsonPath = row.string("rtr_json").trim()
''',
    '''                val rawProgram = row.string("rtr_programm").trim()
                if (rawProgram.isBlank()) return@mapNotNull null
                val broadcaster = row.string("rtr_veranstalter_name")
                val stationName = row.string("rtr_funkst_name")
                val stationLocation = row.string("rtr_funkst_standort")
                val coverageName = row.string("rtr_gebiet_name")
                val code = row.string("rtr_gebiet_code").trim()
                val pi = parseExactPi(row.string("rtr_funkst_rds"))
                val program = officialNames.resolve(
                    frequency = frequency,
                    coverageCode = code,
                    pi = pi,
                    stationName = stationName,
                    stationLocation = stationLocation,
                    broadcaster = broadcaster,
                    latitude = latitude,
                    longitude = longitude,
                ) ?: RtrPublicProgramName.resolve(
                    rawProgram = rawProgram,
                    broadcaster = broadcaster,
                    coverageName = coverageName,
                )
                val jsonPath = row.string("rtr_json").trim()
''',
)
replace(catalog, 'broadcaster = row.string("rtr_veranstalter_name"),', 'broadcaster = broadcaster,')
replace(catalog, 'stationName = row.string("rtr_funkst_name"),', 'stationName = stationName,')
replace(catalog, 'stationLocation = row.string("rtr_funkst_standort"),', 'stationLocation = stationLocation,')
replace(catalog, 'pi = parseExactPi(row.string("rtr_funkst_rds")),', 'pi = pi,')
replace(catalog, 'coverageName = row.string("rtr_gebiet_name"),', 'coverageName = coverageName,')

repository = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"
replace(
    repository,
    'private val catalogFile = File(cacheDirectory, "senderkataster-programs.json")',
    'private val catalogFile = File(cacheDirectory, "senderkataster-programs.json")\n    private val officialCatalogFile = File(cacheDirectory, "medien-frequenzbuch.json")',
)
replace(
    repository,
    '''            snapshot?.let { current ->
                if (!force && isFresh(catalogFile, CATALOG_MAX_AGE_MS)) return@withLock current
            }
''',
    '''            snapshot?.let { current ->
                if (!force && catalogIsFresh()) return@withLock current
            }
''',
)
replace(
    repository,
    '''            if (!force && cached != null && isFresh(catalogFile, CATALOG_MAX_AGE_MS)) {
''',
    '''            if (!force && cached != null && catalogIsFresh()) {
''',
)
replace(
    repository,
    '''                val payload = downloadText(CATALOG_URL)
                val parsed = RtrFmCatalogParser.parse(payload, System.currentTimeMillis())
                require(parsed.stations.size >= MIN_EXPECTED_STATIONS) {
''',
    '''                val payload = downloadText(CATALOG_URL)
                val officialPayload = runCatching { downloadText(OFFICIAL_CATALOG_URL) }
                    .onFailure { Timber.tag(TAG).w(it, "Could not refresh official RTR frequency book") }
                    .getOrNull()
                    ?: officialCatalogFile.takeIf(File::isFile)?.readText()
                val parsed = RtrFmCatalogParser.parse(
                    payload = payload,
                    parsedAt = System.currentTimeMillis(),
                    officialPayload = officialPayload,
                )
                require(parsed.stations.size >= MIN_EXPECTED_STATIONS) {
''',
)
replace(
    repository,
    '''                atomicWrite(catalogFile, payload)
                catalogFile.setLastModified(parsed.parsedAt)
''',
    '''                atomicWrite(catalogFile, payload)
                if (!officialPayload.isNullOrBlank()) atomicWrite(officialCatalogFile, officialPayload)
                catalogFile.setLastModified(parsed.parsedAt)
                if (officialCatalogFile.isFile) officialCatalogFile.setLastModified(parsed.parsedAt)
''',
)
replace(
    repository,
    '''    private fun parseCatalog(payload: String): RtrCatalogSnapshot =
        RtrFmCatalogParser.parse(payload, catalogFile.lastModified().takeIf { it > 0L } ?: System.currentTimeMillis())
''',
    '''    private fun parseCatalog(payload: String): RtrCatalogSnapshot =
        RtrFmCatalogParser.parse(
            payload = payload,
            parsedAt = catalogFile.lastModified().takeIf { it > 0L } ?: System.currentTimeMillis(),
            officialPayload = officialCatalogFile.takeIf(File::isFile)?.readText(),
        )

    private fun catalogIsFresh(): Boolean =
        isFresh(catalogFile, CATALOG_MAX_AGE_MS) && isFresh(officialCatalogFile, CATALOG_MAX_AGE_MS)
''',
)
replace(
    repository,
    'private const val CATALOG_URL = "https://senderkataster.rtr.at/programs/"',
    'private const val CATALOG_URL = "https://senderkataster.rtr.at/programs/"\n        private const val OFFICIAL_CATALOG_URL = "https://data.rtr.at/api/v1/tables/MedienFrequenzbuch.json"',
)

index_file = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrOfficialProgramIndex.kt"
index_file.write_text(r'''package com.metrolist.music.radio.fyt

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
''', encoding="utf-8")

test_file = ROOT / "app/src/test/kotlin/com/metrolist/music/radio/fyt/RtrOfficialProgramIndexTest.kt"
test_file.write_text(r'''package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RtrOfficialProgramIndexTest {
    private val payload = """
        {
          "data": [
            {
              "programm_typ": "Analoger Hörfunk",
              "programm_liste": "Radio Steiermark",
              "veranstalter_name": "Österreichischer Rundfunk",
              "funkst_name": "ARNFELS",
              "funkst_standort": "Kreuzberg",
              "funkst_ost": "15.40",
              "funkst_nord": "46.68",
              "funkst_frequenz": "95,4",
              "funkst_rds": "A202",
              "funkst_code": "ORF_STMK_OE2"
            },
            {
              "programm_typ": "Analoger Hörfunk",
              "programm_liste": "Anderes Programm",
              "veranstalter_name": "Test",
              "funkst_name": "WIEN",
              "funkst_standort": "Test",
              "funkst_ost": "16.37",
              "funkst_nord": "48.20",
              "funkst_frequenz": "95,4",
              "funkst_rds": "B123",
              "funkst_code": "OTHER"
            }
          ]
        }
    """.trimIndent()

    @Test
    fun `official programm_liste wins for matching RTR coverage and frequency`() {
        val index = RtrOfficialProgramIndex.parseOrEmpty(payload)
        assertEquals(
            "Radio Steiermark",
            index.resolve(
                frequency = 95.4f,
                coverageCode = "ORF_STMK_OE2",
                pi = 0xA202,
                stationName = "Arnfels",
                stationLocation = "Kreuzberg",
                broadcaster = "Österreichischer Rundfunk",
                latitude = 46.68,
                longitude = 15.40,
            ),
        )
    }

    @Test
    fun `ambiguous frequency without matching identity is rejected`() {
        val index = RtrOfficialProgramIndex.parseOrEmpty(payload)
        assertNull(
            index.resolve(
                frequency = 95.4f,
                coverageCode = "",
                pi = 0,
                stationName = "",
                stationLocation = "",
                broadcaster = "",
                latitude = 47.0,
                longitude = 14.0,
            ),
        )
    }
}
''', encoding="utf-8")

parser_test = ROOT / "app/src/test/kotlin/com/metrolist/music/radio/fyt/RtrFmCatalogParserOfficialNameTest.kt"
parser_test.write_text(r'''package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Test

class RtrFmCatalogParserOfficialNameTest {
    @Test
    fun `parser prefers official programm_liste over senderkataster label`() {
        val senderkataster = """
            {
              "programs": [{
                "id": "1",
                "rtr_programm_typ": "UKW",
                "rtr_programm": "Ö2 Steiermark",
                "rtr_veranstalter_name": "Österreichischer Rundfunk",
                "rtr_funkst_name": "ARNFELS",
                "rtr_funkst_standort": "Kreuzberg",
                "rtr_funkst_bundesland": "ST",
                "rtr_funkst_nord": "46.68",
                "rtr_funkst_ost": "15.40",
                "rtr_funkst_frequenz": "95.4",
                "rtr_funkst_leistung_kw": "1.0",
                "rtr_funkst_rds": "A202",
                "rtr_gebiet_code": "ORF_STMK_OE2",
                "rtr_gebiet_name": "ORF Steiermark Ö2",
                "rtr_json": ""
              }],
              "bounds": []
            }
        """.trimIndent()
        val official = """
            {"data":[{
              "programm_liste":"Radio Steiermark",
              "veranstalter_name":"Österreichischer Rundfunk",
              "funkst_name":"ARNFELS",
              "funkst_standort":"Kreuzberg",
              "funkst_nord":"46.68",
              "funkst_ost":"15.40",
              "funkst_frequenz":"95.4",
              "funkst_rds":"A202",
              "funkst_code":"ORF_STMK_OE2"
            }]}
        """.trimIndent()

        val result = RtrFmCatalogParser.parse(senderkataster, officialPayload = official)
        assertEquals("Radio Steiermark", result.stations.single().program)
    }
}
''', encoding="utf-8")

print("RTR programm_liste integration applied")
