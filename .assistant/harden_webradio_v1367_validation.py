from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Missing expected text in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Make UIAutomator collection resilient. The previous strict run displayed the
# correct Local history chip, but a transient dump failure made find_coords
# return false before the XML could be parsed.
test = "scripts/dudu7_webradio_reliability_smoke.sh"
replace_once(
    test,
    '''dump_ui() {
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1
    adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1
}''',
    '''dump_ui() {
    local attempt
    for attempt in 1 2 3; do
        rm -f "$RESULTS_DIR/current-window.xml"
        if timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 \
            && adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1 \
            && test -s "$RESULTS_DIR/current-window.xml" \
            && python3 - "$RESULTS_DIR/current-window.xml" <<'PY'
import sys, xml.etree.ElementTree as ET
ET.parse(sys.argv[1])
PY
        then
            return 0
        fi
        sleep 2
    done
    return 1
}''',
)
replace_once(
    test,
    '''assert_text() {
    local label="$1"; local right="$2"; shift 2
    if find_coords "$right" "$@" >/dev/null; then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "assertion-failure"
        return 1
    fi
}''',
    '''assert_text() {
    local label="$1"; local right="$2"; shift 2
    local attempt
    for attempt in 1 2 3; do
        if find_coords "$right" "$@" >/dev/null; then
            echo "PASS: $label"
            return 0
        fi
        sleep 2
    done
    echo "FAIL: $label" >&2
    capture "assertion-failure"
    return 1
}''',
)

# The vehicle layout owns both the embedded pane navigator and the selected-tab
# state. Ask that owner to return to the queue before starting normal YouTube
# playback. A raw NavController route changes only the destination and can race
# the independently saved tab state after Search/Artist restoration.
artist = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    artist,
    '''                                                    if (embeddedInPlayer) {
                                                        navController.popBackStack("vehicle_queue", inclusive = false)
                                                    }
                                                    playerConnection.playQueue(YouTubeQueue(radioEndpoint))''',
    '''                                                    android.util.Log.d(
                                                        "Dudu7ArtistAction",
                                                        "Radio clicked embedded=$embeddedInPlayer callback=${playerConnection.onUserSongSelection != null}",
                                                    )
                                                    if (embeddedInPlayer) {
                                                        playerConnection.notifyUserSongSelection()
                                                    }
                                                    playerConnection.playQueue(
                                                        YouTubeQueue(radioEndpoint),
                                                        notifyUserSelection = !embeddedInPlayer,
                                                    )''',
)
replace_once(
    artist,
    '''                                                        if (embeddedInPlayer) {
                                                            navController.popBackStack("vehicle_queue", inclusive = false)
                                                        }
                                                        playerConnection.playQueue(YouTubeQueue(shuffleEndpoint))''',
    '''                                                        android.util.Log.d(
                                                            "Dudu7ArtistAction",
                                                            "Shuffle clicked embedded=$embeddedInPlayer callback=${playerConnection.onUserSongSelection != null}",
                                                        )
                                                        if (embeddedInPlayer) {
                                                            playerConnection.notifyUserSongSelection()
                                                        }
                                                        playerConnection.playQueue(
                                                            YouTubeQueue(shuffleEndpoint),
                                                            notifyUserSelection = !embeddedInPlayer,
                                                        )''',
)

# Optional short diagnostic path used by the dedicated x86 emulator workflow.
replace_once(
    test,
    '''capture "launch"

# Verify original local history behavior by finishing one normal music playback session.''',
    '''capture "launch"

if [[ "${FOCUSED_ARTIST_ACTION:-0}" == "1" ]]; then
    tap_tab "WebRadio" "=WebRadio"
    tap_text "focused station one" 1 "=Test Radio One"
    sleep 12
    tap_text "focused radio artist" 0 "=Rick Astley"
    sleep 12
    tap_text "focused artist Radio action" 1 "=Radio"
    sleep 8
    adb logcat -d -v threadtime > "$RESULTS_DIR/focused-artist-action-logcat.txt" 2>&1 || true
    capture "focused-artist-action-result"
    grep -E 'Dudu7ArtistAction|FATAL EXCEPTION|IllegalStateException|IllegalArgumentException|NavController' \
        "$RESULTS_DIR/focused-artist-action-logcat.txt" || true
    assert_selected_tab "focused artist action selected queue" "Warteschlange" "Queue"
    assert_absent_anywhere "focused LIVE after artist action" "=LIVE"
    echo "Focused embedded artist action passed"
    exit 0
fi

# Verify original local history behavior by finishing one normal music playback session.''',
)

print("WebRadio 13.6.7 validation hardened and embedded artist actions fixed")
