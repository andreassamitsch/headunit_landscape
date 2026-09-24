#!/usr/bin/env bash
set -Eeuo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7.debug}"
ACTIVITY_NAME="${ACTIVITY_NAME:-com.metrolist.music.MainActivity}"
APK_PATH="${APK_PATH:?APK_PATH must point to the emulator APK}"
RESULTS_DIR="${RESULTS_DIR:-ui-test-results}"
DUDU_WIDTH="${DUDU_WIDTH:-1280}"
DUDU_HEIGHT="${DUDU_HEIGHT:-720}"
DUDU_DENSITY="${DUDU_DENSITY:-200}"

mkdir -p "$RESULTS_DIR"
exec > >(tee "$RESULTS_DIR/artist-subpages-smoke.log") 2>&1
step=0
record_pid=""

finalize() {
    set +e
    adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1
    if [[ -n "$record_pid" ]]; then
        wait "$record_pid" 2>/dev/null || true
    fi
    adb pull /sdcard/dudu7-artist-subpages.mp4 "$RESULTS_DIR/dudu7-artist-subpages.mp4" >/dev/null 2>&1 || true
    adb shell dumpsys activity activities > "$RESULTS_DIR/activities.txt" 2>&1 || true
    adb shell dumpsys window windows > "$RESULTS_DIR/windows.txt" 2>&1 || true
}
trap finalize EXIT

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

capture() {
    step=$((step + 1))
    local prefix
    prefix=$(printf '%02d-%s' "$step" "$1")
    adb exec-out screencap -p > "$RESULTS_DIR/${prefix}.png" || true
    dump_ui "$RESULTS_DIR/${prefix}.xml" || true
}

find_clickable_coords() {
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
    while cur is not None:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            if (right_only != '1' or l >= width//2) and r > l and b > t and cur.attrib.get('clickable') == 'true':
                print((l+r)//2, (t+b)//2)
                raise SystemExit(0)
        cur = parent.get(cur)
raise SystemExit(1)
PY
}

tap_clickable() {
    local label="$1"; local right="$2"; shift 2
    local coords
    coords=$(find_clickable_coords "$right" "$@") || return 1
    echo "Tapping $label at $coords"
    adb shell input tap $coords
    sleep 4
}

find_text_coords() {
    local right_only="$1"; shift
    dump_ui "$RESULTS_DIR/current-window.xml" || return 1
    python3 - "$RESULTS_DIR/current-window.xml" "$DUDU_WIDTH" "$right_only" "$@" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width, right_only, *needles = sys.argv[1:]
width = int(width)
exact = [n[1:].casefold() for n in needles if n.startswith('=')]
partial = [n.casefold() for n in needles if not n.startswith('=')]
root = ET.parse(path).getroot()
for node in root.iter('node'):
    values = [node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()]
    hay = ' '.join(v for v in values if v)
    if not any(v == n for v in values for n in exact) and not (hay and any(n in hay for n in partial)):
        continue
    m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    if not m:
        continue
    l,t,r,b = map(int,m.groups())
    if (right_only != '1' or l >= width//2) and r > l and b > t:
        print((l+r)//2, (t+b)//2)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

assert_text() {
    local label="$1"; local right="$2"; shift 2
    local attempt
    for attempt in 1 2 3 4 5; do
        if find_text_coords "$right" "$@" >/dev/null; then
            echo "PASS: $label"
            return 0
        fi
        sleep 2
    done
    echo "FAIL: $label" >&2
    capture "failure-${label// /-}"
    return 1
}

try_dialogs() {
    local i
    for i in 1 2 3 4 5 6; do
        tap_clickable "dialog" 0 \
            "allow" "zulassen" "while using" "bei verwendung" \
            "continue" "weiter" "skip" "überspringen" \
            "not now" "später" "got it" "verstanden" || break
    done
}

seed_radios() {
    python3 - > /tmp/metrolist_webradio.xml <<'PY'
import html, json
stations = [
 {"uuid":"test-radio-one","name":"Test Radio One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"http://10.0.2.2:8000/logo1.png","manualFavicon":False,"country":"Austria","language":"German","tags":"Test,Rock","codec":"MP3","bitrate":96}
]
raw=json.dumps(stations,separators=(',',':'))
print('<?xml version="1.0" encoding="utf-8" standalone="yes" ?>')
print('<map><string name="stations">'+html.escape(raw)+'</string></map>')
PY
    adb push /tmp/metrolist_webradio.xml /data/local/tmp/metrolist_webradio.xml >/dev/null
    adb shell run-as "$PACKAGE_NAME" mkdir -p shared_prefs
    adb shell run-as "$PACKAGE_NAME" cp /data/local/tmp/metrolist_webradio.xml shared_prefs/metrolist_webradio.xml
}

open_tab() {
    local label="$1"; shift
    local attempt
    for attempt in 1 2 3 4; do
        if tap_clickable "$label" 0 "$@"; then return 0; fi
        adb shell input swipe $((DUDU_WIDTH*9/10)) 75 $((DUDU_WIDTH*55/100)) 75 450 || true
        sleep 2
    done
    echo "FAIL: tab $label not found" >&2
    return 1
}

scroll_to_and_tap_section() {
    local label="$1"; shift
    local attempt
    for attempt in $(seq 1 10); do
        if tap_clickable "$label" 1 "$@"; then return 0; fi
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*84/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*25/100)) 650
        sleep 2
    done
    for attempt in $(seq 1 8); do
        if tap_clickable "$label" 1 "$@"; then return 0; fi
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*25/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*84/100)) 650
        sleep 2
    done
    echo "FAIL: section $label not found" >&2
    return 1
}

assert_original_grid_and_get_first_card() {
    local xml="$1"
    python3 - "$xml" "$DUDU_WIDTH" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width = sys.argv[1], int(sys.argv[2])
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
exclude = {
 'warteschlange','queue','bibliothek','library','webradio','fm','suche','search','hörverlauf','history',
 'alben','albums','singles & eps','singles und eps','zurück','back','mehr optionen','more options'
}
cards = {}
for node in root.iter('node'):
    value = (node.attrib.get('text','').strip() or node.attrib.get('content-desc','').strip())
    if not value or value.casefold() in exclude:
        continue
    cur = node
    while cur is not None:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            w,h = r-l,b-t
            if l >= width//2 and t >= 115 and 105 <= w <= 350 and h >= 75 and cur.attrib.get('clickable') == 'true':
                cards.setdefault((l,t,r,b), value)
                break
        cur = parent.get(cur)
rows = list(cards.items())
if len(rows) < 2:
    raise SystemExit(f'Original compact grid not detected; compact clickable cards={rows}')
pair = None
for i,(rect1,title1) in enumerate(rows):
    l1,t1,r1,b1=rect1; x1=(l1+r1)//2; y1=(t1+b1)//2
    for rect2,title2 in rows[i+1:]:
        l2,t2,r2,b2=rect2; x2=(l2+r2)//2; y2=(t2+b2)//2
        if abs(y1-y2) <= 110 and abs(x1-x2) >= 110:
            pair=(rect1,title1,rect2,title2)
            break
    if pair: break
if pair is None:
    raise SystemExit(f'Cards exist but no side-by-side grid row was found: {rows}')
rect,title = rows[0]
l,t,r,b=rect
print(f'{(l+r)//2}\t{(t+b)//2}\t{title}')
print(f'PASS: original MetroList adaptive grid detected with {len(rows)} compact cards; pair={pair}', file=sys.stderr)
PY
}

assert_album_detail() {
    local xml="$1" expected="$2"
    python3 - "$xml" "$DUDU_WIDTH" "$expected" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width, expected = sys.argv[1], int(sys.argv[2]), sys.argv[3]
root=ET.parse(path).getroot(); parent={child:node for node in root.iter() for child in node}
expected_cf=expected.casefold()
texts=[]; song_rows={}
exclude={'warteschlange','queue','bibliothek','library','webradio','fm','suche','search','hörverlauf','history',
         'wiedergabe','play','pause','zurück','back','mehr optionen','more options','radio','shuffle'}
for node in root.iter('node'):
    value=(node.attrib.get('text','').strip() or node.attrib.get('content-desc','').strip())
    if not value: continue
    m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',node.attrib.get('bounds',''))
    if not m: continue
    l,t,r,b=map(int,m.groups())
    if l < width//2: continue
    texts.append((value,l,t,r,b))
    if t < 175 or value.casefold() in exclude or value.casefold()==expected_cf: continue
    cur=node
    while cur is not None:
        cm=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
        if cm:
            cl,ct,cr,cb=map(int,cm.groups())
            if cl >= width//2 and cr-cl >= 330 and cb-ct >= 45 and cur.attrib.get('clickable')=='true':
                song_rows.setdefault((cl,ct,cr,cb),value)
                break
        cur=parent.get(cur)
if not any(value.casefold()==expected_cf for value, *_ in texts):
    raise SystemExit(f'Opened album title is missing from detail screen: expected={expected!r}, texts={texts[:30]}')
if not song_rows:
    raise SystemExit(f'No full-width clickable song rows found for album {expected!r}; texts={texts[:40]}')
print(f'PASS: album detail opened for {expected!r} with {len(song_rows)} song rows: {list(song_rows.values())[:5]}')
PY
}

assert_no_crash() {
    python3 - "$RESULTS_DIR/logcat.txt" "$PACKAGE_NAME" <<'PY'
import re, sys
text=open(sys.argv[1],encoding='utf-8',errors='ignore').read(); package=sys.argv[2]
hits=[line for line in text.splitlines() if 'FATAL EXCEPTION' in line or re.search(r'ANR in '+re.escape(package),line)]
if hits:
    print('\n'.join(hits)); raise SystemExit(1)
print('PASS: no crash or ANR detected')
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

open_tab "WebRadio" "=WebRadio"
assert_text "saved WebRadio section" 1 "=Gespeichert" "=Saved"
assert_text "test radio station" 1 "=Test Radio One"
tap_clickable "Test Radio One" 1 "=Test Radio One"
sleep 14
assert_text "radio track title in left player" 0 "=Never Gonna Give You Up"
assert_text "radio artist in left player" 0 "=Rick Astley"
tap_clickable "Rick Astley artist" 0 "=Rick Astley"
sleep 16
assert_text "artist page in right pane" 1 "=Rick Astley"
capture "artist-page"

adb shell screenrecord --time-limit 180 /sdcard/dudu7-artist-subpages.mp4 >/dev/null 2>&1 &
record_pid=$!
sleep 2

scroll_to_and_tap_section "Albums section" "=Albums" "=Alben"
sleep 14
assert_text "Albums category title" 1 "=Albums" "=Alben"
assert_text "left player remains visible on Albums" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/albums-grid.xml"
album_card=$(assert_original_grid_and_get_first_card "$RESULTS_DIR/albums-grid.xml")
album_x=$(printf '%s' "$album_card" | cut -f1)
album_y=$(printf '%s' "$album_card" | cut -f2)
album_title=$(printf '%s' "$album_card" | cut -f3-)
echo "Opening album card: $album_title at $album_x $album_y"
capture "albums-original-grid"
adb shell input tap "$album_x" "$album_y"
sleep 16
dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
assert_text "left player remains visible on album detail" 0 "=Rick Astley"
capture "album-detail-with-songs"

adb shell input keyevent KEYCODE_BACK
sleep 5
dump_ui "$RESULTS_DIR/albums-grid-return.xml"
assert_original_grid_and_get_first_card "$RESULTS_DIR/albums-grid-return.xml" >/dev/null
adb shell input keyevent KEYCODE_BACK
sleep 6
assert_text "returned to artist after Albums" 1 "=Rick Astley"

scroll_to_and_tap_section "Singles and EPs section" "=Singles & EPs" "=Singles und EPs" "Singles & EPs" "Singles und EPs"
sleep 14
assert_text "Singles and EPs category title" 1 "=Singles & EPs" "=Singles und EPs" "Singles & EPs" "Singles und EPs"
assert_text "left player remains visible on Singles and EPs" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/singles-eps-grid.xml"
single_card=$(assert_original_grid_and_get_first_card "$RESULTS_DIR/singles-eps-grid.xml")
single_x=$(printf '%s' "$single_card" | cut -f1)
single_y=$(printf '%s' "$single_card" | cut -f2)
single_title=$(printf '%s' "$single_card" | cut -f3-)
echo "Opening single/EP card: $single_title at $single_x $single_y"
capture "singles-eps-original-grid"
adb shell input tap "$single_x" "$single_y"
sleep 16
dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
assert_text "left player remains visible on single or EP detail" 0 "=Rick Astley"
capture "single-ep-detail-with-songs"

adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
assert_no_crash

cat > "$RESULTS_DIR/summary.md" <<EOF
## Metrolist dudu7 13.7.20 artist subpage emulator validation

- PASS: Rick Astley artist page opened inside the right Dudu7 pane
- PASS: Albums opened the original MetroList adaptive grid
- PASS: Album card "$album_title" opened the original album detail with song rows
- PASS: Back navigation returned through Albums to the artist page
- PASS: Singles & EPs opened the original MetroList adaptive grid
- PASS: Single/EP card "$single_title" opened the original album detail with song rows
- PASS: Left player remained visible throughout
- PASS: No crash or ANR detected
EOF

echo "Dudu7 original artist subpages emulator regression passed."
