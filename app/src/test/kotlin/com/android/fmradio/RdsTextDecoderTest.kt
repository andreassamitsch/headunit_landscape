package com.android.fmradio

import org.junit.Assert.assertEquals
import org.junit.Test
import java.nio.charset.StandardCharsets

class RdsTextDecoderTest {
    @Test
    fun utf8RadioTextKeepsGermanUmlauts() {
        val text = "Schritt für Schritt – Grüße äöü ÄÖÜ ß"

        assertEquals(text, RdsTextDecoder.decode(text.toByteArray(StandardCharsets.UTF_8)))
    }

    @Test
    fun latin1RadioTextFallsBackWithoutCorruption() {
        val text = "Grüße aus Österreich: äöü ÄÖÜ ß"

        assertEquals(text, RdsTextDecoder.decode(text.toByteArray(StandardCharsets.ISO_8859_1)))
    }

    @Test
    fun asciiAndRdsPaddingStayStable() {
        val bytes = "\u0000\u0001ANTENNE STEIERMARK\u000D".toByteArray(StandardCharsets.UTF_8)

        assertEquals("ANTENNE STEIERMARK", RdsTextDecoder.decode(bytes))
    }

    @Test
    fun firmwareNotSupportMarkerIsStillFiltered() {
        assertEquals("", RdsTextDecoder.decode("Not Support".toByteArray(StandardCharsets.UTF_8)))
    }
}
