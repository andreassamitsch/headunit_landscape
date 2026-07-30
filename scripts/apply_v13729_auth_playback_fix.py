#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected source block not found in {path}: {old[:100]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"Expected exactly one source block in {path}, found {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"Expected one regex match in {path}, found {count}: {pattern[:120]!r}")
    path.write_text(updated, encoding="utf-8")


# 1) Never keep an empty or unusable authentication cookie in InnerTube.
inner_tube = ROOT / "innertube/src/main/kotlin/com/metrolist/innertube/InnerTube.kt"
replace_once(
    inner_tube,
    '''    var cookie: String? = null
        set(value) {
            field = value
            cookieMap = if (value == null) emptyMap() else parseCookieString(value)
        }
''',
    '''    var cookie: String? = null
        set(value) {
            val normalized = value?.trim()?.takeIf { it.isNotEmpty() }
            val parsed = normalized?.let(::parseCookieString).orEmpty()
            // An empty or partial token must never activate the authenticated request path.
            // InnerTube authentication requires SAPISID to create SAPISIDHASH.
            field = normalized?.takeIf { "SAPISID" in parsed }
            cookieMap = if (field == null) emptyMap() else parsed
        }
''',
)

# 2) Robust advanced-token parser shared by UI and tests.
token_parser = ROOT / "app/src/main/kotlin/com/metrolist/music/utils/AdvancedLoginToken.kt"
token_parser.write_text('''/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */
package com.metrolist.music.utils

import com.metrolist.innertube.utils.parseCookieString

internal data class AdvancedLoginToken(
    val cookie: String = "",
    val visitorData: String = "",
    val dataSyncId: String = "",
    val accountName: String = "",
    val accountEmail: String = "",
    val accountChannelHandle: String = "",
) {
    val hasValidCookie: Boolean
        get() = cookie.isNotBlank() && "SAPISID" in parseCookieString(cookie)
}

/**
 * Parses both the MetroList export template and tolerant variants copied through Android
 * clipboards (CRLF, leading bullets/spaces, Markdown asterisks/backticks, ':' instead of '=').
 * A raw cookie string containing SAPISID is also accepted.
 */
internal fun parseAdvancedLoginToken(input: String): AdvancedLoginToken {
    val values = linkedMapOf<String, String>()
    val linePattern = Regex(
        pattern = """^\\s*[-•]?\\s*`*\\**\\s*(INNERTUBE\\s+COOKIE|VISITOR\\s+DATA|DATASYNC\\s+ID|DATA\\s+SYNC\\s+ID|ACCOUNT\\s+NAME|ACCOUNT\\s+EMAIL|ACCOUNT\\s+CHANNEL\\s+HANDLE)\\s*\\**`*\\s*(?:=|:)\\s*(.*?)\\s*$""",
        option = RegexOption.IGNORE_CASE,
    )

    input.replace("\\r\\n", "\\n").replace('\\r', '\\n').lineSequence().forEach { rawLine ->
        val match = linePattern.matchEntire(rawLine) ?: return@forEach
        val normalizedLabel = match.groupValues[1]
            .uppercase()
            .replace(Regex("\\s+"), " ")
            .replace("DATA SYNC ID", "DATASYNC ID")
        val value = match.groupValues[2].trim().trim('`')
        values[normalizedLabel] = value
    }

    var cookie = values["INNERTUBE COOKIE"].orEmpty().trim()
    if (cookie.isBlank()) {
        val raw = input.trim().trim('`')
        if ("SAPISID" in parseCookieString(raw)) cookie = raw
    }

    return AdvancedLoginToken(
        cookie = cookie,
        visitorData = values["VISITOR DATA"].orEmpty().trim(),
        dataSyncId = values["DATASYNC ID"].orEmpty().trim().substringBefore("||"),
        accountName = values["ACCOUNT NAME"].orEmpty().trim(),
        accountEmail = values["ACCOUNT EMAIL"].orEmpty().trim(),
        accountChannelHandle = values["ACCOUNT CHANNEL HANDLE"].orEmpty().trim(),
    )
}
''', encoding="utf-8")

# 3) Account settings: tolerant parser and safe navigation order.
account_settings = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AccountSettings.kt"
replace_once(
    account_settings,
    'import com.metrolist.music.utils.reportException\n',
    'import com.metrolist.music.utils.reportException\nimport com.metrolist.music.utils.parseAdvancedLoginToken\n',
)
regex_replace_once(
    account_settings,
    r'''                    var cookie = ""\n                    var visitorDataValue = ""\n                    var dataSyncIdValue = ""\n                    var accountNameValue = ""\n                    var accountEmailValue = ""\n                    var accountChannelHandleValue = ""\n\n                    data\.split\("\\n"\)\.forEach \{.*?                    accountSettingsViewModel\.saveTokenAndRestart\(\n                        context = context,\n                        cookie = cookie,\n                        visitorData = visitorDataValue,\n                        dataSyncId = dataSyncIdValue,\n                        accountName = accountNameValue,\n                        accountEmail = accountEmailValue,\n                        accountChannelHandle = accountChannelHandleValue,\n                    \)''',
    '''                    val token = parseAdvancedLoginToken(data)
                    accountSettingsViewModel.saveTokenAndRestart(
                        context = context,
                        cookie = token.cookie,
                        visitorData = token.visitorData,
                        dataSyncId = token.dataSyncId,
                        accountName = token.accountName,
                        accountEmail = token.accountEmail,
                        accountChannelHandle = token.accountChannelHandle,
                    )''',
)
regex_replace_once(
    account_settings,
    r'''                isInputValid = \{ fullText ->\n                    // Extract the cookie value from the formatted template line,.*?                    cookieValue\.isNotEmpty\(\) && "SAPISID" in parseCookieString\(cookieValue\)\n                \},''',
    '''                isInputValid = { fullText ->
                    parseAdvancedLoginToken(fullText).hasValidCookie
                },''',
)
replace_once(
    account_settings,
    '''                    onClick = {
                        onClose()
                        if (isLoggedIn) {
                            navController.navigate("account")
                        } else {
                            navController.navigate("login")
                        }
                    }
''',
    '''                    onClick = {
                        val destination = if (isLoggedIn) "account" else "login"
                        // In the Dudu7 overlay, closing first disposes the navigation host and
                        // navigating afterwards can crash. Navigate while the controller is alive.
                        runCatching {
                            navController.navigate(destination) { launchSingleTop = true }
                        }.onSuccess {
                            onClose()
                        }.onFailure { error ->
                            Timber.e(error, "Failed to open account destination: $destination")
                            reportException(error)
                        }
                    }
''',
)

# 4) Token persistence: reject partial token, update live singleton and relaunch Activity safely
# without killing the process (which looked like an app crash on FYT/Dudu7).
account_vm = ROOT / "app/src/main/kotlin/com/metrolist/music/viewmodels/AccountSettingsViewModel.kt"
replace_once(
    account_vm,
    'import com.metrolist.music.App\n',
    'import com.metrolist.music.App\nimport com.metrolist.innertube.YouTube\nimport com.metrolist.innertube.utils.parseCookieString\n',
)
replace_once(
    account_vm,
    '''    ) {
        viewModelScope.launch(Dispatchers.IO) {
            val saved = context.safeDataStoreEdit { settings ->
                settings[InnerTubeCookieKey] = cookie
                settings[VisitorDataKey] = visitorData
                settings[DataSyncIdKey] = dataSyncId
                settings[AccountNameKey] = accountName
                settings[AccountEmailKey] = accountEmail
                settings[AccountChannelHandleKey] = accountChannelHandle
            }
''',
    '''    ) {
        val normalizedCookie = cookie.trim()
        if ("SAPISID" !in parseCookieString(normalizedCookie)) {
            Timber.e("saveTokenAndRestart: missing SAPISID; token not saved")
            return
        }
        val normalizedVisitorData = visitorData.trim()
        val normalizedDataSyncId = dataSyncId.trim().substringBefore("||")

        viewModelScope.launch(Dispatchers.IO) {
            val saved = context.safeDataStoreEdit { settings ->
                settings[InnerTubeCookieKey] = normalizedCookie
                settings[VisitorDataKey] = normalizedVisitorData
                settings[DataSyncIdKey] = normalizedDataSyncId
                settings[AccountNameKey] = accountName.trim()
                settings[AccountEmailKey] = accountEmail.trim()
                settings[AccountChannelHandleKey] = accountChannelHandle.trim()
            }
''',
)
replace_once(
    account_vm,
    '''            withContext(Dispatchers.Main) {
                val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
                intent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                context.startActivity(intent)
                Runtime.getRuntime().exit(0)
            }
''',
    '''            // Apply the new session immediately. A forced Runtime.exit(0) leaves some FYT
            // launchers on the previously visible app and looks exactly like a crash.
            YouTube.cookie = normalizedCookie
            YouTube.visitorData = normalizedVisitorData.takeIf { it.isNotBlank() }
            YouTube.dataSyncId = normalizedDataSyncId.takeIf { it.isNotBlank() }
            withContext(Dispatchers.Main) {
                val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
                if (intent != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    runCatching { context.startActivity(intent) }
                        .onFailure { Timber.e(it, "saveTokenAndRestart: safe relaunch failed") }
                } else {
                    Timber.w("saveTokenAndRestart: no launch intent; credentials remain active without relaunch")
                }
            }
''',
)

# 5) Web login: require a real SAPISID cookie and never kill the process after login.
login_screen = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/LoginScreen.kt"
replace_once(
    login_screen,
    'import com.metrolist.innertube.YouTube\n',
    'import com.metrolist.innertube.YouTube\nimport com.metrolist.innertube.utils.parseCookieString\n',
)
replace_once(
    login_screen,
    '''            val currentCookie = CookieManager.getInstance().getCookie("https://music.youtube.com").orEmpty()
            if (currentCookie.isBlank()) {
                Timber.d("Login: No YouTube Music cookie found on close, leaving login screen")
''',
    '''            val currentCookie = CookieManager.getInstance()
                .getCookie("https://music.youtube.com")
                .orEmpty()
                .trim()
            if ("SAPISID" !in parseCookieString(currentCookie)) {
                Timber.d("Login: No usable YouTube Music SAPISID cookie found, leaving login screen")
''',
)
replace_once(
    login_screen,
    '''                    withContext(Dispatchers.Main) {
                        val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
                        intent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                        context.startActivity(intent)
                        Runtime.getRuntime().exit(0)
                    }
''',
    '''                    withContext(Dispatchers.Main) {
                        val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
                        if (intent != null) {
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                            runCatching { context.startActivity(intent) }
                                .onFailure {
                                    Timber.e(it, "Login: safe relaunch failed; closing login screen")
                                    onClose()
                                }
                        } else {
                            Timber.w("Login: no launch intent; closing login screen without process exit")
                            onClose()
                        }
                    }
''',
)
replace_once(
    login_screen,
    '''                                CookieManager.getInstance().getCookie("https://music.youtube.com").orEmpty()
                                    .isNotBlank()
''',
    '''                                "SAPISID" in parseCookieString(
                                    CookieManager.getInstance().getCookie("https://music.youtube.com").orEmpty(),
                                )
''',
)

# 6) Playback resolution: valid login detection and a guaranteed fallback away from a stream URL
# that already failed on the real ExoPlayer GET.
yt_utils = ROOT / "app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt"
replace_once(
    yt_utils,
    'import com.metrolist.innertube.YouTube\n',
    'import com.metrolist.innertube.YouTube\nimport com.metrolist.innertube.utils.parseCookieString\n',
)
replace_once(
    yt_utils,
    '''        val isLoggedIn = YouTube.cookie != null
''',
    '''        val isLoggedIn = YouTube.cookie
            ?.let { cookie -> cookie.isNotBlank() && "SAPISID" in parseCookieString(cookie) }
            ?: false
''',
)
replace_once(
    yt_utils,
    '''            if (client.loginRequired && !isLoggedIn) {
''',
    '''            if (client == MAIN_CLIENT && webRemixFailedIds.contains(videoId)) {
                Timber.tag(logTag).d("Skipping WEB_REMIX because its real playback GET failed for $videoId")
                continue
            }

            if (client.loginRequired && !isLoggedIn) {
''',
)

# 7) IO_UNSPECIFIED on the real WEB_REMIX GET is the observed Dudu7 error (code 2000).
# Mark that client unusable for this media id, clear URL/cache and resolve through another client.
music_service = ROOT / "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
replace_once(
    music_service,
    '''        if (error.errorCode == PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS) {
            Timber.tag(TAG).d("IO error detected (${error.errorCode}), attempting recovery")
            handleGenericIOError(mediaId)
            return
        }

        if (dataStore.get(AutoSkipNextOnErrorKey, false)) {
''',
    '''        if (error.errorCode == PlaybackException.ERROR_CODE_IO_BAD_HTTP_STATUS) {
            Timber.tag(TAG).d("IO error detected (${error.errorCode}), attempting recovery")
            handleGenericIOError(mediaId)
            return
        }

        if (error.errorCode == PlaybackException.ERROR_CODE_IO_UNSPECIFIED &&
            currentStreamClient.value == "WEB_REMIX"
        ) {
            Timber.tag(TAG).d("WEB_REMIX IO_UNSPECIFIED detected; forcing another stream client")
            handleAuthenticatedStreamFailure(mediaId)
            return
        }

        if (dataStore.get(AutoSkipNextOnErrorKey, false)) {
''',
)
replace_once(
    music_service,
    '''    /**
     * Handles expired URL (403) errors by clearing caches and retrying.
     */
    private fun handleExpiredUrlError(mediaId: String?) {
''',
    '''    /**
     * Handles an authenticated WEB_REMIX stream that failed on the actual ExoPlayer GET with
     * IO_UNSPECIFIED. Unlike the cipher self-heal path this keeps WEB_REMIX disabled for this
     * media id so the retry is guaranteed to use a different client.
     */
    private fun handleAuthenticatedStreamFailure(mediaId: String?) {
        if (mediaId == null) {
            handleFinalFailure()
            return
        }

        incrementRetryCount(mediaId)
        songUrlCache.remove(mediaId)
        YTPlayerUtils.markWebRemixFailed(mediaId)
        runCatching { playerCache.removeResource(mediaId) }
            .onFailure { Timber.tag(TAG).w(it, "Could not clear player cache after authenticated stream failure") }

        retryJob?.cancel()
        retryJob = scope.launch {
            delay(RETRY_DELAY_MS)
            val currentIndex = player.currentMediaItemIndex
            if (currentIndex == C.INDEX_UNSET) {
                handleFinalFailure()
                return@launch
            }
            player.seekTo(currentIndex, player.currentPosition)
            player.prepare()
            Timber.tag(TAG).d("Retrying $mediaId with WEB_REMIX excluded")
        }
    }

    /**
     * Handles expired URL (403) errors by clearing caches and retrying.
     */
    private fun handleExpiredUrlError(mediaId: String?) {
''',
)

# 8) Version and regression tests.
build_gradle = ROOT / "app/build.gradle.kts"
replace_once(build_gradle, 'versionCode = 1370037\n        versionName = "13.7.28"', 'versionCode = 1370038\n        versionName = "13.7.29"')

test_file = ROOT / "app/src/test/kotlin/com/metrolist/music/utils/AdvancedLoginTokenTest.kt"
test_file.parent.mkdir(parents=True, exist_ok=True)
test_file.write_text('''package com.metrolist.music.utils

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
''', encoding="utf-8")

print("Applied Metrolist dudu7 13.7.29 authentication and playback fixes")
