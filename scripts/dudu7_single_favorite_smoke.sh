#!/usr/bin/env bash
set -Eeuo pipefail
PACKAGE_NAME="${PACKAGE_NAME:-com.metrolist.music.dudu7}"
ACTIVITY_NAME="${ACTIVITY_NAME:-com.metrolist.music.MainActivity}"
APK_PATH="${APK_PATH:?APK_PATH required}"
RESULTS_DIR="${RESULTS_DIR:-ui-test-results-single-favorite}"
DUDU_WIDTH="${DUDU_WIDTH:-1280}"
DUDU_HEIGHT="${DUDU_HEIGHT:-720}"
DUDU_DENSITY="${DUDU_DENSITY:-200}"
mkdir -p "$RESULTS_DIR"
exec > >(tee "$RESULTS_DIR/smoke.log") 2>&1

capture() { adb exec-out screencap -p > "$RESULTS_DIR/$1.png" || true; }
dump_ui() {
  for attempt in 1 2 3; do
    timeout 15s adb shell uiautomator dump /sdcard/window.xml >/dev/null 2>&1 || true
    adb pull /sdcard/window.xml "$RESULTS_DIR/window.xml" >/dev/null 2>&1 || true
    test -s "$RESULTS_DIR/window.xml" && return 0
    sleep 2
  done
  return 1
}
coords() {
  local right="$1"; shift
  dump_ui
  python3 - "$RESULTS_DIR/window.xml" "$DUDU_WIDTH" "$right" "$@" <<'PY'
import re,sys,xml.etree.ElementTree as ET
path,width,right,*needles=sys.argv[1:]; width=int(width)
root=ET.parse(path).getroot(); parent={c:n for n in root.iter() for c in n}
exact=[x[1:].casefold() for x in needles if x.startswith('=')]
partial=[x.casefold() for x in needles if not x.startswith('=')]
for node in root.iter('node'):
    vals=[node.attrib.get('text','').strip().casefold(),node.attrib.get('content-desc','').strip().casefold()]
    hay=' '.join(v for v in vals if v)
    if not (any(v==n for v in vals for n in exact) or any(n in hay for n in partial)): continue
    cur=node; fallback=None
    while cur is not None:
        m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
        if m:
            l,t,r,b=map(int,m.groups())
            if (right!='1' or l>=width//2) and r>l and b>t:
                fallback=(l,t,r,b)
                if cur.attrib.get('clickable')=='true': print((l+r)//2,(t+b)//2); raise SystemExit(0)
        cur=parent.get(cur)
    if fallback:
        l,t,r,b=fallback; print((l+r)//2,(t+b)//2); raise SystemExit(0)
raise SystemExit(1)
PY
}
tap() { local label="$1" right="$2"; shift 2; local p; p=$(coords "$right" "$@"); echo "Tap $label: $p"; adb shell input tap $p; sleep 3; }
assert_ui() { local label="$1" right="$2"; shift 2; for i in 1 2 3 4 5; do coords "$right" "$@" >/dev/null && { echo "PASS: $label"; return; }; sleep 2; done; capture "fail-${label// /-}"; return 1; }

python3 - > /tmp/metrolist_webradio.xml <<'PY'
import html,json
stations=[
  {"uuid":"broken-before","name":"Broken Before","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"","language":"","tags":"","codec":"","bitrate":0},
  {"uuid":"one","name":"Favorite One","streamUrl":"http://10.0.2.2:8000/station1","homepage":"","favicon":"","manualFavicon":False,"country":"","language":"","tags":"","codec":"","bitrate":0},
  {"uuid":"two","name":"Favorite Two","streamUrl":"http://10.0.2.2:8000/station2","homepage":"","favicon":"","manualFavicon":False,"country":"","language":"","tags":"","codec":"","bitrate":0},
  {"uuid":"broken-after","name":"Broken After","streamUrl":"http://10.0.2.2:8000/always-broken","homepage":"","favicon":"","manualFavicon":False,"country":"","language":"","tags":"","codec":"","bitrate":0}
]
raw=json.dumps(stations,separators=(',',':'))
print('<?xml version="1.0" encoding="utf-8" standalone="yes" ?>')
print('<map><string name="stations">'+html.escape(raw)+'</string></map>')
PY

adb wait-for-device
adb shell settings put system accelerometer_rotation 0 || true
adb shell settings put system user_rotation 1 || true
adb shell settings put global window_animation_scale 0 || true
adb shell settings put global transition_animation_scale 0 || true
adb shell settings put global animator_duration_scale 0 || true
adb shell wm size "${DUDU_WIDTH}x${DUDU_HEIGHT}" || true
adb shell wm density "$DUDU_DENSITY" || true
adb install -r -g "$APK_PATH"
adb push /tmp/metrolist_webradio.xml /data/local/tmp/metrolist_webradio.xml >/dev/null
adb shell run-as "$PACKAGE_NAME" mkdir -p shared_prefs
adb shell run-as "$PACKAGE_NAME" cp /data/local/tmp/metrolist_webradio.xml shared_prefs/metrolist_webradio.xml
adb logcat -c
adb shell am force-stop "$PACKAGE_NAME"
adb shell am start -W -n "$PACKAGE_NAME/$ACTIVITY_NAME"
sleep 12
capture launch

tap "WebRadio" 0 "=WebRadio"
assert_ui "favorites visible" 1 "=Favorite One"
tap "Favorite One" 1 "=Favorite One"
assert_ui "single favorite starts" 0 "=Never Gonna Give You Up"
tap "Next favorite" 0 "=Nächster Titel"
assert_ui "next favorite plays" 0 "=Test Track Two"
tap "Previous favorite" 0 "=Vorheriger Titel"
assert_ui "previous favorite plays" 0 "=Never Gonna Give You Up"

adb logcat -d -v threadtime > "$RESULTS_DIR/logcat.txt" || true
! grep -E "FATAL EXCEPTION|ANR in ${PACKAGE_NAME}" "$RESULTS_DIR/logcat.txt"
! grep -q 'GET /always-broken' "$RESULTS_DIR/radio-server.log"
capture final
echo 'PASS: single favorite start, next and previous'
