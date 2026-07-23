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

# Material3 OutlinedButton/IconButton did not receive injected or physical taps
# inside this nested embedded header although their semantics were clickable.
# Use the same simple clipped + combinedClickable surfaces that are reliable in
# the WebRadio favorite list. Keep the original controls outside vehicle mode.
artist = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    artist,
    "import androidx.compose.foundation.background\n",
    "import androidx.compose.foundation.background\nimport androidx.compose.foundation.border\n",
)
replace_once(
    artist,
    "import androidx.compose.ui.graphics.Color\n",
    "import androidx.compose.ui.draw.clip\nimport androidx.compose.ui.graphics.Color\n",
)
replace_once(
    artist,
    '''                                            artistPage?.artist?.radioEndpoint?.let { radioEndpoint ->
                                                OutlinedButton(
                                                    onClick = {
                                                        if (embeddedInPlayer) {
                                                            navController.popBackStack("vehicle_queue", inclusive = false)
                                                        }
                                                        playerConnection.playQueue(YouTubeQueue(radioEndpoint))
                                                    },
                                                    shape = RoundedCornerShape(50),
                                                    modifier = Modifier.height(40.dp),
                                                ) {
                                                    Icon(
                                                        painter = painterResource(R.drawable.radio),
                                                        contentDescription = null,
                                                        modifier = Modifier.size(20.dp),
                                                    )
                                                    Spacer(modifier = Modifier.width(8.dp))
                                                    Text(
                                                        text = stringResource(R.string.radio),
                                                        fontSize = 14.sp,
                                                    )
                                                }
                                            }''',
    '''                                            artistPage?.artist?.radioEndpoint?.let { radioEndpoint ->
                                                val playArtistRadio: () -> Unit = {
                                                    timber.log.Timber.tag("Dudu7ArtistAction").e(
                                                        "Radio clicked embedded=%s callback=%s",
                                                        embeddedInPlayer,
                                                        playerConnection.onUserSongSelection != null,
                                                    )
                                                    if (embeddedInPlayer) {
                                                        playerConnection.notifyUserSongSelection()
                                                    }
                                                    playerConnection.playQueue(
                                                        YouTubeQueue(radioEndpoint),
                                                        notifyUserSelection = !embeddedInPlayer,
                                                    )
                                                }
                                                if (embeddedInPlayer) {
                                                    Row(
                                                        modifier =
                                                            Modifier
                                                                .height(40.dp)
                                                                .clip(RoundedCornerShape(50))
                                                                .border(
                                                                    width = 1.dp,
                                                                    color = MaterialTheme.colorScheme.outline,
                                                                    shape = RoundedCornerShape(50),
                                                                ).combinedClickable(
                                                                    onClick = playArtistRadio,
                                                                    onLongClick = {},
                                                                ).padding(horizontal = 16.dp),
                                                        verticalAlignment = Alignment.CenterVertically,
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.radio),
                                                            contentDescription = null,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = stringResource(R.string.radio),
                                                            fontSize = 14.sp,
                                                        )
                                                    }
                                                } else {
                                                    OutlinedButton(
                                                        onClick = playArtistRadio,
                                                        shape = RoundedCornerShape(50),
                                                        modifier = Modifier.height(40.dp),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.radio),
                                                            contentDescription = null,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = stringResource(R.string.radio),
                                                            fontSize = 14.sp,
                                                        )
                                                    }
                                                }
                                            }''',
)
replace_once(
    artist,
    '''                                            artistPage?.artist?.shuffleEndpoint?.let { shuffleEndpoint ->
                                                IconButton(
                                                    onClick = {
                                                        if (embeddedInPlayer) {
                                                            navController.popBackStack("vehicle_queue", inclusive = false)
                                                        }
                                                        playerConnection.playQueue(YouTubeQueue(shuffleEndpoint))
                                                    },
                                                    modifier =
                                                        Modifier
                                                            .size(48.dp)
                                                            .background(
                                                                MaterialTheme.colorScheme.primary,
                                                                RoundedCornerShape(24.dp),
                                                            ),
                                                ) {
                                                    Icon(
                                                        painter = painterResource(R.drawable.shuffle),
                                                        contentDescription = "Shuffle",
                                                        tint = MaterialTheme.colorScheme.onPrimary,
                                                        modifier = Modifier.size(20.dp),
                                                    )
                                                }
                                            }''',
    '''                                            artistPage?.artist?.shuffleEndpoint?.let { shuffleEndpoint ->
                                                val playArtistShuffle: () -> Unit = {
                                                    timber.log.Timber.tag("Dudu7ArtistAction").e(
                                                        "Shuffle clicked embedded=%s callback=%s",
                                                        embeddedInPlayer,
                                                        playerConnection.onUserSongSelection != null,
                                                    )
                                                    if (embeddedInPlayer) {
                                                        playerConnection.notifyUserSongSelection()
                                                    }
                                                    playerConnection.playQueue(
                                                        YouTubeQueue(shuffleEndpoint),
                                                        notifyUserSelection = !embeddedInPlayer,
                                                    )
                                                }
                                                if (embeddedInPlayer) {
                                                    Box(
                                                        contentAlignment = Alignment.Center,
                                                        modifier =
                                                            Modifier
                                                                .size(48.dp)
                                                                .clip(RoundedCornerShape(24.dp))
                                                                .background(MaterialTheme.colorScheme.primary)
                                                                .combinedClickable(
                                                                    onClick = playArtistShuffle,
                                                                    onLongClick = {},
                                                                ),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.shuffle),
                                                            contentDescription = "Shuffle",
                                                            tint = MaterialTheme.colorScheme.onPrimary,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                    }
                                                } else {
                                                    IconButton(
                                                        onClick = playArtistShuffle,
                                                        modifier =
                                                            Modifier
                                                                .size(48.dp)
                                                                .background(
                                                                    MaterialTheme.colorScheme.primary,
                                                                    RoundedCornerShape(24.dp),
                                                                ),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.shuffle),
                                                            contentDescription = "Shuffle",
                                                            tint = MaterialTheme.colorScheme.onPrimary,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                    }
                                                }
                                            }''',
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
