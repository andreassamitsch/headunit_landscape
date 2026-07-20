package com.metrolist.music.variant

import kotlin.test.Test
import kotlin.test.assertEquals

class Dudu7LayoutTest {
    @Test
    fun playerPaneWeightIsClampedToUsableRange() {
        assertEquals(0.32f, Dudu7Layout.sanitizePlayerPaneWeight(0.1f))
        assertEquals(0.50f, Dudu7Layout.sanitizePlayerPaneWeight(0.5f))
        assertEquals(0.68f, Dudu7Layout.sanitizePlayerPaneWeight(0.9f))
    }
}
