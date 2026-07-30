#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# Main-source bridge: safe for all variants; Dudu7 installs the physical-FM handler.
bridge_path = ROOT / "app/src/main/kotlin/com/metrolist/music/playback/PhysicalFmMediaKeyBridge.kt"
bridge_path.write_text(
    '''package com.metrolist.music.playback

import android.content.Intent
import android.os.Build
import android.os.SystemClock
import android.view.KeyEvent

/**
 * Variant-neutral media-key bridge. The Dudu7 source set installs a handler for
 * physical FM; standard variants leave it unset and stay entirely on Media3.
 */
object PhysicalFmMediaKeyBridge {
    private const val DUPLICATE_WINDOW_MS = 280L

    @Volatile
    private var handler: ((Boolean) -> Boolean)? = null
    private val lock = Any()
    private var lastDirection: Boolean? = null
    private var lastHandledAt = 0L

    fun install(value: ((Boolean) -> Boolean)?) {
        handler = value
        synchronized(lock) {
            lastDirection = null
            lastHandledAt = 0L
        }
    }

    fun handleMediaButton(intent: Intent): Boolean {
        val event = intent.mediaKeyEvent() ?: return false
        if (event.action != KeyEvent.ACTION_DOWN || event.repeatCount != 0) return false
        val direction = when (event.keyCode) {
            KeyEvent.KEYCODE_MEDIA_NEXT,
            KeyEvent.KEYCODE_MEDIA_SKIP_FORWARD,
            -> true
            KeyEvent.KEYCODE_MEDIA_PREVIOUS,
            KeyEvent.KEYCODE_MEDIA_SKIP_BACKWARD,
            -> false
            else -> return false
        }
        return handleDirection(direction)
    }

    fun handleDirection(next: Boolean): Boolean {
        val activeHandler = handler ?: return false
        val now = SystemClock.elapsedRealtime()
        synchronized(lock) {
            if (lastDirection == next && now - lastHandledAt <= DUPLICATE_WINDOW_MS) return true
            if (!activeHandler(next)) return false
            lastDirection = next
            lastHandledAt = now
            return true
        }
    }

    private fun Intent.mediaKeyEvent(): KeyEvent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(Intent.EXTRA_KEY_EVENT)
        }
}
''',
    encoding="utf-8",
)

# Route MediaSession button events and controller next/previous commands through the bridge.
callback_path = "app/src/main/kotlin/com/metrolist/music/playback/MediaLibrarySessionCallback.kt"
callback = read(callback_path)
callback = replace_once(callback, "import android.content.Context\n", "import android.content.Context\nimport android.content.Intent\n", "callback Intent import")
callback = replace_once(callback, "import androidx.media3.common.MediaMetadata\n", "import androidx.media3.common.MediaMetadata\nimport androidx.media3.common.Player\n", "callback Player import")
anchor = '''    override fun onCustomCommand(
        session: MediaSession,
        controller: MediaSession.ControllerInfo,
        customCommand: SessionCommand,
        args: Bundle,
    ): ListenableFuture<SessionResult> {
'''
insert = '''    override fun onMediaButtonEvent(
        session: MediaSession,
        controllerInfo: MediaSession.ControllerInfo,
        intent: Intent,
    ): Boolean {
        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return true
        return super.onMediaButtonEvent(session, controllerInfo, intent)
    }

    override fun onPlayerCommandRequest(
        session: MediaSession,
        controllerInfo: MediaSession.ControllerInfo,
        playerCommand: Int,
    ): Int {
        val direction =
            when (playerCommand) {
                Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM -> true
                Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM -> false
                else -> null
            }
        if (direction != null && PhysicalFmMediaKeyBridge.handleDirection(direction)) {
            return SessionResult.RESULT_SUCCESS
        }
        return super.onPlayerCommandRequest(session, controllerInfo, playerCommand)
    }

'''
callback = replace_once(callback, anchor, insert + anchor, "MediaSession routing methods")
write(callback_path, callback)

# Dudu7 receiver becomes a fallback into the same deduplicated bridge.
receiver_path = "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7MediaButtonReceiver.kt"
receiver = read(receiver_path)
receiver = replace_once(
    receiver,
    '''        val event = intent.mediaKeyEvent()
        val next = event?.let {
            Dudu7FmMediaButtonRouting.directionFor(
                action = it.action,
                keyCode = it.keyCode,
                repeatCount = it.repeatCount,
            )
        }
        if (next != null && FytPhysicalRadio.state.value.isActive) {
            FytPhysicalRadio.tuneAdjacentFavourite(context.applicationContext, next)
            return
        }

        MediaButtonReceiver().onReceive(context, intent)
''',
    '''        Dudu7FmMediaButtonRouting.install(context.applicationContext)
        if (PhysicalFmMediaKeyBridge.handleMediaButton(intent)) return
        MediaButtonReceiver().onReceive(context, intent)
''',
    "receiver bridge route",
)
receiver = replace_once(
    receiver,
    '''internal object Dudu7FmMediaButtonRouting {
    /** Returns true for next, false for previous and null when Media3 should handle the key. */
''',
    '''internal object Dudu7FmMediaButtonRouting {
    @Volatile
    private var installed = false

    fun install(context: Context) {
        if (installed) return
        synchronized(this) {
            if (installed) return
            val appContext = context.applicationContext
            PhysicalFmMediaKeyBridge.install { next ->
                if (!FytPhysicalRadio.state.value.isActive) return@install false
                FytPhysicalRadio.tuneAdjacentFavourite(appContext, next)
                true
            }
            installed = true
        }
    }

    /** Returns true for next, false for previous and null when Media3 should handle the key. */
''',
    "receiver installer",
)
write(receiver_path, receiver)

# Install the Dudu bridge as soon as the physical-radio singleton initializes.
radio_path = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
radio = read(radio_path)
radio = replace_once(
    radio,
    "import com.android.fmradio.FmService\n",
    "import com.android.fmradio.FmService\nimport com.metrolist.music.playback.Dudu7FmMediaButtonRouting\n",
    "radio bridge import",
)
radio = replace_once(
    radio,
    "        startRtrServices(applicationContext)\n",
    "        Dudu7FmMediaButtonRouting.install(applicationContext)\n        startRtrServices(applicationContext)\n",
    "radio bridge install",
)
write(radio_path, radio)

# Restore the standard Media3 manifest receiver; the session callback now owns interception.
manifest_path = "app/src/dudu7/AndroidManifest.xml"
manifest = read(manifest_path)
manifest = replace_once(
    manifest,
    '''        <receiver
            android:name="androidx.media3.session.MediaButtonReceiver"
            tools:node="remove" />
        <receiver
            android:name=".playback.Dudu7MediaButtonReceiver"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MEDIA_BUTTON" />
            </intent-filter>
        </receiver>
''',
    '''        <receiver
            android:name="androidx.media3.session.MediaButtonReceiver"
            android:exported="true"
            tools:node="merge">
            <intent-filter>
                <action android:name="android.intent.action.MEDIA_BUTTON" />
            </intent-filter>
        </receiver>
''',
    "manifest media receiver",
)
write(manifest_path, manifest)

# Focused pure routing test remains independent of Android object construction.
test_path = ROOT / "app/src/test/kotlin/com/metrolist/music/playback/PhysicalFmMediaKeyBridgeContractTest.kt"
test_path.write_text(
    '''package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PhysicalFmMediaKeyBridgeContractTest {
    @Test
    fun duduDirectionParserKeepsOnlySingleDownNextAndPrevious() {
        assertEquals(true, Dudu7FmMediaButtonRouting.directionFor(0, 87, 0))
        assertEquals(false, Dudu7FmMediaButtonRouting.directionFor(0, 88, 0))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(1, 87, 0))
        assertNull(Dudu7FmMediaButtonRouting.directionFor(0, 87, 1))
    }
}
''',
    encoding="utf-8",
)

print("Applied Dudu7 MediaSession FM routing fix")
