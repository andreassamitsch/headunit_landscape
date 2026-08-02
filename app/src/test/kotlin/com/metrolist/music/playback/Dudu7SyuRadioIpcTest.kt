package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7SyuRadioIpcTest {
    @Test
    fun `source claim and module ids match observed Dudu7 protocol`() {
        assertEquals(0, SYU_MAIN_MODULE)
        assertEquals(1, SYU_RADIO_MODULE)
        assertEquals(10, SYU_STEER_MODULE)
        assertEquals(0, SYU_MAIN_COMMAND_SOURCE)
        assertEquals(195, SYU_MAIN_UPDATE_SOURCE_OWNER)
        assertTrue(SYU_RADIO_SOURCE_PAYLOAD.contentEquals(intArrayOf(1)))
        assertTrue(SYU_MAIN_CALLBACK_CODES.contentEquals(intArrayOf(195)))
    }

    @Test
    fun `radio command frequency payload is decoded`() {
        assertEquals(107.5f, extractSyuFmFrequency(intArrayOf(0, 10750), null, null))
        assertEquals(91.9f, extractSyuFmFrequency(intArrayOf(0, 9190), null, null))
        assertEquals(88.2f, extractSyuFmFrequency(null, null, arrayOf("FM 88,20")))
        assertEquals(99.1f, extractSyuFmFrequency(null, floatArrayOf(99.1f), null))
    }

    @Test
    fun `integer key codes cannot become fm frequencies`() {
        assertNull(decodeSyuFmInteger(87))
        assertNull(decodeSyuFmInteger(88))
        assertNull(decodeSyuFmInteger(100))
        assertEquals(88.0f, decodeSyuFmInteger(880))
        assertEquals(107.5f, decodeSyuFmInteger(10750))
    }

    @Test
    fun `non fm telemetry is rejected`() {
        assertNull(extractSyuFmFrequency(intArrayOf(0, 87, 88, 471), floatArrayOf(471.05005f), arrayOf("keyCode=87")))
        assertNull(extractSyuFmFrequency(intArrayOf(2024, 65536), null, arrayOf("2024.01.24")))
    }

    @Test
    fun `callback slots 87 and 88 are not treated as pressed keys`() {
        assertNull(extractSyuSteeringDirection(87, intArrayOf(0)))
        assertNull(extractSyuSteeringDirection(88, intArrayOf(0)))
        assertTrue(extractSyuSteeringDirection(87, intArrayOf(1)) == true)
        assertFalse(extractSyuSteeringDirection(88, intArrayOf(1))!!)
        assertTrue(extractSyuSteeringDirection(12, intArrayOf(87, 0)) == true)
        assertFalse(extractSyuSteeringDirection(12, intArrayOf(88, 0))!!)
    }

    @Test
    fun `external frequency direction handles clear direct and edge wrap moves`() {
        assertTrue(inferExternalFmDirection(99.1f, 100.0f) == true)
        assertFalse(inferExternalFmDirection(99.1f, 98.0f)!!)
        assertTrue(inferExternalFmDirection(107.9f, 87.7f) == true)
        assertFalse(inferExternalFmDirection(87.7f, 107.9f)!!)
        assertNull(inferExternalFmDirection(99.1f, 99.1f))
    }

    @Test
    fun `ambiguous large jumps use shortest cyclic search direction`() {
        assertTrue(inferExternalFmDirection(104.6f, 91.9f) == true)
        assertFalse(inferExternalFmDirection(91.9f, 104.6f)!!)
    }

    @Test
    fun `frequency text is never interpreted as a media key`() {
        assertEquals(88.2f, extractSyuFmFrequency(null, null, arrayOf("FM 88,20")))
        assertNull(extractSyuSteeringDirection(49, null))
    }

    @Test
    fun `sequential syu observations preserve one direction despite MetroList favourite changes`() {
        val anchor = SyuFmFrequencyAnchor()
        assertTrue(anchor.observe(92.4f, 1L).previousFrequency.isNaN())
        assertTrue(inferExternalFmDirection(anchor.observe(92.6f, 2L).previousFrequency, 92.6f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(95.4f, 3L).previousFrequency, 95.4f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(96.5f, 4L).previousFrequency, 96.5f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(98.7f, 5L).previousFrequency, 98.7f) == true)
    }

    @Test
    fun `redirect favourite tune preserves the vendor frequency anchor`() {
        val anchor = SyuFmFrequencyAnchor()
        val gate = SyuFmRedirectTuneGate()
        anchor.reset(92.4f, 1L)
        gate.expect(now = 2L, windowMs = 1_500L)
        assertTrue(gate.consume(3L))
        val observation = anchor.observe(92.6f, 4L)
        assertEquals(92.4f, observation.previousFrequency)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 92.6f) == true)
        assertFalse(gate.consume(5L))
    }

    @Test
    fun `manual tune establishes a new known baseline`() {
        val anchor = SyuFmFrequencyAnchor()
        val gate = SyuFmRedirectTuneGate()
        anchor.observe(104.3f, 1L)
        assertFalse(gate.consume(2L))
        assertEquals(104.3f, anchor.reset(87.6f, 2L))
        val observation = anchor.observe(89.5f, 3L)
        assertEquals(87.6f, observation.previousFrequency)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 89.5f) == true)
    }

    @Test
    fun `expired redirect expectation cannot suppress a later manual tune`() {
        val gate = SyuFmRedirectTuneGate()
        gate.expect(now = 100L, windowMs = 50L)
        assertFalse(gate.consume(151L))
    }

    @Test
    fun `syu wrap sequence remains forward`() {
        val anchor = SyuFmFrequencyAnchor()
        anchor.reset(107.5f, 1L)
        val observation = anchor.observe(88.2f, 2L)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 88.2f) == true)
    }

}
