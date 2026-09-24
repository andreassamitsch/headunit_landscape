package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhysicalFmMediaKeyBridgeContractTest {
    @Test
    fun duduDirectionParserKeepsOnlySingleDownNextAndPrevious() {
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(0, 87, 0))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(0, 88, 0))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(1, 87, 0))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(0, 87, 1))
    }
}
