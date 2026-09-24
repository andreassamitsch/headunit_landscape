package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Test

class Dudu7FmSessionNavigationTest {
    private val ids = linkedSetOf("antenne", "radio-stmk", "oe3")

    @Test
    fun `remembered favourite survives missing detection after AF change`() {
        assertEquals(
            "radio-stmk",
            Dudu7FmSessionNavigation.retainActiveId(
                validIds = ids,
                rememberedId = "radio-stmk",
                detectedId = null,
                fallbackId = "antenne",
            ),
        )
    }

    @Test
    fun `detected favourite is used when no remembered favourite exists`() {
        assertEquals(
            "oe3",
            Dudu7FmSessionNavigation.retainActiveId(
                validIds = ids,
                rememberedId = null,
                detectedId = "oe3",
                fallbackId = "antenne",
            ),
        )
    }

    @Test
    fun `next and previous wrap through ordered favourites`() {
        assertEquals(0, Dudu7FmSessionNavigation.adjacentIndex(3, 2, next = true))
        assertEquals(2, Dudu7FmSessionNavigation.adjacentIndex(3, 0, next = false))
    }

    @Test
    fun `first next from unresolved state selects first favourite only once`() {
        val first = Dudu7FmSessionNavigation.adjacentIndex(3, -1, next = true)
        val second = Dudu7FmSessionNavigation.adjacentIndex(3, first, next = true)
        assertEquals(0, first)
        assertEquals(1, second)
    }
}
