package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7SyuRadioIpcTest {
    @Test
    fun `source claim matches observed NavRadio Syu main command`() {
        assertEquals(0, SYU_MAIN_MODULE)
        assertEquals(0, SYU_MAIN_COMMAND_SOURCE)
        assertTrue(SYU_RADIO_SOURCE_PAYLOAD.contentEquals(intArrayOf(1)))
    }

    @Test
    fun `diagnostic callback range includes known main callbacks`() {
        assertTrue(0 in SYU_MAIN_CALLBACK_CODES)
        assertTrue(12 in SYU_MAIN_CALLBACK_CODES)
        assertTrue(174 in SYU_MAIN_CALLBACK_CODES)
        SYU_KNOWN_MAIN_CALLBACKS.forEach { assertTrue(it in SYU_MAIN_CALLBACK_CODES) }
    }

    @Test
    fun `key candidates require exact 87 or 88 values`() {
        assertEquals(87, extractSyuMediaKeyCandidate(87, null, null))
        assertEquals(88, extractSyuMediaKeyCandidate(10, intArrayOf(2, 88), null))
        assertEquals(87, extractSyuMediaKeyCandidate(10, null, arrayOf("keyCode=87")))
        assertNull(extractSyuMediaKeyCandidate(10, intArrayOf(10750, 9190), arrayOf("87.5 MHz")))
    }

    @Test
    fun `unrelated callback values stay diagnostic only`() {
        assertNull(extractSyuMediaKeyCandidate(174, intArrayOf(1), arrayOf("radio source")))
        assertNull(extractSyuMediaKeyCandidate(26, intArrayOf(0, 10490), null))
    }
}
