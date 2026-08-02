package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FmFavouriteModelTest {
    private val favourites = listOf(
        FmFavouriteRef("antenne", "station:antenne_steiermark", 99.1f, 0xA902),
        FmFavouriteRef("oe3", "station:oe3", 99.5f, 0xA203),
        FmFavouriteRef("radio-stmk", "station:radio_steiermark", 95.4f, 0xA402),
    )

    @Test fun `exact frequency wins over station fallback`() {
        assertEquals(1, FmFavouriteModel.selectCurrentIndex(favourites, 99.5f, "station:antenne_steiermark"))
    }

    @Test fun `stable active id survives AF frequency changes`() {
        assertEquals(
            1,
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = "oe3",
                frequency = 107.0f,
                stationId = "",
                pi = 0,
                rdsConfirmed = false,
            ),
        )
    }

    @Test fun `confirmed unique PI restores current favourite`() {
        assertEquals(
            2,
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = null,
                frequency = 88.8f,
                stationId = "",
                pi = 0xA402,
                rdsConfirmed = true,
            ),
        )
    }

    @Test fun `missing active favourite falls back once then advances from remembered target`() {
        val firstTarget = FmFavouriteModel.adjacentIndex(favourites.size, -1, next = true)
        assertEquals(0, firstTarget)
        val secondCurrent = FmFavouriteModel.resolveCurrentIndex(
            favourites = favourites,
            activeId = favourites[firstTarget].id,
            frequency = 88.8f,
            stationId = "",
            pi = 0,
            rdsConfirmed = false,
        )
        assertEquals(1, FmFavouriteModel.adjacentIndex(favourites.size, secondCurrent, next = true))
    }

    @Test fun `forward and backward navigation wrap`() {
        assertEquals(1, FmFavouriteModel.adjacentIndex(3, 0, next = true))
        assertEquals(0, FmFavouriteModel.adjacentIndex(3, 2, next = true))
        assertEquals(2, FmFavouriteModel.adjacentIndex(3, 0, next = false))
    }

    @Test fun `unknown stations are unique by exact frequency`() {
        val unknown = listOf(FmFavouriteRef("a", "", 93.1f), FmFavouriteRef("b", "", 94.2f))
        assertEquals(0, FmFavouriteModel.existingIndexForUpsert(unknown, 93.1f, ""))
        assertEquals(1, FmFavouriteModel.existingIndexForUpsert(unknown, 94.2f, ""))
        assertEquals(-1, FmFavouriteModel.existingIndexForUpsert(unknown, 107.8f, ""))
    }

    @Test fun `scan grouping requires the same nonblank RTR station id`() {
        assertTrue(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe1"))
        assertFalse(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe3"))
        assertFalse(FmFavouriteModel.shouldGroupScan("", ""))
    }

    @Test fun `legacy ids are deterministic but records stay distinct`() {
        val first = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val again = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val second = FmFavouriteModel.legacyId(1, 87.6f, "Ö1", "station:oe1")
        assertEquals(first, again)
        assertNotEquals(first, second)
    }
    @org.junit.Test
    fun `active favourite id wins when two regional paths share one frequency`() {
        val favourites =
            listOf(
                FmFavouriteRef("home", "rtr:home", 99.7f, 0xA101),
                FmFavouriteRef("travel", "rtr:travel", 99.7f, 0xB202),
            )
        val index =
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = "travel",
                frequency = 99.7f,
                stationId = "rtr:home",
                pi = 0xA101,
                rdsConfirmed = true,
            )
        org.junit.Assert.assertEquals(1, index)
    }

}
