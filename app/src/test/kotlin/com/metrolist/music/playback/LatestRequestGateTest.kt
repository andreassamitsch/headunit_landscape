package com.metrolist.music.playback

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LatestRequestGateTest {
    @Test
    fun `only newest asynchronous queue request remains current`() {
        val gate = LatestRequestGate()
        val slowOldRequest = gate.issue()
        val newerRequest = gate.issue()

        assertFalse(gate.isCurrent(slowOldRequest))
        assertTrue(gate.isCurrent(newerRequest))
    }
}
