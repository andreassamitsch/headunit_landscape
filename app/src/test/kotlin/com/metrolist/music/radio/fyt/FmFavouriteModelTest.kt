package com.metrolist.music.radio.fyt

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class FmFavouriteModelTest {
    @Test
    fun `exact frequency wins over station fallback`() {
        val favourites = listOf(
            FmFavouriteRef("a", "station:oe1", 87.6f),
            FmFavouriteRef("b", "station:antenne_steiermark", 99.7f),
        )

        assertEquals(
            1,
            FmFavouriteModel.selectCurrentIndex(
                favourites = favourites,
                frequency = 99.7f,
                stationId = "station:oe1",
            ),
        )
    }

    @Test
    fun `station fallback keeps one favourite while frequency changes`() {
        val favourites = listOf(FmFavouriteRef("stable", "station:antenne_steiermark", 99.7f))

        assertEquals(
            0,
            FmFavouriteModel.selectCurrentIndex(
                favourites = favourites,
                frequency = 96.8f,
                stationId = "station:antenne_steiermark",
            ),
        )
    }

    @Test
    fun `unknown stations are unique by exact frequency`() {
        val favourites = listOf(
            FmFavouriteRef("a", "", 93.1f),
            FmFavouriteRef("b", "", 94.2f),
        )

        assertEquals(0, FmFavouriteModel.existingIndexForUpsert(favourites, 93.1f, ""))
        assertEquals(1, FmFavouriteModel.existingIndexForUpsert(favourites, 94.2f, ""))
        assertEquals(-1, FmFavouriteModel.existingIndexForUpsert(favourites, 107.8f, ""))
    }

    @Test
    fun `scan grouping requires the same nonblank RTR station id`() {
        assertTrue(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe1"))
        assertFalse(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe3"))
        assertFalse(FmFavouriteModel.shouldGroupScan("", ""))
    }

    @Test
    fun `legacy ids are deterministic but records stay distinct`() {
        val first = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val again = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val second = FmFavouriteModel.legacyId(1, 87.6f, "Ö1", "station:oe1")

        assertEquals(first, again)
        assertNotEquals(first, second)
    }
}
