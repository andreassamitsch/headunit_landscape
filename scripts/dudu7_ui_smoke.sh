#!/usr/bin/env bash
set -uo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7}"
ACTIVITY_NAME="${ACTIVITY_NAME:-com.metrolist.music.MainActivity}"
APK_PATH="${APK_PATH:?APK_PATH must point to the emulator APK}"
RESULTS_DIR="${RESULTS_DIR:-ui-test-results}"
DUDU_WIDTH="${DUDU_WIDTH:-1280}"
DUDU_HEIGHT="${DUDU_HEIGHT:-720}"
DUDU_DENSITY="${DUDU_DENSITY:-200}"
TEST_URL="${TEST_URL:-https://music.youtube.com/watch?v=dQw4w9WgXcQ}"

mkdir -p "$RESULTS_DIR"
exec > >(tee "$RESULTS_DIR/smoke-test.log") 2>&1

step=0
capture() {
    local label="$1"
    step=$((step + 1))
    local prefix
    prefix=$(printf '%02d-%s' "$step" "$label")
    adb exec-out screencap -p > "$RESULTS_DIR/${prefix}.png" || true
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
    adb pull /sdcard/window.xml "$RESULTS_DIR/${prefix}.xml" >/dev/null 2>&1 || true
}

find_and_tap() {
    local label="$1"
    shift
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || return 1
    adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1 || return 1

    local coords
    coords=$(python3 - "$RESULTS_DIR/current-window.xml" "$@" <<'PY'
import re
import sys
import xml.etree.ElementTree as ET

xml_path, *raw_needles = sys.argv[1:]
exact_needles = [needle[1:].casefold() for needle in raw_needles if needle.startswith("=")]
partial_needles = [needle.casefold() for needle in raw_needles if not needle.startswith("=")]
try:
    root = ET.parse(xml_path).getroot()
except Exception:
    raise SystemExit(1)

for node in root.iter("node"):
    values = [
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    ]
    haystack = " ".join(filter(None, values))
    exact_match = any(value == needle for value in values for needle in exact_needles)
    partial_match = bool(haystack) and any(needle in haystack for needle in partial_needles)
    if not exact_match and not partial_match:
        continue
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if right <= left or bottom <= top:
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
raise SystemExit(1)
PY
) || return 1

    echo "Tapping $label at $coords"
    adb shell input tap $coords
    sleep 2
}

assert_selected_tab() {
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

find_and_tap_right() {
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
    local attempt
    for attempt in 1 2 3 4 5; do
        find_and_tap "permission/continue" \
            "allow" "while using" "only this time" \
            "zulassen" "bei verwendung" "nur dieses mal" \
            "continue" "weiter" "los geht" \
            "skip" "überspringen" "not now" "später" \
            "got it" "verstanden" || break
    done
}

tap_cover() {
    local x y
    x=$((DUDU_WIDTH * 28 / 100))
    y=$((DUDU_HEIGHT * 28 / 100))
    echo "Tapping cover/lyrics area at $x $y"
    adb shell input tap "$x" "$y"
    sleep 3
}

echo "Waiting for emulator"
adb wait-for-device
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell svc power stayon true || true
adb shell settings put system accelerometer_rotation 0 || true
adb shell settings put system user_rotation 1 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell wm size "${DUDU_WIDTH}x${DUDU_HEIGHT}" || true
adb shell wm density "$DUDU_DENSITY" || true
sleep 3

{
    echo "Requested display: ${DUDU_WIDTH}x${DUDU_HEIGHT} @ ${DUDU_DENSITY} dpi"
    adb shell wm size
    adb shell wm density
    adb shell getprop ro.build.version.release
    adb shell getprop ro.build.version.sdk
    adb shell getprop ro.product.cpu.abilist
} > "$RESULTS_DIR/device-summary.txt" 2>&1
adb shell getprop > "$RESULTS_DIR/getprop.txt" 2>&1 || true

echo "Installing $APK_PATH"
adb install -r -g "$APK_PATH" | tee "$RESULTS_DIR/install.txt"
adb shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS || true
adb shell pm grant "$PACKAGE_NAME" android.permission.RECORD_AUDIO || true
adb shell dumpsys package "$PACKAGE_NAME" > "$RESULTS_DIR/package.txt" 2>&1 || true

adb logcat -c || true
adb shell am force-stop "$PACKAGE_NAME" || true

echo "Launching $PACKAGE_NAME/$ACTIVITY_NAME"
adb shell am start -W -n "$PACKAGE_NAME/$ACTIVITY_NAME" | tee "$RESULTS_DIR/activity-start.txt"
sleep 12
capture "launch"

try_common_dialogs
sleep 5
capture "after-onboarding"

if [[ -n "$TEST_URL" ]]; then
    echo "Opening test URL: $TEST_URL"
    adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" \
        | tee "$RESULTS_DIR/deep-link.txt" || true
    sleep 20
    try_common_dialogs
    capture "deep-link"
fi

adb shell screenrecord --time-limit 60 /sdcard/dudu7-ui-smoke.mp4 >/dev/null 2>&1 &
record_pid=$!
sleep 2

# Keep the first song playing beyond the default 30-second history threshold.
sleep 12
if ! find_and_tap "history tab live" "=Hörverlauf" "=History"; then
    echo "History tab could not be opened" >&2
    exit 1
fi
sleep 3
capture "history-live"
if ! find_and_tap_right "history current title" "=Never Gonna Give You Up"; then
    echo "Current title did not appear in live listening history" >&2
    exit 1
fi
sleep 5
capture "history-selection-return"
if ! assert_selected_tab "Queue tab" "Warteschlange" "Queue"; then
    exit 1
fi

find_and_tap "playback" "=Wiedergabe" && capture "playback-toggle" || true
find_and_tap "shuffle" "=Zufallswiedergabe deaktiviert" "=Zufallswiedergabe aktiviert" && capture "shuffle" || true
find_and_tap "repeat" \
    "=Wiederholen deaktiviert" \
    "=Warteschlange wiederholen" \
    "=Aktuellen Titel wiederholen" && capture "repeat" || true
find_and_tap "like" "=Gefällt mir" && capture "like" || true
find_and_tap "radio" "=Radio starten" && capture "radio" || true
if find_and_tap "library tab" "=Bibliothek" "=Library"; then
    capture "library"
    echo "Tapping right-pane Liked library card"
    adb shell input tap $((DUDU_WIDTH * 67 / 100)) $((DUDU_HEIGHT * 52 / 100))
    sleep 4
    capture "library-detail"
    adb shell input keyevent KEYCODE_BACK || true
    sleep 3
    capture "library-return"
fi

if find_and_tap "search tab" "=Suche" "=Search"; then
    capture "search"
    find_and_tap "search field" "Search YouTube Music" "YouTube Music durchsuchen" "Search library" "Bibliothek durchsuchen" || true
    adb shell input text "rock"
    adb shell input keyevent KEYCODE_ENTER
    sleep 12
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
fi

find_and_tap "home tab" "=Startseite" "=Home" && sleep 8 && capture "home" || true
find_and_tap "queue tab" "=Warteschlange" "=Queue" && capture "queue" || true

tap_cover
capture "lyrics-toggle"
tap_cover
capture "cover-restored"

wait "$record_pid" || true
adb pull /sdcard/dudu7-ui-smoke.mp4 "$RESULTS_DIR/dudu7-ui-smoke.mp4" >/dev/null 2>&1 || true

capture "final"
adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
adb shell dumpsys activity activities > "$RESULTS_DIR/activities.txt" 2>&1 || true
adb shell dumpsys window windows > "$RESULTS_DIR/windows.txt" 2>&1 || true

python3 - "$RESULTS_DIR/logcat.txt" "$RESULTS_DIR/crashes.txt" "$PACKAGE_NAME" <<'PY'
import re
import sys
from pathlib import Path

log_path, crash_path, package = sys.argv[1:]
text = Path(log_path).read_text(errors="replace") if Path(log_path).exists() else ""
findings = []
for match in re.finditer(r"FATAL EXCEPTION:.*?(?=\n\d{2}-\d{2}|\Z)", text, flags=re.DOTALL):
    block = match.group(0)
    if package in block:
        findings.append(block)
for pattern in [
    rf"ANR in {re.escape(package)}.*?(?=\n\d{{2}}-\d{{2}}|\Z)",
    rf"Process {re.escape(package)} .*? has died",
]:
    findings.extend(re.findall(pattern, text, flags=re.DOTALL))
Path(crash_path).write_text("\n\n".join(findings), encoding="utf-8")
PY

screenshot_count=$(find "$RESULTS_DIR" -maxdepth 1 -name '*.png' | wc -l | tr -d ' ')
crash_bytes=$(wc -c < "$RESULTS_DIR/crashes.txt" | tr -d ' ')
cat > "$RESULTS_DIR/summary.md" <<EOF_SUMMARY
# Dudu7 UI smoke test

- Package: \`$PACKAGE_NAME\`
- Display: \`${DUDU_WIDTH}x${DUDU_HEIGHT}\` at \`${DUDU_DENSITY} dpi\`
- Screenshots: \`$screenshot_count\`
- Test URL: \`$TEST_URL\`
- Crash findings: \`$crash_bytes bytes\`

The artifact contains screenshots, UI hierarchy XML files, a short screen recording,
installation and activity output, Logcat, and Android activity/window dumps.
EOF_SUMMARY

cat "$RESULTS_DIR/summary.md"

if [[ "$crash_bytes" -gt 0 ]]; then
    echo "Detected a crash or ANR for $PACKAGE_NAME"
    cat "$RESULTS_DIR/crashes.txt"
    exit 1
fi
