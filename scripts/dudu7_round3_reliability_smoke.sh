#!/usr/bin/env bash
set -Eeuo pipefail

PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7}"
ACTIVITY_NAME="${ACTIVITY_NAME:-com.metrolist.music.MainActivity}"
APK_PATH="${APK_PATH:?APK_PATH must point to emulator APK}"
RESULTS_DIR="${RESULTS_DIR:-ui-test-results-round3}"
DUDU_WIDTH="${DUDU_WIDTH:-1280}"
DUDU_HEIGHT="${DUDU_HEIGHT:-720}"
DUDU_DENSITY="${DUDU_DENSITY:-200}"
mkdir -p "$RESULTS_DIR"
exec > >(tee "$RESULTS_DIR/round3-smoke.log") 2>&1

capture() {
  local name="$1"
  adb exec-out screencap -p > "$RESULTS_DIR/${name}.png" || true
  timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
  adb pull /sdcard/window.xml "$RESULTS_DIR/${name}.xml" >/dev/null 2>&1 || true
}

dump_ui() {
  for attempt in 1 2 3; do
    rm -f "$RESULTS_DIR/current-window.xml"
    if timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 \
      && adb pull /sdcard/window.xml "$RESULTS_DIR/current-window.xml" >/dev/null 2>&1 \
      && test -s "$RESULTS_DIR/current-window.xml"; then
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
    vals = [node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()]
    hay = ' '.join(v for v in vals if v)
    matched = any(v == n for v in vals for n in exact) or (hay and any(n in hay for n in partial))
    if not matched:
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
  coords=$(find_coords "$right" "$@") || { echo "Could not find $label" >&2; capture "missing-${label// /-}"; return 1; }
  echo "Tapping $label at $coords"
  adb shell input tap $coords
  sleep 3
}

assert_text() {
  local label="$1"; local right="$2"; shift 2
  for attempt in 1 2 3 4 5; do
    if find_coords "$right" "$@" >/dev/null; then
      echo "PASS: $label"
      return 0
    fi
    sleep 2
  done
  echo "FAIL: $label" >&2
  capture "failure-${label// /-}"
  return 1
}

assert_station_active() {
  local station="$1"
  dump_ui || return 1
  python3 - "$RESULTS_DIR/current-window.xml" "$station" "$DUDU_WIDTH" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, station, width = sys.argv[1:]
width = int(width)
root = ET.parse(path).getroot()
def bounds(node):
    m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    return tuple(map(int,m.groups())) if m else None
stations=[n for n in root.iter('node') if n.attrib.get('text','').strip()==station and bounds(n) and bounds(n)[0]>=width//2]
indicators=[n for n in root.iter('node') if 'LÄUFT' in n.attrib.get('text','') and bounds(n) and bounds(n)[0]>=width//2]
for s in stations:
    sy=(bounds(s)[1]+bounds(s)[3])/2
    for i in indicators:
        iy=(bounds(i)[1]+bounds(i)[3])/2
        if abs(sy-iy)<=34:
            raise SystemExit(0)
raise SystemExit(1)
PY
  echo "PASS: active row $station"
}

try_dialogs() {
  for i in 1 2 3 4 5; do
    local coords
    coords=$(find_coords 0 "allow" "zulassen" "continue" "weiter" "skip" "überspringen" "not now" "später" 2>/dev/null) || break
    adb shell input tap $coords
    sleep 2
  done
}

seed_radios() {
  python3 - > /tmp/metrolist_webradio.xml <<'PY'
import html, json
stations = [
 {"uuid":"stale-one","name":"Stale Radio One","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Rock","codec":"MP3","bitrate":96},
 {"uuid":"stale-two","name":"Stale Radio Two","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Pop","codec":"MP3","bitrate":96},
 {"uuid":"slow-one","name":"Slow Old Radio","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"Austria","language":"German","tags":"Rock","codec":"MP3","bitrate":96}
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
adb install -r -g "$APK_PATH"
adb shell pm grant "$PACKAGE_NAME" android.permission.POST_NOTIFICATIONS || true
seed_radios
adb logcat -c || true
adb shell am force-stop "$PACKAGE_NAME"
adb shell am start -W -n "$PACKAGE_NAME/$ACTIVITY_NAME"
sleep 12
try_dialogs
capture launch

tap_text "WebRadio tab" 0 "=WebRadio"
assert_text "saved favorites visible" 1 "=Gespeichert"

# Both favorites contain deliberately dead URLs. The production path must refresh
# them by stable Radio Browser UUID before handing a queue to ExoPlayer.
tap_text "stale favorite one" 1 "=Stale Radio One"
sleep 12
assert_text "refreshed favorite one plays" 0 "=Never Gonna Give You Up"
assert_text "refreshed favorite one artist" 0 "=Rick Astley"
assert_station_active "Test Radio One"
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/prefs-after-one.xml"
python3 - "$RESULTS_DIR/prefs-after-one.xml" <<'PY'
import html,json,sys,xml.etree.ElementTree as ET
raw=html.unescape(ET.parse(sys.argv[1]).getroot().find('string').text or '[]')
station=next(x for x in json.loads(raw) if x['uuid']=='stale-one')
assert station['streamUrl'].endswith('/station1'), station
print('PASS: stale favorite one URL persisted as current station1 URL')
PY

tap_text "stale favorite two" 1 "=Stale Radio Two"
sleep 10
assert_text "refreshed favorite two plays" 0 "=Test Track Two"
assert_text "refreshed favorite two artist" 0 "=Test Artist Two"
assert_station_active "Test Radio Two"
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/prefs-after-two.xml"
python3 - "$RESULTS_DIR/prefs-after-two.xml" <<'PY'
import html,json,sys,xml.etree.ElementTree as ET
raw=html.unescape(ET.parse(sys.argv[1]).getroot().find('string').text or '[]')
station=next(x for x in json.loads(raw) if x['uuid']=='stale-two')
assert station['streamUrl'].endswith('/station2'), station
print('PASS: stale favorite two URL persisted as current station2 URL')
PY

# The first UUID refresh intentionally blocks for six seconds. A newer favorite
# selection must win and must still be active after the old request returns.
tap_text "slow old favorite" 1 "=Slow Old Radio"
sleep 1
tap_text "newer favorite two" 1 "=Test Radio Two" "=Stale Radio Two"
sleep 10
assert_text "newer selection survives delayed old request" 0 "=Test Track Two"
assert_station_active "Test Radio Two"
echo "PASS: latest favorite selection wins delayed refresh race"

# Reopen the refreshed Rick Astley station and test the embedded artist detail
# page that previously became white after 'Alle anzeigen'.
tap_text "refreshed favorite one again" 1 "=Test Radio One" "=Stale Radio One"
sleep 10
assert_text "Rick metadata restored" 0 "=Rick Astley"
tap_text "Rick artist link" 0 "=Rick Astley"
sleep 12
assert_text "embedded artist page" 1 "=Rick Astley"
adb shell input swipe 1100 620 1100 210 500
sleep 3
tap_text "artist all titles" 1 "=Alle anzeigen"
sleep 14
assert_text "artist title detail is not white" 1 "=Never Gonna Give You Up" "=Together Forever"
assert_text "artist detail has back action" 1 "=Zurück"
echo "PASS: embedded artist detail page rendered content"

capture final
adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" 2>&1 || true
if grep -E "FATAL EXCEPTION|ANR in ${PACKAGE_NAME}|Process: ${PACKAGE_NAME}.*has died" "$RESULTS_DIR/logcat.txt"; then
  echo "FAIL: crash or ANR found" >&2
  exit 1
fi

echo "Dudu7 round 3 reliability smoke passed"
