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
    fun `external frequency direction follows cyclic fm band`() {
        assertTrue(inferExternalFmDirection(99.1f, 107.5f) == true)
        assertFalse(inferExternalFmDirection(104.6f, 91.9f)!!)
        assertTrue(inferExternalFmDirection(107.9f, 87.7f) == true)
        assertFalse(inferExternalFmDirection(87.7f, 107.9f)!!)
        assertNull(inferExternalFmDirection(99.1f, 99.1f))
    }

    @Test
    fun `frequency text is never interpreted as a media key`() {
        assertEquals(88.2f, extractSyuFmFrequency(null, null, arrayOf("FM 88,20")))
        assertNull(extractSyuSteeringDirection(49, null))
    }
}
