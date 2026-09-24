package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RadioDnsLogoResolverTest {
    @Test
    fun buildsOfficialFmLookupAndBearer() {
        val identity = RadioDnsLogoResolver.buildFmIdentity(98.7f, 0xA902, "E0")!!
        assertEquals("09870.a902.ae0.fm.radiodns.org", identity.lookup)
        assertEquals("fm:ae0.a902.09870", identity.bearer)
    }

    @Test
    fun bearerAllowsOnlyOneFrequencyCodeTolerance() {
        assertTrue(RadioDnsLogoResolver.bearerMatches("fm:ae0.a902.09871", "fm:ae0.a902.09870"))
        assertFalse(RadioDnsLogoResolver.bearerMatches("fm:ae0.a903.09870", "fm:ae0.a902.09870"))
        assertFalse(RadioDnsLogoResolver.bearerMatches("fm:ae0.a902.09873", "fm:ae0.a902.09870"))
    }
}
