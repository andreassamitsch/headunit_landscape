#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

if "import androidx.compose.foundation.gestures.scrollBy\n" not in artist:
    artist = replace_once(
        artist,
        "import androidx.compose.foundation.combinedClickable\n",
        "import androidx.compose.foundation.combinedClickable\nimport androidx.compose.foundation.gestures.scrollBy\n",
        "ArtistScreen scrollBy import",
    )
if "import kotlinx.coroutines.channels.Channel\n" not in artist:
    artist = replace_once(
        artist,
        "import kotlinx.coroutines.launch\n",
        "import kotlinx.coroutines.channels.Channel\nimport kotlinx.coroutines.launch\n",
        "ArtistScreen Channel import",
    )

artist = replace_once(
    artist,
    """    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
""",
    """    val rightPaneScrollOwner = remember { Any() }
    val rightPaneScrollDeltas = remember { Channel<Float>(Channel.UNLIMITED) }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
""",
    "ArtistScreen scroll channel state",
)

artist = replace_once(
    artist,
    """    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
""",
    """    LaunchedEffect(embeddedInPlayer, lazyListState, rightPaneScrollDeltas) {
        if (embeddedInPlayer) {
            for (delta in rightPaneScrollDeltas) {
                // scrollBy uses the normal LazyList bounds calculation. The former
                // dispatchRawDelta path could move the measured content completely
                // outside the pane and leave an all-white artist page on real units.
                lazyListState.scrollBy(delta)
            }
        }
    }

    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
""",
    "ArtistScreen bounded scroll collector",
)

artist = replace_once(
    artist,
    """                handler = { delta -> lazyListState.dispatchRawDelta(delta) },
""",
    """                handler = { delta ->
                    // A single malformed pointer delta must never jump beyond the
                    // complete list. Normal gestures arrive as many smaller deltas.
                    rightPaneScrollDeltas.trySend(delta.coerceIn(-160f, 160f))
                },
""",
    "ArtistScreen raw scroll handler",
)

artist = replace_once(
    artist,
    """                val onPlayAllClick: () -> Unit = {
                    if (!isGuest) {
""",
    """                val onPlayAllClick: () -> Unit = {
                    timber.log.Timber.tag("Dudu7ArtistAction").i(
                        "Play all clicked embedded=%s local=%s",
                        embeddedInPlayer,
                        showLocal,
                    )
                    if (!isGuest) {
""",
    "ArtistScreen play-all action log",
)

artist = replace_once(
    artist,
    """                if (showLocalFab) {
                    androidx.compose.material3.SmallFloatingActionButton(
                        modifier = Modifier.padding(16.dp).offset(x = (-4).dp), // Align center with standard FAB (56dp vs 48dp)
""",
    """                val playAllTapKey = "artist_play_all"
                DisposableEffect(playAllTapKey, embeddedInPlayer) {
                    onDispose {
                        rightPaneTapTargets.remove(playAllTapKey)
                    }
                }
                val playAllTapModifier =
                    if (embeddedInPlayer) {
                        Modifier.onGloballyPositioned { coordinates ->
                            rightPaneTapTargets[playAllTapKey] =
                                coordinates.boundsInRoot() to onPlayAllClick
                        }
                    } else {
                        Modifier
                    }

                if (showLocalFab) {
                    androidx.compose.material3.SmallFloatingActionButton(
                        modifier =
                            Modifier
                                .padding(16.dp)
                                .offset(x = (-4).dp)
                                .then(playAllTapModifier), // Align center with standard FAB (56dp vs 48dp)
""",
    "ArtistScreen embedded play-all tap registration",
)

artist = replace_once(
    artist,
    """                    androidx.compose.material3.FloatingActionButton(
                        modifier = Modifier.padding(16.dp),
""",
    """                    androidx.compose.material3.FloatingActionButton(
                        modifier = Modifier.padding(16.dp).then(playAllTapModifier),
""",
    "ArtistScreen standard play-all modifier",
)

if "lazyListState.dispatchRawDelta(delta)" in artist:
    raise SystemExit("Obsolete raw artist scroll handler is still present")
if "rightPaneTapTargets[playAllTapKey]" not in artist:
    raise SystemExit("Play-all parent tap target was not added")

artist_path.write_text(artist, encoding="utf-8")


smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")

not_blank_helper = r'''
assert_artist_not_blank() {
    local xml="$1"
    python3 - "$xml" "$DUDU_WIDTH" "$DUDU_HEIGHT" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width, height = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
root = ET.parse(path).getroot()
ignore = {
    'warteschlange','queue','bibliothek','library','suche','search',
    'hörverlauf','history','webradio','startseite','home','rick astley'
}
visible = []
for node in root.iter('node'):
    value = (node.attrib.get('text','').strip() or node.attrib.get('content-desc','').strip())
    if not value or value.casefold() in ignore:
        continue
    m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    if not m:
        continue
    l,t,r,b = map(int,m.groups())
    if l < width//2 or t < 105 or b > height-4 or r <= l or b <= t:
        continue
    visible.append(value)
unique = list(dict.fromkeys(visible))
if len(unique) < 2:
    raise SystemExit(f'Artist pane became blank after scrolling: visible={unique}')
print(f'PASS: artist pane remains populated after scrolling: {unique[:8]}')
PY
}
'''
if "assert_artist_not_blank()" not in smoke:
    marker = """assert_artist_items_detail() {
"""
    if marker not in smoke:
        raise SystemExit("Smoke artist detail helper marker missing")
    smoke = smoke.replace(marker, not_blank_helper + "\n" + marker, 1)

old_scroll = '''    adb logcat -c || true
    dump_ui "$RESULTS_DIR/artist-before-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*30/100)) 700
    sleep 4
    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    adb logcat -d -v threadtime > "$RESULTS_DIR/right-pane-scroll-log.txt" || true
    grep -q "Dudu7RightPaneScroll" "$RESULTS_DIR/right-pane-scroll-log.txt"
    capture "artist-after-real-scroll"
'''
new_scroll = '''    adb logcat -c || true
    dump_ui "$RESULTS_DIR/artist-before-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 500
    sleep 3
    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) 350
    sleep 3
    dump_ui "$RESULTS_DIR/artist-after-strong-scroll.xml"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-strong-scroll.xml"
    adb logcat -d -v threadtime > "$RESULTS_DIR/right-pane-scroll-log.txt" || true
    grep -q "Dudu7RightPaneScroll" "$RESULTS_DIR/right-pane-scroll-log.txt"
    capture "artist-after-bounded-scroll"
'''
smoke = replace_once(smoke, old_scroll, new_scroll, "Smoke bounded artist scroll test")

old_detail_end = '''    grep -q "Dudu7ArtistItems" "$RESULTS_DIR/artist-items-navigation-log.txt"
    capture "artist-songs-detail"

    adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
'''
new_detail_end = '''    grep -q "Dudu7ArtistItems" "$RESULTS_DIR/artist-items-navigation-log.txt"
    capture "artist-songs-detail"

    adb shell input keyevent KEYCODE_BACK
    sleep 4
    assert_text "back to artist before play all" 1 "=Rick Astley"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*88/100)) 450
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*88/100)) 450
    sleep 4
    assert_text "artist play all button" 1 "=Play All"
    adb logcat -c || true
    tap_clickable_text "artist play all" 1 "=Play All"
    sleep 16
    adb logcat -d -v threadtime > "$RESULTS_DIR/artist-play-all-log.txt" || true
    grep -q "Dudu7ArtistAction.*Play all clicked" "$RESULTS_DIR/artist-play-all-log.txt"
    grep -q "Dudu7RightPaneTap.*handled=true" "$RESULTS_DIR/artist-play-all-log.txt"
    capture "artist-play-all-action"

    adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
'''
smoke = replace_once(smoke, old_detail_end, new_detail_end, "Smoke artist play-all validation")

smoke = smoke.replace(
    "- PASS: artist content visibly moved after the swipe\n",
    "- PASS: artist content visibly moved and stayed populated after repeated strong swipes\n",
    1,
)
smoke = smoke.replace(
    "- PASS: Top Songs detail navigation opened\n",
    "- PASS: Top Songs detail navigation opened\n- PASS: embedded artist Play All tap reached the playback action\n",
    1,
)

smoke_path.write_text(smoke, encoding="utf-8")


build_path = Path("app/build.gradle.kts")
build = build_path.read_text(encoding="utf-8")
build = replace_once(build, "versionCode = 160", "versionCode = 161", "versionCode 161")
build = replace_once(build, 'versionName = "13.7.1"', 'versionName = "13.7.2"', "versionName 13.7.2")
build_path.write_text(build, encoding="utf-8")

print("Applied bounded artist scrolling, parent-routed Play All, and 13.7.2 version bump")
