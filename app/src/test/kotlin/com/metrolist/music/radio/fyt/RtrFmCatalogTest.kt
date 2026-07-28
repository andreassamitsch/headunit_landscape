package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RtrFmCatalogTest {
    @Test
    fun `parses embedded Senderkataster JSON and coverage bounds`() {
        val programs = """[{"id":"1","rtr_programm_typ":"UKW","rtr_programm":"Antenne Steiermark","rtr_veranstalter_name":"Antenne","rtr_funkst_name":"TEST Sender","rtr_funkst_standort":"Testberg","rtr_funkst_bundesland":"ST","rtr_funkst_ost":"15,2000","rtr_funkst_nord":"46,8000","rtr_funkst_frequenz":"99,7","rtr_funkst_leistung_kw":"1,5","rtr_funkst_rds":"A123","rtr_gebiet_code":"4711","rtr_gebiet_name":"Testgebiet","rtr_json":"/site/assets/files/1/4711.json"},{"id":"2","rtr_programm_typ":"DAB+","rtr_programm":"Nicht UKW"}]"""
        val bounds = """[{"name":"4711","rtr_bounds":"[[46.0,14.0],[48.0,17.0]]"}]"""
        val payload = """{"programs":${quote(programs)},"bounds":${quote(bounds)}}"""

        val parsed = RtrFmCatalogParser.parse(payload, parsedAt = 123L)

        assertEquals(1, parsed.stations.size)
        val station = parsed.stations.single()
        assertEquals("Antenne Steiermark", station.program)
        assertEquals(99.7f, station.frequency)
        assertEquals(0xA123, station.pi)
        assertEquals("https://senderkataster.rtr.at/site/assets/files/1/4711.png", station.coverageImageUrl)
        assertEquals(46.0, station.coverageBounds?.south ?: 0.0, 0.0001)
        assertEquals(123L, parsed.parsedAt)
    }

    @Test
    fun `GPS and official coverage disambiguate a short STMK RDS name`() {
        val point = FmGeoPoint(46.72, 15.25)
        val steiermark = station("st", "Antenne Steiermark", 99.7f, 46.75, 15.30, "stmk")
        val kaernten = station("ktn", "Antenne Kärnten", 99.7f, 46.62, 13.85, "ktn")
        val match = RtrFmMatcher.resolve(
            snapshot = RtrCatalogSnapshot(listOf(steiermark, kaernten), 1L),
            frequency = 99.7f,
            rawPs = "STMK",
            storedName = "ANTENNE",
            pi = 0,
            location = point,
            coverageStrengths = mapOf("stmk" to 5, "ktn" to 0),
        )

        assertNotNull(match)
        assertEquals("rtr:antenne_steiermark", match?.stableId)
        assertEquals("Antenne Steiermark", match?.canonicalName)
        assertTrue((match?.confidence ?: 0) >= 70)
    }

    @Test
    fun `does not invent a station when evidence remains ambiguous`() {
        val first = station("1", "Radio Eins", 100.0f, 47.0, 15.0, "a")
        val second = station("2", "Radio Zwei", 100.0f, 47.0, 15.0, "b")
        assertNull(
            RtrFmMatcher.resolve(
                RtrCatalogSnapshot(listOf(first, second), 1L),
                100.0f,
                "",
                null,
                0,
                null,
            ),
        )
    }

    @Test
    fun `coverage projection maps bounds and all seven RTR colours`() {
        val bounds = RtrCoverageBounds(46.0, 14.0, 48.0, 16.0)
        val center = RtrCoverageProjection.pixelFor(bounds, 1001, 1001, FmGeoPoint(47.0, 15.0))
        assertNotNull(center)
        assertTrue(center!!.first in 495..505)
        assertTrue(center.second in 490..510)
        val weak = (0xff shl 24) or (254 shl 16) or (217 shl 8) or 217
        val strong = (0xff shl 24) or (202 shl 16)
        assertEquals(1, RtrCoverageProjection.strengthFromArgb(weak))
        assertEquals(7, RtrCoverageProjection.strengthFromArgb(strong))
        assertEquals(0, RtrCoverageProjection.strengthFromArgb(0x00ffffff))
    }

    @Test
    fun `AF predictions rank official coverage before distance fallback`() {
        val current = station("a", "Antenne Steiermark", 99.7f, 46.8, 15.2, "current")
        val strong = station("b", "Antenne Steiermark", 106.8f, 47.3, 15.5, "strong")
        val weak = station("c", "Antenne Steiermark", 95.5f, 46.75, 15.25, "weak")
        val snapshot = RtrCatalogSnapshot(listOf(current, strong, weak), 1L)
        val match = RtrFmMatch(
            current.stableProgramId,
            current.program,
            90,
            300,
            "test",
            current.stationName,
            current.coverageCode,
            current.coverageName,
            5,
            1.0,
            listOf(95.5f, 99.7f, 106.8f),
        )
        val predictions = RtrFmMatcher.alternatives(
            snapshot,
            match,
            99.7f,
            FmGeoPoint(46.75, 15.25),
            mapOf("strong" to 7, "weak" to 2),
        )
        assertEquals(106.8f, predictions.first().frequency)
        assertEquals(7, predictions.first().coverageStrength)
    }

    private fun station(
        id: String,
        program: String,
        frequency: Float,
        latitude: Double,
        longitude: Double,
        coverageCode: String,
    ) = RtrFmStation(
        id,
        program,
        "",
        "Sender $id",
        "",
        "",
        latitude,
        longitude,
        frequency,
        1.0,
        0,
        coverageCode,
        coverageCode,
        "https://example.test/$coverageCode.png",
        RtrCoverageBounds(45.0, 9.0, 49.5, 17.5),
    )

    private fun quote(value: String): String = buildString {
        append('"')
        value.forEach { character ->
            when (character) {
                '\\' -> append("\\\\")
                '"' -> append("\\\"")
                '\n' -> append("\\n")
                '\r' -> append("\\r")
                '\t' -> append("\\t")
                else -> append(character)
            }
        }
        append('"')
    }
}
