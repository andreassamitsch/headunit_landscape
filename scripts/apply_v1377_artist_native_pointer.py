#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


vehicle_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
vehicle = vehicle_path.read_text(encoding="utf-8")
vehicle = replace_once(
    vehicle,
    """                                ) {
                                    val scrollHandler = rightPaneScrollBridge.handler
""",
    """                                ) {
                                    // Artist screens must receive their pointer stream directly.
                                    // Merely observing the stream here on PointerEventPass.Initial
                                    // prevented the embedded LazyColumn and its buttons from handling
                                    // native gestures reliably on the Dudu7.
                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        Timber.tag("Dudu7ArtistInput").i(
                                            "Using native artist pointer handling route=%s",
                                            currentPaneRoute,
                                        )
                                        return@pointerInput
                                    }
                                    val scrollHandler = rightPaneScrollBridge.handler
""",
    "VehicleLandscapeLayout native artist pointer bypass",
)
vehicle_path.write_text(vehicle, encoding="utf-8")


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")
artist = replace_once(
    artist,
    """            userScrollEnabled = !embeddedInPlayer,
""",
    """            userScrollEnabled = true,
""",
    "ArtistScreen native LazyColumn scrolling",
)
artist_path.write_text(artist, encoding="utf-8")


smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")

absent_helper = r'''
assert_text_absent() {
    local label="$1"; local right="$2"; shift 2
    local attempt
    for attempt in 1 2 3 4; do
        if ! find_coords "$right" "$@" >/dev/null 2>&1; then
            echo "PASS: $label"
            return 0
        fi
        sleep 2
    done
    echo "FAIL: $label is still visible" >&2
    capture "assertion-failure-${label// /-}"
    return 1
}
'''
if "assert_text_absent()" not in smoke:
    marker = """tap_tab() {
"""
    if marker not in smoke:
        raise SystemExit("Smoke tap_tab marker missing")
    smoke = smoke.replace(marker, absent_helper + "\n" + marker, 1)

smoke = smoke.replace(
    '''    adb logcat -d -v threadtime > "$RESULTS_DIR/right-pane-scroll-log.txt" || true
    grep -q "Dudu7RightPaneScroll" "$RESULTS_DIR/right-pane-scroll-log.txt"
    capture "artist-after-bounded-scroll"
''',
    '''    adb logcat -d -v threadtime > "$RESULTS_DIR/artist-native-scroll-log.txt" || true
    capture "artist-after-native-scroll"
''',
    1,
)
smoke = smoke.replace(
    '''    grep -q "Dudu7ArtistSectionTap" "$RESULTS_DIR/artist-items-navigation-log.txt"
    grep -q "Dudu7ArtistNavigation" "$RESULTS_DIR/artist-items-navigation-log.txt"
''',
    '''    grep -q "Dudu7ArtistNavigation" "$RESULTS_DIR/artist-items-navigation-log.txt"
''',
    1,
)
smoke = smoke.replace(
    '''    grep -q "Dudu7ArtistAction.*Play all clicked" "$RESULTS_DIR/artist-play-all-log.txt"
    grep -q "Dudu7RightPaneTap.*handled=true" "$RESULTS_DIR/artist-play-all-log.txt"
    capture "artist-play-all-action"
''',
    '''    grep -q "Dudu7ArtistAction.*Play all clicked" "$RESULTS_DIR/artist-play-all-log.txt"
    assert_text_absent "radio LIVE indicator cleared after Play All" 0 "=LIVE"
    capture "artist-play-all-action"
''',
    1,
)
smoke = smoke.replace(
    "- PASS: embedded artist Play All tap reached the playback action\n",
    "- PASS: native embedded artist Play All tap started non-radio playback\n",
    1,
)
smoke_path.write_text(smoke, encoding="utf-8")

if 'return@pointerInput' not in vehicle:
    raise SystemExit("Native artist pointer bypass was not added")
if "userScrollEnabled = true" not in artist:
    raise SystemExit("Artist LazyColumn is not natively scrollable")
if "assert_text_absent" not in smoke:
    raise SystemExit("Playback-state absence assertion missing")

print("Enabled direct native pointer handling for embedded artist routes and strengthened Play All validation")
