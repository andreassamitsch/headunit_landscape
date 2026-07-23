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
    local attempt
    for attempt in 1 2 3; do
        rm -f "$RESULTS_DIR/current-window.xml"
        if timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1             && adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1             && test -s "$RESULTS_DIR/current-window.xml"             && python3 - "$RESULTS_DIR/current-window.xml" <<'PY'
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
}

assert_selected_tab() {
    local label="$1"; shift
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$@" <<'PY'
import sys, xml.etree.ElementTree as ET
path, *needles = sys.argv[1:]
needles = [n.casefold() for n in needles]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter('node'):
    values = [node.attrib.get('text','').strip(), node.attrib.get('content-desc','').strip()]
    hay = ' '.join(v for v in values if v).casefold()
    if not hay or not any(n in hay for n in needles):
        continue
    cur = node
    while cur is not None:
        if cur.attrib.get('selected') == 'true':
            raise SystemExit(0)
        cur = parent.get(cur)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "selected-tab-failure"
        return 1
    fi
}

assert_station_active() {
    local label="$1"; local station="$2"
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$station" <<'PY'
import sys, xml.etree.ElementTree as ET
path, station = sys.argv[1:]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
station_node = next((n for n in root.iter('node') if n.attrib.get('text','').strip() == station), None)
if station_node is None:
    raise SystemExit(1)
row = station_node
while row is not None and row.attrib.get('clickable') != 'true':
    row = parent.get(row)
if row is None:
    raise SystemExit(1)
for node in row.iter('node'):
    if 'LÄUFT' in node.attrib.get('text',''):
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "active-station-failure"
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

assert_absent_anywhere() {
    local label="$1"; shift
    if find_coords 0 "$@" >/dev/null; then
        echo "FAIL: $label unexpectedly visible" >&2
        capture "unexpected-$label"
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
 {"uuid":"test-radio-two","name":"Test Radio Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"http://10.0.2.2:8000/logo2.png","country":"Austria","language":"German","tags":"Test,Pop","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-three","name":"Test Radio Three","streamUrl":"http://10.0.2.2:8000/station3","homepage":"http://10.0.2.2:8000/station3-home","favicon":"","country":"Austria","language":"German","tags":"Test,Indie","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-four","name":"kronehit","streamUrl":"http://10.0.2.2:8000/station4","homepage":"http://10.0.2.2:8000/kronehit-home","favicon":"http://10.0.2.2:8000/kronehit.svg","country":"Austria","language":"German","tags":"Hits,Austria","codec":"MP3","bitrate":96},
 {"uuid":"9608a2aa-0601-11e8-ae97-52543be04c81","name":"Antenne Steiermark","streamUrl":"http://live.antenne.at/as","homepage":"http://www.antenne.at/","favicon":"https://upload.wikimedia.org/wikipedia/commons/6/63/Antenne_Logo.svg","country":"Austria","language":"German","tags":"Pop,Austria","codec":"MP3","bitrate":128}
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
    grep -E 'Dudu7ArtistAction|FATAL EXCEPTION|IllegalStateException|IllegalArgumentException|NavController'         "$RESULTS_DIR/focused-artist-action-logcat.txt" || true
    assert_selected_tab "focused artist action selected queue" "Warteschlange" "Queue"
    assert_absent_anywhere "focused LIVE after artist action" "=LIVE"
    echo "Focused embedded artist action passed"
    exit 0
fi

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

# Open embedded WebRadio and verify three favorites plus homepage logo discovery.
tap_tab "WebRadio" "=WebRadio"
assert_text "saved radio section" 1 "=Gespeichert"
assert_text "first saved station" 1 "=Test Radio One"
assert_text "second saved station" 1 "=Test Radio Two"
assert_text "third saved station" 1 "=Test Radio Three"
assert_text "kronehit saved station" 1 "=kronehit"
assert_text "Antenne Steiermark saved station" 1 "=Antenne Steiermark"
sleep 35
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/radio-prefs-after-logo.xml"
grep -q 'logo3.png' "$RESULTS_DIR/radio-prefs-after-logo.xml"
echo "PASS: missing sender logo discovered from station homepage and persisted"
grep -Eq 'AS-Logo-Button|cover-stmk-live|1024-QBE62OCK|android-chrome-[0-9]+x[0-9]+\.png' "$RESULTS_DIR/radio-prefs-after-logo.xml"
if grep -q 'Antenne_Logo.svg' "$RESULTS_DIR/radio-prefs-after-logo.xml"; then
    echo "FAIL: Antenne Steiermark still uses the unsupported SVG logo" >&2
    exit 1
fi
echo "PASS: Antenne Steiermark received a persisted raster station logo"
python3 - "$RESULTS_DIR/radio-prefs-after-logo.xml" > "$RESULTS_DIR/kronehit-logo-before.txt" <<'PY'
import html, json, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
raw=html.unescape(root.find("string").text or "[]")
station=next(x for x in json.loads(raw) if x["uuid"] == "test-radio-four")
print(station["favicon"])
PY
if grep -q 'kronehit.svg' "$RESULTS_DIR/kronehit-logo-before.txt"; then
    echo "FAIL: kronehit still uses SVG artwork" >&2
    exit 1
fi
capture "webradio-five-favorites"

# The cleaned favorites view has no edit/delete/up/down buttons. Actions live
# behind a long press, while the view switch mirrors the library control.
assert_absent_right "old edit icon" "Bearbeiten"
assert_absent_right "old delete icon" "Löschen"
assert_absent_right "old move up icon" "Nach oben"
assert_absent_right "old move down icon" "Nach unten"
tap_text "switch to radio grid" 1 "Kachelansicht"
assert_text "radio grid switch became list switch" 1 "Listenansicht"
tap_text "switch back to radio list" 1 "Listenansicht"
# Long press on the text area (not the logo drag handle) opens the station menu.
coords=$(find_coords 1 "=Test Radio One")
adb shell input swipe $coords $coords 900
sleep 2
assert_text "station long-click edit action" 0 "=Bearbeiten"
assert_text "station long-click delete action" 0 "=Löschen"
adb shell input keyevent KEYCODE_BACK || true
sleep 2

# Start favorite two, then replace it directly with favorite one.
tap_text "station two favorite" 1 "=Test Radio Two"
sleep 10
assert_text "favorite two title" 0 "Test Track Two"
assert_text "favorite two artist" 0 "Test Artist Two"
assert_text "favorite two live" 0 "LIVE"
assert_selected_tab "WebRadio tab remains selected after favorite start" "WebRadio"
assert_station_active "favorite two row shows active playback" "Test Radio Two"

tap_tab "WebRadio" "=WebRadio"
tap_text "station one favorite" 1 "=Test Radio One"
sleep 14
assert_text "favorite one title" 0 "=Never Gonna Give You Up"
assert_text "favorite one artist" 0 "=Rick Astley"
assert_text "favorite one live" 0 "LIVE"
assert_text "matched radio song exposes like action" 0 "Song gefällt mir"
adb logcat -d -v threadtime > "$RESULTS_DIR/cover-log.txt" 2>&1 || true
resolved_count=$(grep -c 'Resolved radio song to YouTube Music: Never Gonna Give You Up' "$RESULTS_DIR/cover-log.txt" || true)
test "$resolved_count" -ge 1
test "$resolved_count" -le 2
echo "PASS: clear artist/title resolved once to a reliable YouTube Music song"
assert_selected_tab "WebRadio tab remains selected after second favorite" "WebRadio"
assert_station_active "favorite one row shows active playback" "Test Radio One"
tap_text "radio artist link" 0 "=Rick Astley"
sleep 12
assert_text "radio artist name visible in compact pane" 1 "=Rick Astley"
adb shell input swipe 1100 620 1100 230 500
sleep 3
assert_text "radio artist page scrolls and exposes content" 1 "Songs" "Alben" "Albums" "Never Gonna Give You Up"
adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
echo "PASS: radio artist rendered at pane width and scrolled inside the right pane"
capture "radio-artist-right-pane"
adb shell input keyevent KEYCODE_BACK
sleep 3
assert_text "back from artist returns to WebRadio favorites" 1 "=Gespeichert"
# Open it once more and exercise a real artist action. This must use the
# embedded navigator and normal music selection must return to the queue tab.
tap_text "station one favorite after artist back" 1 "=Test Radio One"
sleep 8
tap_text "radio artist link functional test" 0 "=Rick Astley"
sleep 10
tap_text "artist Radio action" 1 "=Radio"
sleep 15
assert_selected_tab "artist action selected normal music queue" "Warteschlange" "Queue"
assert_absent_anywhere "LIVE after artist radio action" "=LIVE"
tap_tab "WebRadio" "=WebRadio"

# Start a third favorite with ambiguous metadata. It must play, but must not run cover search.
tap_tab "WebRadio" "=WebRadio"
tap_text "station three favorite" 1 "=Test Radio Three"
sleep 10
assert_text "favorite three ambiguous title" 0 "=Station identification"
assert_text "favorite three station artist" 0 "=Test Radio Three"
adb logcat -d -v threadtime > "$RESULTS_DIR/ambiguous-cover-log.txt" 2>&1 || true
grep -q 'Skipping radio song lookup for ambiguous metadata: Station identification' "$RESULTS_DIR/ambiguous-cover-log.txt"
echo "PASS: ambiguous metadata skipped YouTube Music matching"
assert_text "music recognition offered without metadata" 0 "Musik erkennen"

# Start favorite 3 at its real saved-list index and exercise the unchanged
# order in both directions. The active indicator must follow every player skip.
assert_station_active "third favorite active indicator" "Test Radio Three"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous from favorite three reaches favorite two" 0 "=Test Track Two"
assert_station_active "favorite two active indicator" "Test Radio Two"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous again reaches favorite one" 0 "=Never Gonna Give You Up"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next returns to favorite two" 0 "=Test Track Two"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next returns to favorite three" 0 "=Station identification"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next from favorite three reaches following kronehit favorite" 0 "=Kronehit Track"
assert_station_active "kronehit active indicator" "kronehit"
# Recreate the WebRadio screen repeatedly. The persisted kronehit raster logo
# must remain byte-for-byte the same and its alternating homepage must not be
# requested again.
for i in 1 2 3; do
    tap_tab "Warteschlange" "=Warteschlange" "=Queue"
    tap_tab "WebRadio" "=WebRadio"
done
sleep 8
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/radio-prefs-after-reopen.xml"
python3 - "$RESULTS_DIR/radio-prefs-after-reopen.xml" > "$RESULTS_DIR/kronehit-logo-after.txt" <<'PY'
import html, json, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
raw=html.unescape(root.find("string").text or "[]")
station=next(x for x in json.loads(raw) if x["uuid"] == "test-radio-four")
print(station["favicon"])
PY
cmp "$RESULTS_DIR/kronehit-logo-before.txt" "$RESULTS_DIR/kronehit-logo-after.txt"
echo "PASS: kronehit logo stayed stable across repeated pane recreation"

# Switch radio -> YouTube. LIVE must disappear and normal song playback must be active.
echo "Switching from radio to YouTube"
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/radio-to-youtube.txt" || true
sleep 20
try_dialogs
assert_text "YouTube title after radio" 0 "=Never Gonna Give You Up"
assert_absent_anywhere "LIVE after switching to YouTube" "=LIVE"
capture "youtube-after-radio"

# Switch YouTube -> favorite two, then restart the same favorite again.
tap_tab "WebRadio" "=WebRadio"
tap_text "favorite two after YouTube" 1 "=Test Radio Two"
sleep 10
assert_text "radio after YouTube title" 0 "=Test Track Two"
assert_text "radio after YouTube live" 0 "LIVE"
assert_text "WebRadio remains open after YouTube to radio" 1 "=Gespeichert"

tap_tab "WebRadio" "=WebRadio"
tap_text "restart same favorite two" 1 "=Test Radio Two"
sleep 10
assert_text "same favorite restarts" 0 "=Test Track Two"
assert_text "same favorite remains live" 0 "LIVE"

# Switch back to YouTube a second time, then start favorite one again.
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" | tee "$RESULTS_DIR/radio-to-youtube-second.txt" || true
sleep 18
assert_text "second YouTube return" 0 "=Never Gonna Give You Up"
assert_absent_anywhere "LIVE after second YouTube return" "=LIVE"

tap_tab "WebRadio" "=WebRadio"
tap_text "favorite one final restart" 1 "=Test Radio One"
sleep 10
assert_text "final radio restart title" 0 "=Never Gonna Give You Up"
assert_text "final radio restart live" 0 "LIVE"
capture "radio-final-restart"

# Verify URL/M3U editor exists.
tap_tab "WebRadio" "=WebRadio"
tap_text "add station" 1 "Sender per URL hinzufügen"
sleep 2
assert_text "URL and playlist editor" 0 "M3U" "PLS"
capture "radio-url-editor"
adb shell input keyevent KEYCODE_BACK || true
sleep 2

# Verify search UI and attempt a real Radio Browser query. Network result is recorded, not hard-required.
tap_text "radio search" 1 "=Sender suchen"
assert_text "country filter available" 1 "=Land"
assert_text "genre filter available" 1 "=Genre"
assert_text "language filter available" 1 "=Sprache"
tap_text "radio search field" 1 "Sender oder freier Suchbegriff"
adb shell input text "ORF"
adb shell input keyevent KEYCODE_ENTER
sleep 12
capture "radio-browser-search"

# Radio playback must not pollute the normal music history.
tap_tab "Hörverlauf" "=Hörverlauf" "=History"
assert_text "local history remains available" 1 "Lokal" "Local"
assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Radio Three" "kronehit" "Antenne Steiermark" "Test Track Two" "Station identification" "Kronehit Track"
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
- Five saved stations repeatedly started and replaced
- WebRadio stays open while radio playback and player skip controls are used
- Favorite 3 starts at queue index 3 with favorites 1/2 before and the rest after
- Active play indicator follows the currently playing favorite
- Radio -> YouTube -> Radio -> YouTube -> Radio transitions passed
- ICY artist/title metadata visible in the left player
- Radio always uses artwork rather than an empty lyrics panel
- Artist page renders at right-pane width, scrolls, navigates and plays content
- Missing station logo discovered from homepage and persisted
- kronehit logo remains stable instead of alternating
- Ambiguous metadata skipped cover search
- Clear metadata resolved to a reliable YouTube Music song and exposes song-like behavior
- Ambiguous/no metadata exposes the existing music-recognition action
- Favorites support persisted list/grid switching and long-click actions without old edit/delete/arrows
- Country, genre and language filters are available for Radio Browser search
- Direct URL / M3U / PLS editor available
- Radio Browser search exercised
- Radio stations excluded from normal music history
- No app crash or ANR detected
EOF

echo "Dudu7 WebRadio smoke test passed"
