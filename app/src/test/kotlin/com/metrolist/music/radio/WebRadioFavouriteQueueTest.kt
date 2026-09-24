package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class WebRadioFavouriteQueueTest {
    private fun station(id: String, url: String = "https://example.invalid/$id") =
        RadioStation(uuid = id, name = id, streamUrl = url)

    @Test
    fun `selected station keeps its saved position`() {
        val one = station("one")
        val two = station("two")
        val three = station("three")
        val result = orderWebRadioFavourites(two, listOf(one, two, three))

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals(1, webRadioFavouriteStartIndex(two, result))
    }

    @Test
    fun `refreshed selected station replaces stale object at the same position`() {
        val stale = station("two", "https://old.invalid")
        val refreshed = station("two", "https://new.invalid")
        val result = orderWebRadioFavourites(
            refreshed,
            listOf(station("one"), stale, stale, station("three")),
        )

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals("https://new.invalid", result[1].streamUrl)
        assertEquals(1, webRadioFavouriteStartIndex(refreshed, result))
    }

    @Test
    fun `unsaved selected station is appended deterministically`() {
        val selected = station("three")
        val result = orderWebRadioFavourites(selected, listOf(station("one"), station("two")))

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals(2, webRadioFavouriteStartIndex(selected, result))
    }
}
