package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class RadioFavoriteQueueTest {
    @Test
    fun `store updates replace stale URL without changing drag order`() {
        val aOld = RadioStation(uuid = "a", name = "A", streamUrl = "https://old/a")
        val bOld = RadioStation(uuid = "b", name = "B", streamUrl = "https://old/b")
        val aFresh = aOld.copy(streamUrl = "https://fresh/a")
        val bFresh = bOld.copy(streamUrl = "https://fresh/b")

        val merged = mergeSavedStationUpdates(listOf(bOld, aOld), listOf(aFresh, bFresh))

        assertEquals(listOf("b", "a"), merged.map { it.uuid })
        assertEquals("https://fresh/b", merged[0].streamUrl)
        assertEquals("https://fresh/a", merged[1].streamUrl)
    }

    @Test
    fun `fresh selected station replaces only its queue entry`() {
        val a = RadioStation(uuid = "a", name = "A", streamUrl = "https://old/a")
        val b = RadioStation(uuid = "b", name = "B", streamUrl = "https://old/b")
        val freshB = b.copy(streamUrl = "https://fresh/b")

        val result = replaceFavoriteStation(listOf(a, b), freshB)

        assertEquals(listOf("a", "b"), result.map { it.uuid })
        assertEquals("https://fresh/b", result[1].streamUrl)
    }
}
