package com.metrolist.music.radio.fyt

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
