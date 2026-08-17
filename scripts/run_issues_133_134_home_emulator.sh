#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS="artifacts"
PACKAGE="com.metrolist.music.dudu7.debug"
ACTIVITY="com.metrolist.music.MainActivity"
APK="$ARTIFACTS/Metrolist-dudu7-13.7.68-x86_64-test.apk"

mkdir -p "$ARTIFACTS"
adb install -r "$APK"
adb shell pm grant "$PACKAGE" android.permission.POST_NOTIFICATIONS || true
adb shell settings put global hide_error_dialogs 1 || true
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell wm size 1080x1920
adb shell wm density 420
adb shell am force-stop "$PACKAGE"
adb shell am start -W -n "$PACKAGE/$ACTIVITY"
sleep 15

# A clean emulator can show one app-owned first-run/changelog overlay. Home itself is
# enough to prove that the Dudu7 tab strip is visible; with seven tabs, other entries
# may legitimately lie outside the visible horizontal region in portrait.
for attempt in 1 2 3 4; do
  adb shell uiautomator dump /sdcard/window.xml || true
  adb pull /sdcard/window.xml "$ARTIFACTS/home-ui-pre.xml" || true
  adb exec-out screencap -p > "$ARTIFACTS/home-ui-pre-$attempt.png" || true

  if grep -q "isn't responding" "$ARTIFACTS/home-ui-pre.xml" 2>/dev/null || \
     grep -q 'resource-id="android:id/aerr_close"' "$ARTIFACTS/home-ui-pre.xml" 2>/dev/null; then
    python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
p = Path('artifacts/home-ui-pre.xml')
if p.exists():
    root = ET.parse(p).getroot()
    for node in root.iter('node'):
        if node.attrib.get('resource-id') == 'android:id/aerr_close' or node.attrib.get('text') == 'Close app':
            m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
            if m:
                x1,y1,x2,y2 = map(int,m.groups())
                subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=False)
                break
PY
    sleep 2
    adb shell am start -W -n "$PACKAGE/$ACTIVITY" || true
    sleep 8
    continue
  fi

  if grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/home-ui-pre.xml" 2>/dev/null && \
     grep -q 'text="Home"' "$ARTIFACTS/home-ui-pre.xml" 2>/dev/null; then
    break
  fi

  # Only one app-owned overlay is expected. Never keep pressing Back once MetroList's
  # Home tab is visible, otherwise the test would exit the app itself.
  adb shell input keyevent 4 || true
  sleep 4
done

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
p = Path('artifacts/home-ui-pre.xml')
if not p.exists():
    raise SystemExit('UI hierarchy missing before Home tap')
root = ET.parse(p).getroot()
if not any(n.attrib.get('package') == 'com.metrolist.music.dudu7.debug' for n in root.iter('node')):
    raise SystemExit('MetroList is not foreground')
for node in root.iter('node'):
    if node.attrib.get('text') == 'Home':
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
        if m:
            x1,y1,x2,y2 = map(int,m.groups())
            subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=True)
            break
else:
    raise SystemExit('Home tab not found')
PY
sleep 15
adb shell uiautomator dump /sdcard/window.xml || true
adb pull /sdcard/window.xml "$ARTIFACTS/home-portrait-ui.xml" || true
adb exec-out screencap -p > "$ARTIFACTS/home-portrait.png"

python3 - <<'PY'
import re, xml.etree.ElementTree as ET
from pathlib import Path
root = ET.parse(Path('artifacts/home-portrait-ui.xml')).getroot()
found = {}
for node in root.iter('node'):
    text = node.attrib.get('text','')
    if text in {'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
        if m:
            found[text] = tuple(map(int,m.groups()))
print('portrait Dudu7 tab bounds:', found)
if 'Home' not in found:
    raise SystemExit('Home tab missing in portrait')
if not (780 <= found['Home'][1] <= 1250):
    raise SystemExit(f'Home tab not in portrait lower pane: {found["Home"]}')
PY

# Verify the same Home tab survives the adaptive landscape arrangement.
adb shell wm size 1920x1080
sleep 8
adb shell am start -W -n "$PACKAGE/$ACTIVITY" || true
sleep 4
adb shell uiautomator dump /sdcard/window-landscape.xml || true
adb pull /sdcard/window-landscape.xml "$ARTIFACTS/home-landscape-ui.xml" || true
adb exec-out screencap -p > "$ARTIFACTS/home-landscape.png"
adb shell dumpsys activity top > "$ARTIFACTS/home-activity-top.txt"
adb logcat -d -t 1000 > "$ARTIFACTS/home-emulator-logcat.txt" || true

grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/home-landscape-ui.xml"
grep -q 'text="Home"' "$ARTIFACTS/home-landscape-ui.xml"
