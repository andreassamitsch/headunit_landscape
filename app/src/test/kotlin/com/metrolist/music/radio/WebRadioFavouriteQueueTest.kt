package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class WebRadioFavouriteQueueTest {
    private fun station(id: String, url: String = "https://example.invalid/$id") =
        RadioStation(uuid = id, name = id, streamUrl = url)

    @Test
    fun `selected station is first and remaining favourites retain order`() {
        val one = station("one")
        val two = station("two")
        val three = station("three")

        assertEquals(
            listOf("two", "one", "three"),
            orderWebRadioFavourites(two, listOf(one, two, three)).map { it.uuid },
        )
    }

    @Test
    fun `refreshed selected station replaces stale saved object without duplicates`() {
        val stale = station("two", "https://old.invalid")
        val refreshed = station("two", "https://new.invalid")
        val result = orderWebRadioFavourites(refreshed, listOf(station("one"), stale, stale))

        assertEquals(listOf("two", "one"), result.map { it.uuid })
        assertEquals("https://new.invalid", result.first().streamUrl)
    }
}
