#!/usr/bin/env bash
set -Eeuo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7.debug}"
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
    step=$((step + 1))
    local prefix
    prefix=$(printf '%02d-%s' "$step" "$1")
    adb exec-out screencap -p > "$RESULTS_DIR/${prefix}.png" || true
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
    adb pull /sdcard/window.xml "$RESULTS_DIR/${prefix}.xml" >/dev/null 2>&1 || true
}

dump_ui() {
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1
    adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1
}

find_coords() {
    local right_only="$1"; shift
    dump_ui || return 1
    python3 - "$RESULTS_DIR/current-window.xml" "$DUDU_WIDTH" "$right_only" "$@" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width, right_only, *needles = sys.argv[1:]
width = int(width)
exact = [n[1:].casefold() for n in needles if n.startswith('=')]
partial = [n.casefold() for n in needles if not n.startswith('=')]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter('node'):
    values = [node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()]
    hay = ' '.join(v for v in values if v)
    if not any(v == n for v in values for n in exact) and not (hay and any(n in hay for n in partial)):
        continue
    cur = node
    fallback = None
    while cur is not None:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            if (right_only != '1' or l >= width//2) and r>l and b>t:
                fallback=(l,t,r,b)
                if cur.attrib.get('clickable') == 'true':
                    print((l+r)//2, (t+b)//2); raise SystemExit(0)
        cur = parent.get(cur)
    if fallback:
        l,t,r,b=fallback; print((l+r)//2,(t+b)//2); raise SystemExit(0)
raise SystemExit(1)
PY
}

tap_text() {
    local label="$1"; local right="$2"; shift 2
    local coords
    coords=$(find_coords "$right" "$@") || return 1
    echo "Tapping $label at $coords"
    adb shell input tap $coords
    sleep 3
}

assert_text() {
    local label="$1"; local right="$2"; shift 2
    if find_coords "$right" "$@" >/dev/null; then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "assertion-failure"
        return 1
    fi
}

assert_absent_right() {
    local label="$1"; shift
    if find_coords 1 "$@" >/dev/null; then
        echo "FAIL: $label unexpectedly visible" >&2
        return 1
    fi
    echo "PASS: $label absent"
}

tap_tab() {
    local label="$1"; shift
    local attempt
    for attempt in 1 2 3 4; do
        if tap_text "$label" 0 "$@"; then return 0; fi
        adb shell input swipe $((DUDU_WIDTH*9/10)) 75 $((DUDU_WIDTH*55/100)) 75 450 || true
        sleep 2
    done
    echo "Could not open tab: $label" >&2
    return 1
}

try_dialogs() {
    local i
    for i in 1 2 3 4 5 6; do
        tap_text "dialog" 0 "allow" "zulassen" "while using" "bei verwendung" "continue" "weiter" "skip" "überspringen" "not now" "später" "got it" "verstanden" || break
    done
}

seed_radios() {
    python3 - > /tmp/metrolist_webradio.xml <<'PY'
import html, json
stations = [
 {"uuid":"test-radio-one","name":"Test Radio One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"http://10.0.2.2:8000/logo1.png","country":"Austria","language":"German","tags":"Test,Rock","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-two","name":"Test Radio Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"http://10.0.2.2:8000/logo2.png","country":"Austria","language":"German","tags":"Test,Pop","codec":"MP3","bitrate":96}
]
raw=json.dumps(stations,separators=(',',':'))
print('<?xml version="1.0" encoding="utf-8" standalone="yes" ?>')
print('<map><string name="stations">'+html.escape(raw)+'</string></map>')
PY
    adb push /tmp/metrolist_webradio.xml /data/local/tmp/metrolist_webradio.xml >/dev/null
    adb shell run-as "$PACKAGE_NAME" mkdir -p shared_prefs
    adb shell run-as "$PACKAGE_NAME" cp /data/local/tmp/metrolist_webradio.xml shared_prefs/metrolist_webradio.xml
}

adb wait-for-device
adb shell input keyevent KEYCODE_WAKEUP || true
adb shell wm dismiss-keyguard || true
adb shell settings put system accelerometer_rotation 0 || true
adb shell settings put system user_rotation 1 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell wm size "${DUDU_WIDTH}x${DUDU_HEIGHT}" || true
adb shell wm density "$DUDU_DENSITY" || true

adb install -r -g "$APK_PATH" | tee "$RESULTS_DIR/install.txt"
adb shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS || true
seed_radios
adb logcat -c || true
adb shell am force-stop "$PACKAGE_NAME" || true
adb shell am start -W -n "$PACKAGE_NAME/$ACTIVITY_NAME" | tee "$RESULTS_DIR/activity-start.txt"
sleep 12
try_dialogs
capture "launch"

# Verify original local history behavior by finishing one normal music playback session.
echo "Opening normal music test item"
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/deep-link.txt" || true
sleep 20
try_dialogs
adb shell input keyevent KEYCODE_MEDIA_PLAY || true
assert_text "normal music title loaded" 0 "=Never Gonna Give You Up" || true
sleep 35
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8

tap_tab "Hörverlauf" "=Hörverlauf" "=History"
assert_text "original local-history chip" 1 "Lokal" "Local"
capture "history-original"
assert_text "normal song recorded in original history" 1 "=Never Gonna Give You Up"

# Open embedded WebRadio and verify the right-pane library.
tap_tab "WebRadio" "=WebRadio"
assert_text "saved radio section" 1 "=Gespeichert"
assert_text "radio search section" 1 "=Sender suchen"
assert_text "first saved station" 1 "=Test Radio One"
assert_text "second saved station" 1 "=Test Radio Two"
capture "webradio-saved"

# Play station one and wait for ICY StreamTitle metadata on the left player.
tap_text "station one" 1 "=Test Radio One"
sleep 12
capture "radio-one-playing"
assert_text "station one stream title" 0 "Test Track One"
assert_text "station one artist" 0 "Test Artist One"
assert_text "live indicator" 0 "LIVE"

# Player next must move through the saved station queue.
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 12
capture "radio-two-playing"
assert_text "station two stream title" 0 "Test Track Two"
assert_text "station two artist" 0 "Test Artist Two"

# Previous returns to station one.
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 10
assert_text "previous returns to station one" 0 "Test Track One"
capture "radio-previous"

# Verify URL/M3U editor exists.
tap_tab "WebRadio" "=WebRadio"
tap_text "add station" 1 "Sender per URL hinzufügen"
sleep 2
assert_text "URL and playlist editor" 1 "M3U" "PLS"
capture "radio-url-editor"
adb shell input keyevent KEYCODE_BACK || true
sleep 2

# Verify search UI and attempt a real Radio Browser query. Network result is recorded, not hard-required.
tap_text "radio search" 1 "=Sender suchen"
tap_text "radio search field" 1 "Sender, Land oder Genre"
adb shell input text "ORF"
adb shell input keyevent KEYCODE_ENTER
sleep 12
capture "radio-browser-search"

# Radio playback must not pollute the normal music history.
tap_tab "Hörverlauf" "=Hörverlauf" "=History"
assert_text "local history remains available" 1 "Lokal" "Local"
assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Track One" "Test Track Two"
capture "history-after-radio"

adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
adb shell dumpsys activity activities > "$RESULTS_DIR/activities.txt" 2>&1 || true
adb shell dumpsys window windows > "$RESULTS_DIR/windows.txt" 2>&1 || true

python3 - "$RESULTS_DIR/logcat.txt" "$RESULTS_DIR/crashes.txt" "$PACKAGE_NAME" <<'PY'
import re, sys
log, out, package = sys.argv[1:]
text=open(log,encoding='utf-8',errors='ignore').read()
patterns=[r'FATAL EXCEPTION', r'ANR in '+re.escape(package), r'Process: '+re.escape(package)+r'.*has died']
hits=[line for line in text.splitlines() if any(re.search(p,line,re.I) for p in patterns)]
open(out,'w',encoding='utf-8').write('\n'.join(hits))
if hits:
 print('\n'.join(hits)); raise SystemExit(1)
PY

cat > "$RESULTS_DIR/summary.md" <<'EOF'
## Dudu7 WebRadio smoke test

- Original local history chip visible
- Normal YouTube Music item visible in original history
- Saved stations visible in the right pane
- ICY artist/title metadata visible in the left player
- Previous/next switches the saved radio queue
- Direct URL / M3U / PLS editor available
- Radio Browser search exercised
- Radio stations excluded from normal music history
- No app crash or ANR detected
EOF

echo "Dudu7 WebRadio smoke test passed"
