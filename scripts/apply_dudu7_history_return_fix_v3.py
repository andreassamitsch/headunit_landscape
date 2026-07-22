#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one occurrence in {path}, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Make the live history insert synchronous and transactionally ensure that the
# parent song exists before inserting the Event foreign-key row.
music = Path("app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt")
replace_once(
    music,
    """                    if (elapsedMs >= historyDurationMs && !dataStore.get(PauseListenHistoryKey, false)) {
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
""",
    """                    if (elapsedMs >= historyDurationMs && !dataStore.get(PauseListenHistoryKey, false)) {
                        val metadata = player.currentMetadata
                        if (metadata == null || metadata.id != mediaId) {
                            delay(500)
                            continue
                        }
                        try {
                            database.withTransaction {
                                // The event table has a foreign key to song. Persist metadata in
                                // the same transaction so a freshly started stream cannot race it.
                                insert(metadata)
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
                        } catch (e: Exception) {
                            Timber.tag(TAG).w(e, "History insert not ready for $mediaId; retrying")
                        }
                    }
""",
)

# Expose a semantic user-song-selection event from PlayerConnection. It is
# emitted only for user-triggered queue changes, not for internal sync/restore.
connection = Path("app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt")
replace_once(
    connection,
    "import kotlinx.coroutines.flow.MutableStateFlow\n",
    "import kotlinx.coroutines.flow.MutableSharedFlow\nimport kotlinx.coroutines.flow.MutableStateFlow\nimport kotlinx.coroutines.flow.asSharedFlow\n",
)
replace_once(
    connection,
    """    var onSkipPrevious: (() -> Unit)? = null
    var onSkipNext: (() -> Unit)? = null

""",
    """    var onSkipPrevious: (() -> Unit)? = null
    var onSkipNext: (() -> Unit)? = null

    private val _userSongSelections = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val userSongSelections = _userSongSelections.asSharedFlow()

    fun notifyUserSongSelection() {
        _userSongSelections.tryEmit(Unit)
    }

""",
)
replace_once(
    connection,
    """        if (!playerReadinessFlow.value) {
            Timber.tag(TAG).w("playQueue called before player ready; delegating to service")
        }
        try {
""",
    """        if (!playerReadinessFlow.value) {
            Timber.tag(TAG).w("playQueue called before player ready; delegating to service")
        }
        if (!allowInternalSync) {
            notifyUserSongSelection()
        }
        try {
""",
)

# A click on the currently active history item toggles playback instead of
# calling playQueue, so explicitly emit the same semantic selection event.
history = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/HistoryScreen.kt")
replace_once(
    history,
    """                                            if (song.id == mediaMetadata?.id) {
                                                playerConnection.togglePlayPause()
""",
    """                                            if (song.id == mediaMetadata?.id) {
                                                playerConnection.notifyUserSongSelection()
                                                playerConnection.togglePlayPause()
""",
)
replace_once(
    history,
    """                                            } else if (event.song.id == mediaMetadata?.id) {
                                                playerConnection.togglePlayPause()
""",
    """                                            } else if (event.song.id == mediaMetadata?.id) {
                                                playerConnection.notifyUserSongSelection()
                                                playerConnection.togglePlayPause()
""",
)

# Replace transition-reason inference with the explicit selection flow.
layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
replace_once(layout, "import androidx.compose.runtime.DisposableEffect\n", "")
replace_once(layout, "import androidx.media3.common.MediaItem\nimport androidx.media3.common.Player\n", "")
replace_once(
    layout,
    """    // A deliberate song choice from Library, Search, History or Home replaces
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
    """    // React only to an explicit title/playlist selection made by the user.
    // Automatic next-track transitions do not emit this signal and therefore
    // never interrupt browsing in the other tabs.
    LaunchedEffect(playerConnection, paneNavController) {
        playerConnection?.userSongSelections?.collect {
            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {
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
    }

""",
)

# Test only nodes in the right pane when selecting a history title; the same
# title is also shown beneath the left cover.
test = Path("scripts/dudu7_ui_smoke.sh")
replace_once(
    test,
    """try_common_dialogs() {
""",
    """find_and_tap_right() {
    local label="$1"
    shift
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || return 1
    adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1 || return 1

    local coords
    coords=$(python3 - "$RESULTS_DIR/current-window.xml" "$DUDU_WIDTH" "$@" <<'PY_RIGHT'
import re
import sys
import xml.etree.ElementTree as ET
xml_path, width, *raw_needles = sys.argv[1:]
minimum_left = int(width) // 2
exact = [value[1:].casefold() for value in raw_needles if value.startswith("=")]
partial = [value.casefold() for value in raw_needles if not value.startswith("=")]
root = ET.parse(xml_path).getroot()
for node in root.iter("node"):
    values = [
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    ]
    haystack = " ".join(filter(None, values))
    if not any(value == needle for value in values for needle in exact) and not (
        haystack and any(needle in haystack for needle in partial)
    ):
        continue
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if left < minimum_left or right <= left or bottom <= top:
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
raise SystemExit(1)
PY_RIGHT
) || return 1

    echo "Tapping $label in right pane at $coords"
    adb shell input tap $coords
    sleep 2
}

try_common_dialogs() {
""",
)
replace_once(
    test,
    'if ! find_and_tap "history current title" "=Never Gonna Give You Up"; then\n',
    'if ! find_and_tap_right "history current title" "=Never Gonna Give You Up"; then\n',
)

# Update structural safeguards.
verify = Path("scripts/verify_dudu7_architecture.py")
text = verify.read_text(encoding="utf-8")
text = text.replace(
    '        "MEDIA_ITEM_TRANSITION_REASON_PLAYLIST_CHANGED",\n        "selectedTab = VehicleRightPaneTab.QUEUE",\n',
    '        "userSongSelections.collect",\n        "selectedTab = VehicleRightPaneTab.QUEUE",\n',
)
text = text.replace(
    '        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",\n',
    '        "database.withTransaction",\n        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",\n',
)
verify.write_text(text, encoding="utf-8")

print("Final Dudu7 history and queue-return patch applied")
