#!/usr/bin/env python3
"""Apply the Dudu7-specific MetroList fixes before building.

The fork intentionally keeps the upstream source layout close to MetroList so future
updates remain manageable. This script applies a small, assertion-checked patch set:

* microphone button performs speech-to-text search instead of song recognition
* pre-warms YouTube cipher and PoToken helpers after startup
* starts playback with a smaller initial buffer
* skips the unreliable WEB_REMIX HEAD probe
* retries rejected/expired WEB_REMIX streams through fallback clients

It is idempotent and fails loudly when an upstream change invalidates a patch anchor.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path: str, old: str, new: str, marker: str | None = None) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")

    if marker and marker in text:
        print(f"[dudu7] already applied: {relative_path} ({marker})")
        return
    if old not in text:
        raise RuntimeError(f"Patch anchor not found in {relative_path}: {old[:120]!r}")

    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[dudu7] patched: {relative_path}")


SEARCH_SCREEN = "app/src/main/kotlin/com/metrolist/music/ui/screens/search/SearchScreen.kt"
MUSIC_SERVICE = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
YT_PLAYER_UTILS = "app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt"
CIPHER = "app/src/main/kotlin/com/metrolist/music/utils/cipher/CipherDeobfuscator.kt"
APP = "app/src/main/kotlin/com/metrolist/music/App.kt"
MANIFEST = "app/src/main/AndroidManifest.xml"

# --- Real voice search -------------------------------------------------------
replace_once(
    SEARCH_SCREEN,
    "package com.metrolist.music.ui.screens.search\n\nimport androidx.compose.foundation.layout.Box",
    """package com.metrolist.music.ui.screens.search

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Box""",
    marker="import android.speech.RecognizerIntent",
)
replace_once(
    SEARCH_SCREEN,
    "import androidx.compose.ui.platform.LocalFocusManager\nimport androidx.compose.ui.platform.LocalSoftwareKeyboardController",
    """import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController""",
    marker="import androidx.compose.ui.platform.LocalContext",
)
replace_once(
    SEARCH_SCREEN,
    "import java.net.URLEncoder\n",
    "import java.net.URLEncoder\nimport java.util.Locale\n",
    marker="import java.util.Locale",
)
replace_once(
    SEARCH_SCREEN,
    "    val database = LocalDatabase.current\n    val coroutineScope = rememberCoroutineScope()",
    """    val database = LocalDatabase.current
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()""",
    marker="val context = LocalContext.current",
)
replace_once(
    SEARCH_SCREEN,
    """    val onSearch: (String) -> Unit = { searchQuery -> handleSearch(searchQuery) }

    val onSearchFromSuggestion: (String) -> Unit = { searchQuery -> handleSearch(searchQuery) }
""",
    """    val voiceSearchLauncher =
        rememberLauncherForActivityResult(
            contract = ActivityResultContracts.StartActivityForResult(),
        ) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                result.data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull()
                    ?.trim()
                    ?.takeIf { it.isNotEmpty() }
                    ?.let { spokenQuery ->
                        query = TextFieldValue(spokenQuery)
                        handleSearch(spokenQuery)
                    }
            }
        }

    fun startVoiceSearch() {
        val intent =
            Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, Locale.getDefault().toLanguageTag())
                putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                putExtra(RecognizerIntent.EXTRA_PROMPT, \"Musik suchen\")
            }

        try {
            voiceSearchLauncher.launch(intent)
        } catch (_: ActivityNotFoundException) {
            Toast
                .makeText(context, \"Keine Spracherkennung auf diesem Gerät verfügbar\", Toast.LENGTH_LONG)
                .show()
        }
    }

    val onSearch: (String) -> Unit = { searchQuery -> handleSearch(searchQuery) }

    val onSearchFromSuggestion: (String) -> Unit = { searchQuery -> handleSearch(searchQuery) }
""",
    marker="val voiceSearchLauncher =",
)
replace_once(
    SEARCH_SCREEN,
    '                onClick = { navController.navigate("recognition") },',
    "                onClick = { startVoiceSearch() },",
    marker="onClick = { startVoiceSearch() }",
)

# Allow package visibility for speech recognizers on modern Android versions.
replace_once(
    MANIFEST,
    """    <queries>
        <intent>
            <action android:name="android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL" />
        </intent>""",
    """    <queries>
        <intent>
            <action android:name="android.speech.action.RECOGNIZE_SPEECH" />
        </intent>
        <intent>
            <action android:name="android.speech.RecognitionService" />
        </intent>
        <intent>
            <action android:name="android.media.action.DISPLAY_AUDIO_EFFECT_CONTROL_PANEL" />
        </intent>""",
    marker="android.speech.action.RECOGNIZE_SPEECH",
)

# --- Faster and more reliable playback --------------------------------------
replace_once(
    MUSIC_SERVICE,
    "import androidx.media3.exoplayer.DefaultRenderersFactory\n",
    "import androidx.media3.exoplayer.DefaultLoadControl\nimport androidx.media3.exoplayer.DefaultRenderersFactory\n",
    marker="import androidx.media3.exoplayer.DefaultLoadControl",
)
replace_once(
    MUSIC_SERVICE,
    """                .setMediaSourceFactory(createMediaSourceFactory())
                .setRenderersFactory(createRenderersFactory(eqProcessor, silenceProcessor))
                .setHandleAudioBecomingNoisy(true)""",
    """                .setMediaSourceFactory(createMediaSourceFactory())
                .setRenderersFactory(createRenderersFactory(eqProcessor, silenceProcessor))
                .setLoadControl(
                    DefaultLoadControl
                        .Builder()
                        .setBufferDurationsMs(50_000, 50_000, 750, 2_000)
                        .build(),
                )
                .setHandleAudioBecomingNoisy(true)""",
    marker="setBufferDurationsMs(50_000, 50_000, 750, 2_000)",
)
replace_once(
    MUSIC_SERVICE,
    """        // Clear the cached URL
        songUrlCache.remove(mediaId)
        Timber.tag(TAG).d("Cleared cached URL for $mediaId")
""",
    """        // Clear the cached URL and avoid retrying the same rejected WEB_REMIX URL.
        songUrlCache.remove(mediaId)
        YTPlayerUtils.markWebRemixFailed(mediaId)
        Timber.tag(TAG).d("Cleared cached URL for $mediaId; switching to fallback stream clients")
""",
    marker="switching to fallback stream clients",
)
replace_once(
    MUSIC_SERVICE,
    """            isFileNotFoundError(error) -> {
                Timber.tag(TAG).d("Cache file missing (ENOENT) detected, refreshing stream")
                handleFileNotFoundError(mediaId)
                return
            }

            !isNetworkConnected.value || isNetworkRelatedError(error) -> {""",
    """            isFileNotFoundError(error) -> {
                Timber.tag(TAG).d("Cache file missing (ENOENT) detected, refreshing stream")
                handleFileNotFoundError(mediaId)
                return
            }

            error.errorCode == PlaybackException.ERROR_CODE_REMOTE_ERROR -> {
                Timber.tag(TAG).d("Remote stream error detected, refreshing URL through fallback clients")
                handleExpiredUrlError(mediaId)
                return
            }

            !isNetworkConnected.value || isNetworkRelatedError(error) -> {""",
    marker="Remote stream error detected, refreshing URL through fallback clients",
)

replace_once(
    YT_PLAYER_UTILS,
    """    private val poTokenGenerator = PoTokenGenerator()

    private val MAIN_CLIENT: YouTubeClient = WEB_REMIX
""",
    """    private val poTokenGenerator = PoTokenGenerator()

    private val webRemixFailedIds =
        java.util.Collections.newSetFromMap(
            java.util.concurrent.ConcurrentHashMap<String, Boolean>(),
        )

    fun markWebRemixFailed(videoId: String) {
        webRemixFailedIds.add(videoId)
    }

    private const val POTOKEN_WARMUP_VIDEO_ID = "jNQXAC9IVRw"

    suspend fun prewarmPoToken() {
        val sessionId = YouTube.visitorData ?: return
        if (!MAIN_CLIENT.useWebPoTokens) return
        runCatching {
            poTokenGenerator.getWebClientPoToken(POTOKEN_WARMUP_VIDEO_ID, sessionId)
        }.onFailure { Timber.tag(TAG).w(it, "PoToken prewarm skipped: ${it.message}") }
    }

    private val MAIN_CLIENT: YouTubeClient = WEB_REMIX
""",
    marker="private val webRemixFailedIds =",
)
replace_once(
    YT_PLAYER_UTILS,
    """        val startIndex = when {
            isAgeRestricted -> 0
            else -> -1
        }
""",
    """        val startIndex = when {
            isAgeRestricted || videoId in webRemixFailedIds -> 0
            else -> -1
        }
""",
    marker="isAgeRestricted || videoId in webRemixFailedIds",
)
replace_once(
    YT_PLAYER_UTILS,
    """                if (clientIndex == STREAM_FALLBACK_CLIENTS.size - 1) {
                    /** skip [validateStatus] for last client */""",
    """                if (clientIndex == -1) {
                    // WEB_REMIX CDN URLs can reject HEAD while the actual range GET works.
                    // Let ExoPlayer perform the real request; a 403/410 is retried with fallbacks.
                    Timber.tag(logTag).d("Using WEB_REMIX without HEAD validation")
                    Timber.tag(TAG).i("Playback: client=${currentClient.clientName}, videoId=$videoId")
                    break
                }

                if (clientIndex == STREAM_FALLBACK_CLIENTS.size - 1) {
                    /** skip [validateStatus] for last client */""",
    marker="Using WEB_REMIX without HEAD validation",
)

replace_once(
    CIPHER,
    """    /**
     * Debug method: Get current state information
     */
""",
    """    /** Best-effort warm-up so the first song does not pay the WebView/player-JS cold start. */
    suspend fun prewarm() {
        runCatching { getOrCreateWebView(forceRefresh = false) }
            .onFailure { Timber.tag(TAG).w(it, "Cipher prewarm skipped: ${it.message}") }
    }

    /**
     * Debug method: Get current state information
     */
""",
    marker="suspend fun prewarm()",
)

replace_once(
    APP,
    "import com.metrolist.music.utils.CrashHandler\n",
    "import com.metrolist.music.utils.CrashHandler\nimport com.metrolist.music.utils.YTPlayerUtils\n",
    marker="import com.metrolist.music.utils.YTPlayerUtils",
)
replace_once(
    APP,
    "import kotlinx.coroutines.Dispatchers\n",
    "import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.delay\n",
    marker="import kotlinx.coroutines.delay",
)
replace_once(
    APP,
    """        applicationScope.launch {
            initializeSettings()
            observeSettingsChanges()
        }
""",
    """        applicationScope.launch {
            // Apply locale/proxy/session settings before creating cached network/WebView helpers.
            initializeSettings()

            launch(Dispatchers.IO) {
                delay(1_500)
                CipherDeobfuscator.prewarm()
            }

            launch(Dispatchers.IO) {
                delay(2_500)
                var waitedMs = 0
                while (YouTube.visitorData == null && waitedMs < 12_000) {
                    delay(500)
                    waitedMs += 500
                }
                YTPlayerUtils.prewarmPoToken()
            }

            observeSettingsChanges()
        }
""",
    marker="CipherDeobfuscator.prewarm()",
)

print("[dudu7] all patches applied successfully")
