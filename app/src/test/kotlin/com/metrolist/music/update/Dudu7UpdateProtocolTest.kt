package com.metrolist.music.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7UpdateProtocolTest {
    @Test
    fun `selects newest non-draft Dudu7 release with manifest`() {
        val json = """[
          {"tag_name":"other-v9","draft":false,"assets":[]},
          {"tag_name":"dudu7-v13.7.68","name":"13.7.68","draft":false,"prerelease":true,
           "body":"new notes","published_at":"2026-08-17T10:00:00Z","assets":[
             {"name":"dudu7-update.json","browser_download_url":"https://example/manifest"},
             {"name":"Metrolist.apk","browser_download_url":"https://example/apk"}
           ]},
          {"tag_name":"dudu7-v13.7.67","draft":false,"assets":[
             {"name":"dudu7-update.json","browser_download_url":"https://example/old"}
           ]}
        ]"""
        val result = selectDudu7Release(json)
        assertNotNull(result)
        assertEquals("dudu7-v13.7.68", result?.tag)
        assertEquals("https://example/manifest", result?.manifestUrl)
        assertEquals("https://example/apk", result?.assets?.get("Metrolist.apk"))
    }

    @Test
    fun `ignores draft or releases without signed manifest`() {
        val json = """[
          {"tag_name":"dudu7-v99","draft":true,"assets":[{"name":"dudu7-update.json","browser_download_url":"x"}]},
          {"tag_name":"dudu7-v98","draft":false,"assets":[]}
        ]"""
        assertNull(selectDudu7Release(json))
    }

    @Test
    fun `parses and normalizes release manifest`() {
        val manifest = parseDudu7UpdateManifest("""{
          "versionCode":1370077,
          "versionName":"13.7.68",
          "packageName":"com.metrolist.music.dudu7.debug",
          "signerSha256":"AA:BB:CC",
          "apkAsset":"Metrolist.apk",
          "sha256":"11 22 33"
        }""")
        assertEquals(1370077L, manifest.versionCode)
        assertEquals("aabbcc", manifest.signerSha256)
        assertEquals("112233", manifest.sha256)
    }

    @Test
    fun `version comparison uses versionCode only`() {
        assertTrue(isDudu7UpdateNewer(1370076, 1370077))
        assertFalse(isDudu7UpdateNewer(1370076, 1370076))
        assertFalse(isDudu7UpdateNewer(1370076, 1370000))
    }
}
