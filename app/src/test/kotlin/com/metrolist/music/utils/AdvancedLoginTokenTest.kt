package com.metrolist.music.utils

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AdvancedLoginTokenTest {
    private val cookie = "SAPISID=test-sapisid; SID=test-sid; HSID=test-hsid"

    @Test
    fun parsesMetroListTemplateAndTrimsValues() {
        val parsed = parseAdvancedLoginToken(
            """
              ***INNERTUBE COOKIE*** = $cookie
              ***VISITOR DATA*** = visitor-value
              ***DATASYNC ID*** = sync-value||ignored
              ***ACCOUNT NAME*** = Andrew
              ***ACCOUNT EMAIL*** = test@example.com
              ***ACCOUNT CHANNEL HANDLE*** = @andrew
            """.trimIndent(),
        )

        assertTrue(parsed.hasValidCookie)
        assertEquals(cookie, parsed.cookie)
        assertEquals("visitor-value", parsed.visitorData)
        assertEquals("sync-value", parsed.dataSyncId)
        assertEquals("Andrew", parsed.accountName)
        assertEquals("@andrew", parsed.accountChannelHandle)
    }

    @Test
    fun acceptsClipboardFormattingVariants() {
        val parsed = parseAdvancedLoginToken(
            """
              - **INNERTUBE COOKIE**: `$cookie`
              • **VISITOR DATA**: visitor
              **DATA SYNC ID**: sync
            """.trimIndent(),
        )
        assertTrue(parsed.hasValidCookie)
        assertEquals(cookie, parsed.cookie)
        assertEquals("visitor", parsed.visitorData)
        assertEquals("sync", parsed.dataSyncId)
    }

    @Test
    fun rejectsPartialExportWithoutCookie() {
        val parsed = parseAdvancedLoginToken(
            """
              ***INNERTUBE COOKIE*** =
              ***VISITOR DATA*** = visitor-only
              ***ACCOUNT NAME*** = Andrew
            """.trimIndent(),
        )
        assertFalse(parsed.hasValidCookie)
        assertEquals("", parsed.cookie)
    }
}
