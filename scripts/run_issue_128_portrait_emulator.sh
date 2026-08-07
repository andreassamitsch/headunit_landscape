#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS="artifacts"
PACKAGE="com.metrolist.music.dudu7.debug"
ACTIVITY="com.metrolist.music.MainActivity"
APK="$ARTIFACTS/Metrolist-dudu7-13.7.66-x86_64-test.apk"

mkdir -p "$ARTIFACTS"
adb install -r "$APK"
adb shell pm grant "$PACKAGE" android.permission.POST_NOTIFICATIONS || true
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell wm size 1080x1920
adb shell wm density 420
adb shell am force-stop "$PACKAGE"
adb shell am start -W -n "$PACKAGE/$ACTIVITY"
sleep 15

# First capture the actual initial app state before trying to dismiss any overlay.
adb exec-out screencap -p > "$ARTIFACTS/portrait-emulator-initial.png" || true
adb shell uiautomator dump /sdcard/window.xml || true
adb pull /sdcard/window.xml "$ARTIFACTS/portrait-ui-initial.xml" || true

# Changelog/dialogs can cover the player on a clean emulator. Try BACK and re-check,
# but never change the underlying selected player/tab state.
for attempt in 1 2 3; do
  adb shell uiautomator dump /sdcard/window.xml || true
  adb pull /sdcard/window.xml "$ARTIFACTS/portrait-ui.xml" || true
  if grep -q 'text="WebRadio"' "$ARTIFACTS/portrait-ui.xml" 2>/dev/null && \
     grep -q 'text="FM"' "$ARTIFACTS/portrait-ui.xml" 2>/dev/null; then
    break
  fi
  adb shell input keyevent 4 || true
  sleep 4
done

adb exec-out screencap -p > "$ARTIFACTS/portrait-emulator.png"
adb shell dumpsys window displays > "$ARTIFACTS/window-displays.txt"
adb shell dumpsys activity top > "$ARTIFACTS/activity-top.txt"
adb logcat -d -t 800 > "$ARTIFACTS/portrait-logcat.txt" || true

python3 - <<'PY'
import re
import xml.etree.ElementTree as ET
from pathlib import Path

xml = Path('artifacts/portrait-ui.xml')
if not xml.exists():
    raise SystemExit('portrait UI hierarchy missing')
root = ET.parse(xml).getroot()
found = {}
for node in root.iter('node'):
    text = node.attrib.get('text', '')
    if text in {'WebRadio', 'FM'}:
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds', ''))
        if m:
            found[text] = tuple(map(int, m.groups()))
print('portrait tab bounds:', found)
if 'WebRadio' not in found or 'FM' not in found:
    raise SystemExit('Dudu7 tabs not present in portrait UI')
# 1080x1920 target. The second pane begins around the halfway point after insets.
for name, (_, y1, _, y2) in found.items():
    if not (780 <= y1 <= 1250):
        raise SystemExit(f'{name} is not in lower 50% region: y={y1}..{y2}')
PY
