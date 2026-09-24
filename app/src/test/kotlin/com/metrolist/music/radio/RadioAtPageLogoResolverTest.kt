package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class RadioAtPageLogoResolverTest {
    @Test
    fun `oe24 relative jpeg including query parameters is resolved`() {
        val candidate =
            RadioAtPageLogoResolver.resolveFromHtml(
                html =
                    """
                    <html>
                      <head><title>oe24 RADIO | Live per Webradio hören</title></head>
                      <body>
                        <h1>oe24 RADIO</h1>
                        <img alt="oe24 RADIO" src="/175/oe24.jpeg?version=abc123&amp;format=original">
                      </body>
                    </html>
                    """.trimIndent(),
                pageUrl = "https://www.radio.at/s/oe24",
                slug = "oe24",
                expectedName = "oe24 RADIO",
            )

        assertEquals(
            "https://www.radio.at/175/oe24.jpeg?version=abc123&format=original",
            candidate?.url,
        )
        assertEquals(RadioLogoSource.RADIO_AT, candidate?.source)
    }

    @Test
    fun `exact station image wins over generic and related artwork`() {
        val candidate =
            RadioAtPageLogoResolver.resolveFromHtml(
                html =
                    """
                    <html>
                      <head>
                        <title>oe24 RADIO</title>
                        <meta property="og:image" content="/300/radio-logo.png">
                      </head>
                      <body>
                        <h1>oe24 RADIO</h1>
                        <img alt="oe24 RADIO Nr 1 Hits" src="/175/oe24nr1hits.jpeg?version=related">
                        <img alt="oe24 RADIO" src="/175/oe24.jpeg?version=station">
                      </body>
                    </html>
                    """.trimIndent(),
                pageUrl = "https://www.radio.at/s/oe24",
                slug = "oe24",
                expectedName = "oe24 RADIO",
            )

        assertEquals("https://www.radio.at/175/oe24.jpeg?version=station", candidate?.url)
    }

    @Test
    fun `absolute webp from matching srcset remains unchanged`() {
        val candidate =
            RadioAtPageLogoResolver.resolveFromHtml(
                html =
                    """
                    <html>
                      <head><title>oe24 RADIO</title></head>
                      <body>
                        <h1>oe24 RADIO</h1>
                        <picture>
                          <source srcset="https://cdn.example.test/175/oe24.webp?version=v2 175w">
                          <img alt="oe24 RADIO" src="/75/oe24.jpeg?version=v1">
                        </picture>
                      </body>
                    </html>
                    """.trimIndent(),
                pageUrl = "https://www.radio.at/s/oe24",
                slug = "oe24",
                expectedName = "oe24 RADIO",
            )

        assertTrue(candidate?.url.orEmpty().startsWith("https://"))
        assertTrue(candidate?.url.orEmpty().contains("oe24"))
    }

    @Test
    fun `mismatching station page is rejected`() {
        val candidate =
            RadioAtPageLogoResolver.resolveFromHtml(
                html =
                    """
                    <html>
                      <head><title>Radio Example</title></head>
                      <body>
                        <h1>Radio Example</h1>
                        <img alt="Radio Example" src="/175/example.jpeg">
                      </body>
                    </html>
                    """.trimIndent(),
                pageUrl = "https://www.radio.at/s/example",
                slug = "oe24",
                expectedName = "oe24 RADIO",
            )

        assertNull(candidate)
    }
}
