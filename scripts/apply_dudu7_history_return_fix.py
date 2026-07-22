#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one occurrence in {path}, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


music = Path("app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt")
replace_once(
    music,
    "import android.os.Looper\n",
    "import android.os.Looper\nimport android.os.SystemClock\n",
)
replace_once(
    music,
    "    private var scrobbleManager: ScrobbleManager? = null\n",
    """    private var scrobbleManager: ScrobbleManager? = null

    // PlaybackStatsListener only finalizes a listening session after the item ends.
    // Track active listening as well so History updates while the current song plays.
    private var activeHistoryMediaId: String? = null
    private var activeHistoryAccumulatedMs = 0L
    private var activeHistoryStartedAtMs: Long? = null
    private var activeHistoryRecorded = false
    private var activeHistoryMonitorJob: Job? = null
""",
)
replace_once(
    music,
    "    private var previousMediaItemIndex = C.INDEX_UNSET\n",
    """    private fun activeHistoryElapsedMs(): Long =
        activeHistoryAccumulatedMs +
            (activeHistoryStartedAtMs?.let { startedAt ->
                (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)
            } ?: 0L)

    private fun stopActiveHistoryClock() {
        activeHistoryStartedAtMs?.let { startedAt ->
            activeHistoryAccumulatedMs +=
                (SystemClock.elapsedRealtime() - startedAt).coerceAtLeast(0L)
        }
        activeHistoryStartedAtMs = null
        activeHistoryMonitorJob?.cancel()
        activeHistoryMonitorJob = null
    }

    private fun resetActiveHistoryTracking(mediaId: String?) {
        stopActiveHistoryClock()
        activeHistoryMediaId = mediaId
        activeHistoryAccumulatedMs = 0L
        activeHistoryRecorded = false
        if (mediaId != null && player.isPlaying) {
            activeHistoryStartedAtMs = SystemClock.elapsedRealtime()
            startActiveHistoryMonitor()
        }
    }

    private fun updateActiveHistoryTracking(isPlaying: Boolean) {
        val mediaId = player.currentMediaItem?.mediaId
        if (mediaId != activeHistoryMediaId) {
            resetActiveHistoryTracking(mediaId)
        }
        if (isPlaying && mediaId != null && !activeHistoryRecorded) {
            if (activeHistoryStartedAtMs == null) {
                activeHistoryStartedAtMs = SystemClock.elapsedRealtime()
            }
            startActiveHistoryMonitor()
        } else if (!isPlaying) {
            stopActiveHistoryClock()
        }
    }

    private fun startActiveHistoryMonitor() {
        val mediaId = activeHistoryMediaId ?: return
        if (activeHistoryRecorded || activeHistoryMonitorJob?.isActive == true) return

        activeHistoryMonitorJob =
            scope.launch {
                while (isActive && activeHistoryMediaId == mediaId && !activeHistoryRecorded) {
                    if (!player.isPlaying || player.currentMediaItem?.mediaId != mediaId) return@launch

                    val historyDurationMs =
                        ((dataStore[HistoryDuration]?.times(1000f)) ?: 30000f).toLong()
                    val elapsedMs = activeHistoryElapsedMs()
                    if (elapsedMs >= historyDurationMs && !dataStore.get(PauseListenHistoryKey, false)) {
                        try {
                            database.query {
                                insert(
                                    Event(
                                        songId = mediaId,
                                        timestamp = LocalDateTime.now(),
                                        playTime = elapsedMs,
                                    ),
                                )
                            }
                            activeHistoryRecorded = true
                            Timber.tag(TAG).d("Recorded active history item for $mediaId after ${elapsedMs}ms")
                            return@launch
                        } catch (e: SQLException) {
                            // Metadata may still be entering Room during the first seconds.
                            Timber.tag(TAG).w(e, "History insert not ready for $mediaId; retrying")
                        }
                    }
                    delay(500)
                }
            }
    }

    private var previousMediaItemIndex = C.INDEX_UNSET
""",
)
replace_once(
    music,
    "        lastTransitionedMediaId = mediaItem?.mediaId\n",
    "        lastTransitionedMediaId = mediaItem?.mediaId\n        resetActiveHistoryTracking(mediaItem?.mediaId)\n",
)
replace_once(
    music,
    """        if (events.containsAny(Player.EVENT_IS_PLAYING_CHANGED)) {
            updateWidgetUI(player.isPlaying)
""",
    """        if (events.containsAny(Player.EVENT_IS_PLAYING_CHANGED)) {
            updateActiveHistoryTracking(player.isPlaying)
            updateWidgetUI(player.isPlaying)
""",
)
replace_once(
    music,
    """        if (playbackStats.totalPlayTimeMs >= historyDurationMs &&
            !dataStore.get(PauseListenHistoryKey, false)
        ) {
            database.query {
                incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)
                try {
                    insert(
                        Event(
                            songId = mediaItem.mediaId,
                            timestamp = LocalDateTime.now(),
                            playTime = playbackStats.totalPlayTimeMs,
                        ),
                    )
                } catch (_: SQLException) {
                }
            }
        }
""",
    """        if (playbackStats.totalPlayTimeMs >= historyDurationMs &&
            !dataStore.get(PauseListenHistoryKey, false)
        ) {
            // The active monitor writes the Event when the threshold is reached.
            // PlaybackStats remains responsible for aggregate play time.
            database.query {
                incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)
            }
        }
""",
)
replace_once(
    music,
    """        player.release()
        scope.cancel()
""",
    """        activeHistoryMonitorJob?.cancel()
        player.release()
        scope.cancel()
""",
)

layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
replace_once(
    layout,
    "import androidx.compose.runtime.CompositionLocalProvider\n",
    "import androidx.compose.runtime.CompositionLocalProvider\nimport androidx.compose.runtime.DisposableEffect\n",
)
replace_once(
    layout,
    "import androidx.compose.ui.unit.dp\n",
    "import androidx.compose.ui.unit.dp\nimport androidx.media3.common.MediaItem\nimport androidx.media3.common.Player\n",
)
replace_once(
    layout,
    "import com.metrolist.music.LocalPlayerAwareWindowInsets\n",
    "import com.metrolist.music.LocalPlayerAwareWindowInsets\nimport com.metrolist.music.LocalPlayerConnection\n",
)
replace_once(
    layout,
    "    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()\n",
    "    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()\n    val playerConnection = LocalPlayerConnection.current\n",
)
replace_once(
    layout,
    """    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {
        paneNavController.popBackStack()
    }

""",
    """    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {
        paneNavController.popBackStack()
    }

    // A deliberate song choice from Library, Search, History or Home replaces
    // the playlist. Return to Queue for that reason only; automatic next-track
    // transitions must not interrupt browsing.
    DisposableEffect(playerConnection, paneNavController) {
        val activePlayer = playerConnection?.player
        val listener =
            object : Player.Listener {
                override fun onMediaItemTransition(
                    mediaItem: MediaItem?,
                    reason: Int,
                ) {
                    if (mediaItem == null || reason != Player.MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED) return
                    if (paneNavController.currentDestination?.route == VEHICLE_QUEUE_ROUTE) return

                    selectedTab = VehicleRightPaneTab.QUEUE
                    paneNavController.navigate(VEHICLE_QUEUE_ROUTE) {
                        popUpTo(VEHICLE_QUEUE_ROUTE) {
                            inclusive = false
                            saveState = true
                        }
                        launchSingleTop = true
                    }
                }
            }
        activePlayer?.addListener(listener)
        onDispose { activePlayer?.removeListener(listener) }
    }

""",
)

test = Path("scripts/dudu7_ui_smoke.sh")
replace_once(
    test,
    """try_common_dialogs() {
""",
    """assert_selected_tab() {
    local label="$1"
    shift
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || return 1
    adb pull /sdcard/window.xml "$RESULTS_DIR/selected-tab.xml" >/dev/null 2>&1 || return 1
    python3 - "$RESULTS_DIR/selected-tab.xml" "$@" <<'PY_SELECTED'
import sys
import xml.etree.ElementTree as ET
xml_path, *labels = sys.argv[1:]
labels = {label.casefold() for label in labels}
root = ET.parse(xml_path).getroot()
for node in root.iter("node"):
    values = {
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    }
    if values & labels and node.attrib.get("selected") == "true":
        raise SystemExit(0)
raise SystemExit(1)
PY_SELECTED
    local status=$?
    if [[ "$status" -ne 0 ]]; then
        echo "$label is not selected" >&2
    fi
    return "$status"
}

try_common_dialogs() {
""",
)
replace_once(
    test,
    "find_and_tap \"playback\" \"=Wiedergabe\" && capture \"playback-toggle\" || true\n",
    """# Keep the first song playing beyond the default 30-second history threshold.
sleep 12
if ! find_and_tap "history tab live" "=Hörverlauf" "=History"; then
    echo "History tab could not be opened" >&2
    exit 1
fi
sleep 3
capture "history-live"
if ! find_and_tap "history current title" "=Never Gonna Give You Up"; then
    echo "Current title did not appear in live listening history" >&2
    exit 1
fi
sleep 5
capture "history-selection-return"
if ! assert_selected_tab "Queue tab" "Warteschlange" "Queue"; then
    exit 1
fi

find_and_tap "playback" "=Wiedergabe" && capture "playback-toggle" || true
""",
)
replace_once(
    test,
    """    sleep 12
    capture "search-results"
    adb shell input keyevent KEYCODE_BACK || true
    sleep 3
    capture "search-return"
""",
    """    sleep 12
    capture "search-results"
    if ! find_and_tap "search song selection" "=Back In Black"; then
        echo "Could not select a song from search results" >&2
        exit 1
    fi
    sleep 5
    capture "search-selection-return"
    if ! assert_selected_tab "Queue tab after search selection" "Warteschlange" "Queue"; then
        exit 1
    fi
""",
)
replace_once(
    test,
    "find_and_tap \"history tab\" \"=Hörverlauf\" \"=History\" && capture \"history\" || true\n",
    "",
)

verify = Path("scripts/verify_dudu7_architecture.py")
text = verify.read_text(encoding="utf-8")
anchor = '    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n'
addition = '''    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt": (
        "activeHistoryMonitorJob",
        "Recorded active history item",
        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt": (
        "MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED",
        "selectedTab = VehicleRightPaneTab.QUEUE",
    ),
'''
if addition not in text:
    if anchor not in text:
        raise SystemExit("Verification insertion anchor missing")
    verify.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")

print("Dudu7 history and queue-return patch applied")
