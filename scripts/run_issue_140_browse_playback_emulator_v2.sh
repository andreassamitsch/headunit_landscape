#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS="artifacts"
PACKAGE="com.metrolist.music.dudu7.debug"
ACTIVITY="com.metrolist.music.MainActivity"
APK="$ARTIFACTS/Metrolist-dudu7-issue140-x86_64-test.apk"

mkdir -p "$ARTIFACTS"
adb install -r "$APK"
adb shell pm grant "$PACKAGE" android.permission.POST_NOTIFICATIONS || true
adb shell settings put global hide_error_dialogs 1 || true
adb shell settings put global anr_show_background 0 || true
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell wm size 1080x1920
adb shell wm density 420
adb shell am force-stop "$PACKAGE"
# The Pixel launcher occasionally ANRs under a cold CI emulator and covered the
# complete app in the previous test. Keep that unrelated process out of this gate.
adb shell am force-stop com.google.android.apps.nexuslauncher || true

# Start the Dudu7 pane on Home, then still select the visible Home tab explicitly
# below. The explicit UI action is the proof; this preference is only a fast path.
adb shell "run-as $PACKAGE mkdir -p shared_prefs"
printf '%s\n' \
  '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>' \
  '<map>' \
  '  <string name="last_main_tab_route">home</string>' \
  '</map>' \
  | adb shell "run-as $PACKAGE sh -c 'cat > shared_prefs/dudu7_vehicle_pane.xml'"

adb shell am start -W -n "$PACKAGE/$ACTIVITY"
sleep 12

dump_ui() {
  local remote="$1"
  local local_file="$2"
  local ok=0
  for _ in 1 2 3; do
    if adb shell uiautomator dump "$remote" >/dev/null 2>&1 && adb pull "$remote" "$local_file" >/dev/null 2>&1; then
      ok=1
      break
    fi
    sleep 2
  done
  test "$ok" = 1
}

# Dismiss an unrelated Android/launcher ANR dialog if one survived force-stop,
# then bring MetroList back to the foreground. A system dialog must never be
# mistaken for a tested application state again.
for attempt in 1 2 3 4 5; do
  dump_ui /sdcard/system-dialog.xml "$ARTIFACTS/system-dialog-$attempt.xml"
  if python3 - "$ARTIFACTS/system-dialog-$attempt.xml" <<'PY'
import re, subprocess, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
alert=any("isn't responding" in n.attrib.get('text','') for n in root.iter('node'))
if not alert:
    raise SystemExit(1)
for label in ('Close app','Wait'):
    for n in root.iter('node'):
        if n.attrib.get('text') != label:
            continue
        m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
        if m:
            x1,y1,x2,y2=map(int,m.groups())
            subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)],check=True)
            raise SystemExit(0)
raise SystemExit('ANR dialog found but no dismiss button')
PY
  then
    sleep 3
  else
    break
  fi
done
adb shell am start -W -n "$PACKAGE/$ACTIVITY"
sleep 6

# Explicitly select the Home tab. If the LazyRow starts scrolled away from the
# first tab, reveal the left edge and retry. This replaces the invalid previous
# assumption that a SharedPreferences write proved Home was visible.
rm -f "$ARTIFACTS/home-selected.xml"
for attempt in 1 2 3 4 5 6; do
  dump_ui /sdcard/home-tabs.xml "$ARTIFACTS/home-tabs-$attempt.xml"
  if python3 - "$ARTIFACTS/home-tabs-$attempt.xml" <<'PY'
import re, subprocess, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot(); parent={c:p for p in root.iter() for c in p}
for n in root.iter('node'):
    if n.attrib.get('text') != 'Home' and n.attrib.get('content-desc') != 'Home':
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if y2 < 850:
        continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true':
        cur=parent.get(cur)
    target=cur or n
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',target.attrib.get('bounds',''))
    if not m:
        continue
    xa,ya,xb,yb=map(int,m.groups())
    subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    sleep 8
    dump_ui /sdcard/home-selected.xml "$ARTIFACTS/home-selected.xml"
    adb exec-out screencap -p > "$ARTIFACTS/home-selected.png"
    break
  fi
  # Swipe the tab row toward its beginning (Home is the first tab).
  adb shell input swipe 180 1040 930 1040 450
  sleep 2
done
test -f "$ARTIFACTS/home-selected.xml"

# Scroll only the lower Dudu7 pane until the real Home section
# "Stimmungen & Genres" is visible.
rm -f "$ARTIFACTS/mood-title-visible.xml"
for attempt in 1 2 3 4 5 6 7 8 9 10 11 12; do
  dump_ui /sdcard/home-scroll.xml "$ARTIFACTS/home-scroll-$attempt.xml"
  adb exec-out screencap -p > "$ARTIFACTS/home-scroll-$attempt.png" || true
  if python3 - "$ARTIFACTS/home-scroll-$attempt.xml" <<'PY'
import re, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
for n in root.iter('node'):
    if 'Genres' not in n.attrib.get('text',''):
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if m:
        x1,y1,x2,y2=map(int,m.groups())
        if 1100 <= y1 < y2 <= 1910 and x2>x1:
            raise SystemExit(0)
raise SystemExit(1)
PY
  then
    cp "$ARTIFACTS/home-scroll-$attempt.xml" "$ARTIFACTS/mood-title-visible.xml"
    break
  fi
  adb shell input swipe 800 1770 800 1220 600
  sleep 3
done
test -f "$ARTIFACTS/mood-title-visible.xml"

# Open the original MetroList MoodAndGenresScreen via a real touch.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-title-visible.xml'
root=ET.parse(p).getroot(); parent={c:p for p in root.iter() for c in p}
for n in root.iter('node'):
    if 'Genres' not in n.attrib.get('text',''):
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if not (1100 <= y1 < y2 <= 1910):
        continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true':
        cur=parent.get(cur)
    if cur is None:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    xa,ya,xb,yb=map(int,m.groups())
    subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
    raise SystemExit(0)
raise SystemExit('Visible Mood & Genres section is not clickable')
PY
sleep 10

dump_ui /sdcard/moods.xml "$ARTIFACTS/mood-genres.xml"
adb exec-out screencap -p > "$ARTIFACTS/mood-genres.png"

# Choose one visible real genre/mood button. From this point on clear logcat so
# every Browse target and navigation line belongs to this exact test path.
adb logcat -c
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-genres.xml'
root=ET.parse(p).getroot(); parent={c:p for p in root.iter() for c in p}
ignored={'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}
seen=set(); candidates=[]
for n in root.iter('node'):
    text=n.attrib.get('text','').strip()
    if not text or text in ignored:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if not (1120 <= y1 < y2 <= 1910):
        continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true':
        cur=parent.get(cur)
    if cur is None:
        continue
    m2=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    if not m2:
        continue
    xa,ya,xb,yb=map(int,m2.groups()); w,h=xb-xa,yb-ya
    if w < 140 or h < 45 or ya < 1100:
        continue
    key=(xa,ya,xb,yb)
    if key in seen:
        continue
    seen.add(key); candidates.append((ya,xa,xb,yb,text))
if not candidates:
    raise SystemExit('No visible mood/genre button found in lower pane')
candidates.sort(); ya,xa,xb,yb,text=candidates[0]
print('selected visible genre:',text,(xa,ya,xb,yb))
open('artifacts/selected-genre.txt','w').write(text+'\n')
subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
PY
sleep 15

dump_ui /sdcard/browse.xml "$ARTIFACTS/browse-page.xml"
adb exec-out screencap -p > "$ARTIFACTS/browse-page.png"

# Select a specifically identified PlaylistItem from the actual rendered card
# bounds logged by BrowseScreen. If the first viewport has no playlist, scroll the
# same Dudu7 pane and retry. The eventual action is a real `adb input tap`.
rm -f "$ARTIFACTS/selected-playlist.json"
for attempt in 1 2 3 4 5 6; do
  adb logcat -d -v brief > "$ARTIFACTS/browse-targets-$attempt.log"
  if python3 - "$ARTIFACTS/browse-targets-$attempt.log" <<'PY'
import json, re, subprocess, sys
text=open(sys.argv[1],encoding='utf-8',errors='replace').read().splitlines()
rx=re.compile(r'type=PlaylistItem id=(\S+) bounds=\[([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+)\] title=(.*?) browseId=(.*)$')
by_id={}
for line in text:
    if 'Dudu7BrowseTarget' not in line:
        continue
    m=rx.search(line)
    if not m:
        continue
    item_id=m.group(1); l,t,r,b=map(float,m.group(2,3,4,5)); title=m.group(6)
    cx=(l+r)/2; cy=(t+b)/2
    if 0 <= cx <= 1080 and 1120 <= cy <= 1900 and r>l and b>t:
        by_id[item_id]={'id':item_id,'title':title,'bounds':[l,t,r,b],'center':[round(cx),round(cy)]}
if not by_id:
    raise SystemExit(1)
selected=sorted(by_id.values(),key=lambda v:(v['bounds'][1],v['bounds'][0]))[0]
print('selected rendered playlist target:',selected)
with open('artifacts/selected-playlist.json','w',encoding='utf-8') as f:
    json.dump(selected,f,ensure_ascii=False,indent=2)
subprocess.run(['adb','shell','input','tap',str(selected['center'][0]),str(selected['center'][1])],check=True)
PY
  then
    break
  fi
  adb shell input swipe 800 1770 800 1240 550
  sleep 4
done
test -f "$ARTIFACTS/selected-playlist.json"
sleep 8

dump_ui /sdcard/after-playlist-tap.xml "$ARTIFACTS/playlist-after-tap.xml"
adb exec-out screencap -p > "$ARTIFACTS/playlist-after-tap.png"
adb logcat -d -v brief > "$ARTIFACTS/playlist-after-tap-logcat.txt"

# Mandatory proof chain:
#  1) a real rendered PlaylistItem bound was chosen,
#  2) the parent Dudu7 bridge received the adb touch,
#  3) BrowseScreen executed PlaylistItem navigation,
#  4) NavController's current destination is the OnlinePlaylistScreen route.
python3 - <<'PY'
import json, re
from pathlib import Path
selected=json.loads(Path('artifacts/selected-playlist.json').read_text(encoding='utf-8'))
log=Path('artifacts/playlist-after-tap-logcat.txt').read_text(encoding='utf-8',errors='replace')
item_id=selected['id']
if 'Dudu7BrowseTap' not in log or 'Bridged BrowseScreen tap' not in log:
    raise SystemExit('adb touch never reached the Dudu7 Browse bridge')
pattern=re.compile(r'completed type=playlist id='+re.escape(item_id)+r' currentRoute=online_playlist/\{playlistId\}')
if not pattern.search(log):
    relevant='\n'.join(line for line in log.splitlines() if 'Dudu7Browse' in line or 'Dudu7RightPaneTap' in line)
    print(relevant)
    raise SystemExit(f'Playlist touch did not navigate to OnlinePlaylistScreen for {item_id}')
xml=Path('artifacts/playlist-after-tap.xml').read_text(encoding='utf-8',errors='replace')
if "isn't responding" in xml:
    raise SystemExit('System ANR dialog covered the post-tap UI')
print('PASS: real adb playlist touch reached OnlinePlaylistScreen:',selected)
PY

grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/playlist-after-tap.xml"
