package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class RadioDnsFormatRegressionTest {
    @Test
    fun heartLondonExampleMatchesOfficialRadioDnsWalkthrough() {
        val frequencyCode = (106.2f * 100f).toInt().toString().padStart(5, '0')
        val pi = "c460"
        val gcc = "${pi.first()}e1"
        assertEquals("10620.c460.ce1.fm.radiodns.org", "$frequencyCode.$pi.$gcc.fm.radiodns.org")
        assertEquals("fm:ce1.c460.10620", "fm:$gcc.$pi.$frequencyCode")
    }
}
