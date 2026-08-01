package com.metrolist.music.playback

import org.junit.After
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class Dudu7FmSessionOwnershipTest {
    @Before
    fun resetBefore() {
        Dudu7FmSessionOwnership.release()
    }

    @After
    fun resetAfter() {
        Dudu7FmSessionOwnership.release()
    }

    @Test
    fun `claim is visible before tuner activation`() {
        assertFalse(Dudu7FmSessionOwnership.claimed.value)
        assertTrue(Dudu7FmSessionOwnership.claim())
        assertTrue(Dudu7FmSessionOwnership.claimed.value)
    }

    @Test
    fun `release without prior claim keeps normal player ownership`() {
        assertFalse(Dudu7FmSessionOwnership.release())
        assertFalse(Dudu7FmSessionOwnership.claimed.value)
    }

    @Test
    fun `claim and release are idempotent`() {
        assertTrue(Dudu7FmSessionOwnership.claim())
        assertFalse(Dudu7FmSessionOwnership.claim())
        assertTrue(Dudu7FmSessionOwnership.release())
        assertFalse(Dudu7FmSessionOwnership.release())
        assertFalse(Dudu7FmSessionOwnership.claimed.value)
    }
}
