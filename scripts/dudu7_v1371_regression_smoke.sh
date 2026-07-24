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
exec > >(tee "$RESULTS_DIR/regression-smoke.log") 2>&1
step=0

capture() {
    step=$((step + 1))
    local prefix
    prefix=$(printf '%02d-%s' "$step" "$1")
    adb exec-out screencap -p > "$RESULTS_DIR/${prefix}.png" || true
    dump_ui "$RESULTS_DIR/${prefix}.xml" || true
}

dump_ui() {
    local output="${1:-$RESULTS_DIR/current-window.xml}"
    local attempt
    for attempt in 1 2 3; do
        rm -f "$output"
        if timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 \
            && adb pull /sdcard/window.xml "$output" >/dev/null 2>&1 \
            && test -s "$output" \
            && python3 - "$output" <<'PY'
import sys, xml.etree.ElementTree as ET
ET.parse(sys.argv[1])
PY
        then
            return 0
        fi
        sleep 2
    done
    return 1
}

find_coords() {
    local right_only="$1"; shift
    dump_ui "$RESULTS_DIR/current-window.xml" || return 1
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
            if (right_only != '1' or l >= width//2) and r > l and b > t:
                fallback = (l,t,r,b)
                if cur.attrib.get('clickable') == 'true':
                    print((l+r)//2, (t+b)//2)
                    raise SystemExit(0)
        cur = parent.get(cur)
    if fallback:
        l,t,r,b = fallback
        print((l+r)//2, (t+b)//2)
        raise SystemExit(0)
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
    local attempt
    for attempt in 1 2 3 4; do
        if find_coords "$right" "$@" >/dev/null; then
            echo "PASS: $label"
            return 0
        fi
        sleep 2
    done
    echo "FAIL: $label" >&2
    capture "assertion-failure-${label// /-}"
    return 1
}

tap_tab() {
    local label="$1"; shift
    local attempt
    for attempt in 1 2 3 4; do
        if tap_text "$label" 0 "$@"; then return 0; fi
        adb shell input swipe $((DUDU_WIDTH*9/10)) 75 $((DUDU_WIDTH*55/100)) 75 450 || true
        sleep 2
    done
    echo "FAIL: could not open tab $label" >&2
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
 {"uuid":"test-radio-one","name":"Test Radio One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"http://10.0.2.2:8000/logo1.png","manualFavicon":False,"country":"Austria","language":"German","tags":"Test,Rock","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-two","name":"Test Radio Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"http://10.0.2.2:8000/logo2.png","manualFavicon":False,"country":"Austria","language":"German","tags":"Test,Pop","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-three","name":"Test Radio Three","streamUrl":"http://10.0.2.2:8000/station3","homepage":"http://10.0.2.2:8000/station3-home","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Test,Indie","codec":"MP3","bitrate":96}
]
raw=json.dumps(stations,separators=(',',':'))
print('<?xml version="1.0" encoding="utf-8" standalone="yes" ?>')
print('<map><string name="stations">'+html.escape(raw)+'</string></map>')
PY
    adb push /tmp/metrolist_webradio.xml /data/local/tmp/metrolist_webradio.xml >/dev/null
    adb shell run-as "$PACKAGE_NAME" mkdir -p shared_prefs
    adb shell run-as "$PACKAGE_NAME" cp /data/local/tmp/metrolist_webradio.xml shared_prefs/metrolist_webradio.xml
}

assert_split_half() {
    dump_ui "$RESULTS_DIR/split.xml"
    python3 - "$RESULTS_DIR/split.xml" "$DUDU_WIDTH" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width = sys.argv[1], int(sys.argv[2])
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
labels = {'warteschlange','queue'}
for node in root.iter('node'):
    values = {node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()}
    if not values & labels:
        continue
    cur = node
    candidates = []
    while cur is not None:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            if r > width // 2 and b > t:
                candidates.append((l,t,r,b,cur.attrib.get('selected') == 'true'))
        cur = parent.get(cur)
    expected = width // 2
    for l,t,r,b,selected in candidates:
        if expected - 55 <= l <= expected + 100 and (selected or r >= width - 20):
            print(f'PASS: right pane begins near half width: left={l}, expected={expected}, selected={selected}')
            raise SystemExit(0)
raise SystemExit('Right pane does not begin near the 50/50 split')
PY
}

assert_scroll_moved() {
    local before="$1" after="$2"
    python3 - "$before" "$after" "$DUDU_WIDTH" "$DUDU_HEIGHT" <<'PY'
import re, sys, xml.etree.ElementTree as ET
before_path, after_path, width, height = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ignore = {'warteschlange','queue','bibliothek','library','suche','search','hörverlauf','history','webradio','startseite','home','rick astley'}
def collect(path):
    root=ET.parse(path).getroot(); out={}
    for node in root.iter('node'):
        value=(node.attrib.get('text','').strip() or node.attrib.get('content-desc','').strip())
        key=value.casefold()
        if not value or key in ignore: continue
        m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.attrib.get('bounds',''))
        if not m: continue
        l,t,r,b=map(int,m.groups())
        if l < width//2 or t < 105 or b > height-8: continue
        out.setdefault(key,[]).append((t+b)//2)
    return out
before=collect(before_path); after=collect(after_path)
movements=[]
for key in before.keys() & after.keys():
    for y1 in before[key]:
        for y2 in after[key]:
            movements.append((y1-y2,key,y1,y2))
best=max(movements, default=(0,'',0,0))
new_keys=set(after)-set(before)
lost_keys=set(before)-set(after)
if best[0] >= 55 or (len(new_keys) >= 2 and len(lost_keys) >= 2):
    print(f'PASS: right artist pane scrolled; best movement={best}, new={sorted(new_keys)[:5]}, lost={sorted(lost_keys)[:5]}')
else:
    raise SystemExit(f'Artist pane did not visibly scroll; best={best}, new={sorted(new_keys)}, lost={sorted(lost_keys)}')
PY
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

adb install -r "$APK_PATH" | tee "$RESULTS_DIR/install.txt"
adb shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS || true
adb shell pm revoke "$PACKAGE_NAME" android.permission.RECORD_AUDIO || true
seed_radios
adb logcat -c || true
adb shell am force-stop "$PACKAGE_NAME" || true
adb shell am start -W -n "$PACKAGE_NAME/$ACTIVITY_NAME" | tee "$RESULTS_DIR/activity-start.txt"
sleep 12
try_dialogs
capture "launch"

if [[ "${ARTIST_SCROLL_ONLY:-0}" == "1" ]]; then
    # Deterministic scroll validation: use the local ICY test station instead of
    # depending on a YouTube deep link and external network timing.
    tap_tab "WebRadio" "=WebRadio"
    assert_text "saved section" 1 "=Gespeichert"
    assert_text "station one" 1 "=Test Radio One"
    tap_text "play station one" 1 "=Test Radio One"
    sleep 14
    assert_text "radio title" 0 "=Never Gonna Give You Up"
    assert_text "radio artist" 0 "=Rick Astley"
    tap_text "open artist" 0 "=Rick Astley"
    sleep 15
    assert_text "artist page title" 1 "=Rick Astley"

    adb logcat -c || true
    dump_ui "$RESULTS_DIR/artist-before-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*30/100)) 700
    sleep 4
    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    adb logcat -d -v threadtime > "$RESULTS_DIR/right-pane-scroll-log.txt" || true
    grep -q "Dudu7RightPaneScroll" "$RESULTS_DIR/right-pane-scroll-log.txt"
    capture "artist-after-real-scroll"

    if ! tap_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
        sleep 3
        tap_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
    sleep 10
    assert_text "artist songs detail content" 1 "=Never Gonna Give You Up" "=Together Forever"
    capture "artist-songs-detail"

    adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
    python3 - "$RESULTS_DIR/logcat.txt" "$PACKAGE_NAME" <<'PY'
import re, sys
text=open(sys.argv[1],encoding='utf-8',errors='ignore').read(); package=sys.argv[2]
hits=[line for line in text.splitlines() if 'FATAL EXCEPTION' in line or re.search(r'ANR in '+re.escape(package),line)]
if hits:
    print('\n'.join(hits)); raise SystemExit(1)
print('PASS: no crash or ANR detected')
PY

    cat > "$RESULTS_DIR/summary.md" <<'EOF'
## Metrolist Dudu7 13.7.1 artist scroll regression

- PASS: local WebRadio station started
- PASS: radio artist page opened in the right pane
- PASS: right-pane bridge received the vertical drag
- PASS: artist content visibly moved after the swipe
- PASS: Top Songs detail navigation opened
- PASS: no crash or ANR detected
EOF
    echo "Dudu7 artist scroll regression passed."
    exit 0
fi

# Normal playback establishes the left player and a queue for shuffle testing.
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/deep-link.txt" || true
sleep 20
try_dialogs
assert_text "normal title" 0 "=Never Gonna Give You Up"
assert_text "normal artist" 0 "=Rick Astley"
assert_split_half

# Normalize shuffle off, then prove two fresh enable seeds with an off cycle between.
tap_text "disable pre-existing shuffle" 0 "=Zufallswiedergabe aktiviert" || true
adb logcat -c || true
tap_text "enable shuffle first" 0 "=Zufallswiedergabe deaktiviert"
tap_text "disable shuffle" 0 "=Zufallswiedergabe aktiviert"
tap_text "enable shuffle second" 0 "=Zufallswiedergabe deaktiviert"
sleep 2
adb logcat -d -v brief > "$RESULTS_DIR/shuffle-log.txt"
python3 - "$RESULTS_DIR/shuffle-log.txt" <<'PY'
import re, sys
text=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
seeds=re.findall(r'Shuffle enabled with fresh seed=(\d+)',text)
if len(seeds) < 2 or len(set(seeds[-2:])) != 2:
    raise SystemExit(f'Expected two distinct shuffle seeds, got {seeds}')
if 'Shuffle disabled; original timeline order active' not in text:
    raise SystemExit('Shuffle disable/original-order marker missing')
print('PASS: shuffle generated distinct orders and restored original order when disabled:', seeds[-2:])
PY

# Favorites list and grid must expose the dedicated drag handle.
tap_tab "WebRadio" "=WebRadio"
assert_text "saved section" 1 "=Gespeichert"
assert_text "station one" 1 "=Test Radio One"
assert_text "list drag handle" 1 "=Sender verschieben"
tap_text "switch to grid" 1 "=Kachelansicht"
assert_text "grid active" 1 "=Listenansicht"
assert_text "grid drag handle" 1 "=Sender verschieben"
capture "webradio-grid-drag-handle"
tap_text "switch to list" 1 "=Listenansicht"

# Open station one, follow artist link, and verify actual movement after a swipe.
tap_text "play station one" 1 "=Test Radio One"
sleep 14
assert_text "radio title" 0 "=Never Gonna Give You Up"
assert_text "radio artist" 0 "=Rick Astley"
tap_text "open artist" 0 "=Rick Astley"
sleep 15
assert_text "artist page title" 1 "=Rick Astley"
dump_ui "$RESULTS_DIR/artist-before-scroll.xml"
adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*30/100)) 700
sleep 4
dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
adb logcat -d -v threadtime > "$RESULTS_DIR/artist-scroll-log.txt" || true
if ! assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"; then
    grep -E "Dudu7ArtistScroll|Embedded artist drag" "$RESULTS_DIR/artist-scroll-log.txt" || true
    capture "artist-scroll-failure"
    exit 1
fi
grep -q "Embedded artist drag ended" "$RESULTS_DIR/artist-scroll-log.txt"
capture "artist-after-real-scroll"

# Exercise a real section navigation when its title is available.
if ! tap_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
    sleep 3
    tap_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
fi
sleep 10
assert_text "artist songs detail content" 1 "=Never Gonna Give You Up" "=Together Forever"
capture "artist-songs-detail"
adb shell input keyevent KEYCODE_BACK
sleep 4
assert_text "back to artist page" 1 "=Rick Astley"
adb shell input keyevent KEYCODE_BACK
sleep 4
assert_text "back to WebRadio favorites" 1 "=Gespeichert"

# Direct recognition must decode the stream without microphone permission.
tap_text "play ambiguous station" 1 "=Test Radio Three"
sleep 12
assert_text "ambiguous metadata" 0 "=Station identification"
assert_text "direct recognition action" 0 "=Musik erkennen"
adb shell pm revoke "$PACKAGE_NAME" android.permission.RECORD_AUDIO || true
adb logcat -c || true
tap_text "start direct stream recognition" 0 "=Musik erkennen"
assert_text "recognition started" 0 "=Musik wird erkannt"
sleep 38
adb logcat -d -v threadtime > "$RESULTS_DIR/direct-recognition-log.txt"
grep -q 'Direct radio stream decoded:' "$RESULTS_DIR/direct-recognition-log.txt"
if grep -q 'Microphone permission not granted' "$RESULTS_DIR/direct-recognition-log.txt"; then
    echo 'FAIL: direct recognition tried to use microphone permission' >&2
    exit 1
fi
if grep -q 'Direct radio-stream recognition failed' "$RESULTS_DIR/direct-recognition-log.txt"; then
    echo 'FAIL: direct radio stream decoder failed' >&2
    exit 1
fi
echo 'PASS: direct stream recognition decoded audio without microphone permission'

capture "final"
adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
python3 - "$RESULTS_DIR/logcat.txt" "$PACKAGE_NAME" <<'PY'
import re, sys
text=open(sys.argv[1],encoding='utf-8',errors='ignore').read(); package=sys.argv[2]
hits=[line for line in text.splitlines() if 'FATAL EXCEPTION' in line or re.search(r'ANR in '+re.escape(package),line)]
if hits:
    print('\n'.join(hits)); raise SystemExit(1)
print('PASS: no crash or ANR detected')
PY

cat > "$RESULTS_DIR/summary.md" <<'EOF'
## Metrolist Dudu7 13.7.1 focused regression

- 50/50 pane boundary verified from the live UI hierarchy
- Shuffle toggled off/on twice with two distinct seeds and original-order restore marker
- WebRadio list and grid both expose the dedicated drag handle
- Original artist page opened in the right pane
- Artist page movement verified by before/after UI coordinates, not merely by visible text
- Artist song-section navigation and back stack verified
- Direct radio-stream decoding verified with RECORD_AUDIO permission revoked
- No app crash or ANR detected
EOF

echo 'Metrolist Dudu7 13.7.1 focused regression passed'
