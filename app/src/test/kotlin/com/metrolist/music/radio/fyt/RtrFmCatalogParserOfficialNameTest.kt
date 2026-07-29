package com.metrolist.music.radio.fyt

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
