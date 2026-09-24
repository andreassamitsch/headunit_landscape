package com.metrolist.music.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
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

    @Test
    fun `trusted signer with matching package manager evidence needs no fallback`() {
        val verification = evaluateDudu7SignerEvidence(
            manifestSignerSha256 = DUDU7_TRUSTED_SIGNER_SHA256,
            archiveSigners = setOf(DUDU7_TRUSTED_SIGNER_SHA256),
            installedSigners = setOf(DUDU7_TRUSTED_SIGNER_SHA256),
        )

        assertEquals(Dudu7SignerEvidenceState.MATCH, verification.archiveEvidence)
        assertEquals(Dudu7SignerEvidenceState.MATCH, verification.installedEvidence)
        assertFalse(verification.usesSystemInstallerFallback)
    }

    @Test
    fun `missing OEM signer evidence falls back to Android installer without rejecting update`() {
        val verification = evaluateDudu7SignerEvidence(
            manifestSignerSha256 = DUDU7_TRUSTED_SIGNER_SHA256,
            archiveSigners = emptySet(),
            installedSigners = emptySet(),
        )

        assertEquals(Dudu7SignerEvidenceState.MISSING, verification.archiveEvidence)
        assertEquals(Dudu7SignerEvidenceState.MISSING, verification.installedEvidence)
        assertTrue(verification.usesSystemInstallerFallback)
    }

    @Test
    fun `different OEM signer evidence is diagnostic and does not false-block`() {
        val verification = evaluateDudu7SignerEvidence(
            manifestSignerSha256 = DUDU7_TRUSTED_SIGNER_SHA256,
            archiveSigners = setOf("a".repeat(64)),
            installedSigners = setOf("b".repeat(64)),
        )

        assertEquals(Dudu7SignerEvidenceState.DIFFERENT, verification.archiveEvidence)
        assertEquals(Dudu7SignerEvidenceState.DIFFERENT, verification.installedEvidence)
        assertTrue(verification.usesSystemInstallerFallback)
    }

    @Test
    fun `release manifest signer must match pinned Dudu7 certificate`() {
        try {
            evaluateDudu7SignerEvidence(
                manifestSignerSha256 = "0".repeat(64),
                archiveSigners = emptySet(),
                installedSigners = emptySet(),
            )
            fail("untrusted manifest signer must be rejected")
        } catch (error: IllegalStateException) {
            assertTrue(error.message.orEmpty().contains("vertrauenswürdigen Dudu7-Signer"))
        }
    }
}
