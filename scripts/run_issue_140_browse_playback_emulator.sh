#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS="artifacts"
PACKAGE="com.metrolist.music.dudu7.debug"
ACTIVITY="com.metrolist.music.MainActivity"
APK="$ARTIFACTS/Metrolist-dudu7-13.7.70-x86_64-test.apk"

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

dump_ui() {
  local remote="$1"
  local local_file="$2"
  adb shell uiautomator dump "$remote" || true
  adb pull "$remote" "$local_file" || true
}

# Reveal the visible Dudu7 Home tab by scrolling the actual tab strip.
for attempt in 1 2 3 4 5 6; do
  dump_ui /sdcard/tab.xml "$ARTIFACTS/tab-$attempt.xml"
  adb exec-out screencap -p > "$ARTIFACTS/tab-$attempt.png" || true
  if python3 - "$ARTIFACTS/tab-$attempt.xml" <<'PY'
import re, sys, xml.etree.ElementTree as ET
root = ET.parse(sys.argv[1]).getroot()
for n in root.iter('node'):
    if n.attrib.get('text') != 'Home': continue
    m = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', n.attrib.get('bounds',''))
    if m:
        x1,y1,x2,y2 = map(int,m.groups())
        if 0 <= x1 < x2 <= 1080 and 930 <= y1 <= 1150:
            raise SystemExit(0)
raise SystemExit(1)
PY
  then
    cp "$ARTIFACTS/tab-$attempt.xml" "$ARTIFACTS/home-tab-visible.xml"
    break
  fi
  adb shell input swipe 950 1040 170 1040 450
  sleep 2
done

test -f "$ARTIFACTS/home-tab-visible.xml"

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
p='artifacts/home-tab-visible.xml'; root=ET.parse(p).getroot(); parent={c:p for p in root.iter() for c in p}
for n in root.iter('node'):
    if n.attrib.get('text') != 'Home': continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups())
    if not (0 <= x1 < x2 <= 1080 and 930 <= y1 <= 1150): continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true': cur=parent.get(cur)
    if cur is None: raise SystemExit('Visible Home tab has no clickable ancestor')
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    xa,ya,xb,yb=map(int,m.groups())
    subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
    break
else: raise SystemExit('Visible Home tab not found for tap')
PY
sleep 15

dump_ui /sdcard/home-selected.xml "$ARTIFACTS/home-selected.xml"
adb exec-out screencap -p > "$ARTIFACTS/home-selected.png"

# Scroll only the lower pane until the visible Stimmungen & Genres header appears.
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  dump_ui /sdcard/home-scroll.xml "$ARTIFACTS/home-scroll-$attempt.xml"
  adb exec-out screencap -p > "$ARTIFACTS/home-scroll-$attempt.png" || true
  if python3 - "$ARTIFACTS/home-scroll-$attempt.xml" <<'PY'
import re, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
for n in root.iter('node'):
    if 'Genres' not in n.attrib.get('text',''): continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if m:
        x1,y1,x2,y2=map(int,m.groups())
        if 1130 <= y1 < y2 <= 1900 and x2>x1: raise SystemExit(0)
raise SystemExit(1)
PY
  then
    cp "$ARTIFACTS/home-scroll-$attempt.xml" "$ARTIFACTS/mood-title-visible.xml"
    break
  fi
  adb shell input swipe 800 1740 800 1220 550
  sleep 3
done

test -f "$ARTIFACTS/mood-title-visible.xml"

python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-title-visible.xml'; root=ET.parse(p).getroot(); parent={c:p for p in root.iter() for c in p}
for n in root.iter('node'):
    if 'Genres' not in n.attrib.get('text',''): continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups())
    if not (1130 <= y1 < y2 <= 1900): continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true': cur=parent.get(cur)
    if cur is None: continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    xa,ya,xb,yb=map(int,m.groups())
    subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
    break
else: raise SystemExit('Visible Mood & Genres title is not clickable')
PY
sleep 10

dump_ui /sdcard/moods.xml "$ARTIFACTS/mood-genres.xml"
adb exec-out screencap -p > "$ARTIFACTS/mood-genres.png"

# Select the first visible mood/genre button in the lower Dudu7 pane.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-genres.xml'; root=ET.parse(p).getroot(); parent={c:p for p in root.iter() for c in p}
seen=set(); candidates=[]
for n in root.iter('node'):
    text=n.attrib.get('text','').strip()
    if not text or text in {'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}: continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m: continue
    x1,y1,x2,y2=map(int,m.groups())
    if not (1160 <= y1 < y2 <= 1900): continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true': cur=parent.get(cur)
    if cur is None: continue
    m2=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    if not m2: continue
    xa,ya,xb,yb=map(int,m2.groups()); w,h=xb-xa,yb-ya
    if w < 140 or h < 45 or ya < 1130: continue
    key=(xa,ya,xb,yb)
    if key in seen: continue
    seen.add(key); candidates.append((ya,xa,xb,yb,text))
if not candidates: raise SystemExit('No visible mood/genre button found in lower pane')
candidates.sort(); ya,xa,xb,yb,text=candidates[0]
print('selected visible genre:',text,(xa,ya,xb,yb)); open('artifacts/selected-genre.txt','w').write(text+'\n')
subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
PY
sleep 12

dump_ui /sdcard/browse.xml "$ARTIFACTS/browse-page.xml"
adb exec-out screencap -p > "$ARTIFACTS/browse-page.png"

# Choose a visible large BrowseScreen card and remember its first descendant title.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root=ET.parse('artifacts/browse-page.xml').getroot()
def b(n):
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    return tuple(map(int,m.groups())) if m else None
c=[]
for n in root.iter('node'):
    if n.attrib.get('clickable')!='true': continue
    bb=b(n)
    if not bb: continue
    x1,y1,x2,y2=bb; w,h=x2-x1,y2-y1
    if y1<1160 or y2>1900 or w<220 or h<220: continue
    texts=[]
    for d in n.iter('node'):
        t=d.attrib.get('text','').strip(); db=b(d)
        if t and db and db[1]>=y1 and db[3]<=y2: texts.append(t)
    if texts: c.append((y1,x1,x2,y2,texts))
if not c: raise SystemExit('No visible large BrowseScreen card with title found')
c.sort(); y1,x1,x2,y2,texts=c[0]; title=texts[0]
print('clicking visible browse card:',title,(x1,y1,x2,y2),texts)
open('artifacts/selected-browse-title.txt','w').write(title+'\n')
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)],check=True)
PY
sleep 18

dump_ui /sdcard/after-play.xml "$ARTIFACTS/browse-after-play.xml"
adb exec-out screencap -p > "$ARTIFACTS/browse-after-play.png"
adb shell dumpsys media_session > "$ARTIFACTS/browse-after-play-media-session.txt" || true
adb logcat -d -t 1500 > "$ARTIFACTS/browse-after-play-logcat.txt" || true

# Strong proof: clicked Browse title appears in upper player and the empty-player
# placeholder is gone.
python3 - <<'PY'
import re, xml.etree.ElementTree as ET
from pathlib import Path
title=Path('artifacts/selected-browse-title.txt').read_text().strip(); root=ET.parse('artifacts/browse-after-play.xml').getroot(); found=[]
for n in root.iter('node'):
    if n.attrib.get('text','').strip()!=title: continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if m:
        bb=tuple(map(int,m.groups()))
        if bb[1]<960: found.append(bb)
print('selected title in upper player:',title,found)
if not found: raise SystemExit(f'Clicked Browse title did not appear in upper player: {title!r}')
if any(n.attrib.get('text')=='Noch keine Wiedergabe' for n in root.iter('node')):
    raise SystemExit('Player still reports no playback after Browse song tap')
PY

grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/browse-after-play.xml"
