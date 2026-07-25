package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RadioFavoriteNavigationTest {
    private val stations =
        listOf(
            RadioStation("broken-before", "Broken Before", "http://invalid/before"),
            RadioStation("one", "Favorite One", "http://valid/one"),
            RadioStation("two", "Favorite Two", "http://valid/two"),
            RadioStation("broken-after", "Broken After", "http://invalid/after"),
        )

    @Test
    fun nextAndPreviousUsePersistedOrder() {
        assertEquals("two", radioFavoriteNeighbor(stations, stations[1].mediaId, 1)?.uuid)
        assertEquals("one", radioFavoriteNeighbor(stations, stations[2].mediaId, -1)?.uuid)
    }

    @Test
    fun navigationStopsAtOrderEdges() {
        assertNull(radioFavoriteNeighbor(stations, stations.first().mediaId, -1))
        assertNull(radioFavoriteNeighbor(stations, stations.last().mediaId, 1))
    }

    @Test
    fun unknownOrInvalidDirectionDoesNothing() {
        assertNull(radioFavoriteNeighbor(stations, "radio:missing", 1))
        assertNull(radioFavoriteNeighbor(stations, stations[1].mediaId, 0))
    }
}
