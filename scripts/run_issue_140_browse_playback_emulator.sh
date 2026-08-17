#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS="artifacts"
PACKAGE="com.metrolist.music.dudu7.debug"
ACTIVITY="com.metrolist.music.MainActivity"
APK="$ARTIFACTS/Metrolist-dudu7-13.7.69-x86_64-test.apk"

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

# Dismiss at most the app-owned first-run/changelog layer until the original Home
# suggestions are visible. Do not blindly leave the app once Home is present.
for attempt in 1 2 3; do
  adb shell uiautomator dump /sdcard/window.xml || true
  adb pull /sdcard/window.xml "$ARTIFACTS/browse-home-pre.xml" || true
  adb exec-out screencap -p > "$ARTIFACTS/browse-home-pre-$attempt.png" || true
  if grep -q 'text="Energize"' "$ARTIFACTS/browse-home-pre.xml" 2>/dev/null; then
    break
  fi
  adb shell input keyevent 4 || true
  sleep 4
done

grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/browse-home-pre.xml"
grep -q 'text="Energize"' "$ARTIFACTS/browse-home-pre.xml"

# Open a deterministic Home mood/browse destination using its visible text bounds.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root = ET.parse('artifacts/browse-home-pre.xml').getroot()
for node in root.iter('node'):
    if node.attrib.get('text') == 'Energize':
        m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
        if not m:
            continue
        x1,y1,x2,y2 = map(int,m.groups())
        subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=True)
        break
else:
    raise SystemExit('Energize Home destination not found')
PY
sleep 15
adb shell uiautomator dump /sdcard/browse.xml || true
adb pull /sdcard/browse.xml "$ARTIFACTS/browse-page.xml" || true
adb exec-out screencap -p > "$ARTIFACTS/browse-page.png"

# Choose the first large clickable content card in the browse body. The BrowseScreen
# grid attaches combinedClickable to each YouTubeGridItem; top bars/chips are much
# smaller and are filtered out by geometry.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root = ET.parse('artifacts/browse-page.xml').getroot()
candidates=[]
for node in root.iter('node'):
    if node.attrib.get('clickable') != 'true':
        continue
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2 = map(int,m.groups())
    w,h=x2-x1,y2-y1
    if y1 >= 250 and w >= 220 and h >= 220:
        candidates.append((y1,x1,x2,y2,node.attrib.get('class','')))
if not candidates:
    raise SystemExit('No large clickable BrowseScreen card found')
candidates.sort()
y1,x1,x2,y2,klass=candidates[0]
print('clicking browse card:', (x1,y1,x2,y2), klass)
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)], check=True)
PY
sleep 18
adb shell uiautomator dump /sdcard/after-play.xml || true
adb pull /sdcard/after-play.xml "$ARTIFACTS/browse-after-play.xml" || true
adb exec-out screencap -p > "$ARTIFACTS/browse-after-play.png"
adb shell dumpsys media_session > "$ARTIFACTS/browse-after-play-media-session.txt" || true
adb logcat -d -t 1500 > "$ARTIFACTS/browse-after-play-logcat.txt" || true

# The app must remain foreground and its media session must exist after the explicit
# browse-card tap. The screenshot and dumpsys are kept for manual semantic inspection.
grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/browse-after-play.xml"
grep -q 'com.metrolist.music.dudu7.debug' "$ARTIFACTS/browse-after-play-media-session.txt"
