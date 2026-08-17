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

# VehicleLandscapeLayout reads this production SharedPreferences value before it
# constructs the right-pane NavHost. Starting on Home therefore exercises the exact
# production navigation path while making the emulator setup deterministic.
adb shell "run-as $PACKAGE mkdir -p shared_prefs"
printf '%s\n' \
  '<?xml version="1.0" encoding="utf-8" standalone="yes" ?>' \
  '<map>' \
  '  <string name="last_main_tab_route">home</string>' \
  '</map>' \
  | adb shell "run-as $PACKAGE sh -c 'cat > shared_prefs/dudu7_vehicle_pane.xml'"

adb shell am start -W -n "$PACKAGE/$ACTIVITY"
sleep 18

dump_ui() {
  local remote="$1"
  local local_file="$2"
  adb shell uiautomator dump "$remote" || true
  adb pull "$remote" "$local_file" || true
}

dump_ui /sdcard/home-selected.xml "$ARTIFACTS/home-selected.xml"
adb exec-out screencap -p > "$ARTIFACTS/home-selected.png"

# Prove that the Home *tab* is visibly selected around the real portrait 50/50 split,
# rather than accidentally interacting with precomposed/off-screen Home semantics.
python3 - <<'PY'
import re, xml.etree.ElementTree as ET
root=ET.parse('artifacts/home-selected.xml').getroot()
visible=[]
for n in root.iter('node'):
    if n.attrib.get('text') != 'Home':
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    b=tuple(map(int,m.groups()))
    if 0 <= b[0] < b[2] <= 1080 and 990 <= b[1] <= 1140:
        visible.append(b)
print('visible Home tab bounds:',visible)
if not visible:
    raise SystemExit('Home was not the visible Dudu7 startup tab')
PY

# Scroll only the lower Dudu7 pane until the real Home section "Stimmungen & Genres"
# is visibly present. The upper player is never touched by these gestures.
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
        if 1130 <= y1 < y2 <= 1880 and x2>x1:
            raise SystemExit(0)
raise SystemExit(1)
PY
  then
    cp "$ARTIFACTS/home-scroll-$attempt.xml" "$ARTIFACTS/mood-title-visible.xml"
    break
  fi
  adb shell input swipe 800 1760 800 1210 600
  sleep 3
done

test -f "$ARTIFACTS/mood-title-visible.xml"

# Tap the clickable ancestor of the visible section title to open the original
# MetroList MoodAndGenresScreen inside the Dudu7 right pane.
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
    if not (1130 <= y1 < y2 <= 1880):
        continue
    cur=n
    while cur is not None and cur.attrib.get('clickable') != 'true':
        cur=parent.get(cur)
    if cur is None:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',cur.attrib.get('bounds',''))
    xa,ya,xb,yb=map(int,m.groups())
    subprocess.run(['adb','shell','input','tap',str((xa+xb)//2),str((ya+yb)//2)],check=True)
    break
else:
    raise SystemExit('Visible Mood & Genres section is not clickable')
PY
sleep 12

dump_ui /sdcard/moods.xml "$ARTIFACTS/mood-genres.xml"
adb exec-out screencap -p > "$ARTIFACTS/mood-genres.png"

# Choose the first visible clickable genre/mood entry in the lower pane.
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
    if not (1160 <= y1 < y2 <= 1880):
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
    if w < 140 or h < 45 or ya < 1130:
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

# Pick a real visible large BrowseScreen card in the lower pane. Prefer the center
# play overlay when it is exposed as clickable; otherwise tap the card itself. Save
# the first visible title within the card so the upper player can be verified later.
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root=ET.parse('artifacts/browse-page.xml').getroot()
def bounds(n):
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    return tuple(map(int,m.groups())) if m else None
candidates=[]
for n in root.iter('node'):
    if n.attrib.get('clickable')!='true':
        continue
    b=bounds(n)
    if not b:
        continue
    x1,y1,x2,y2=b; w,h=x2-x1,y2-y1
    if y1<1160 or y2>1880 or w<220 or h<220:
        continue
    texts=[]
    for d in n.iter('node'):
        t=d.attrib.get('text','').strip(); db=bounds(d)
        if t and db and db[1]>=y1 and db[3]<=y2:
            texts.append(t)
    if texts:
        candidates.append((y1,x1,x2,y2,texts,n))
if not candidates:
    raise SystemExit('No visible large BrowseScreen card with title found')
candidates.sort(key=lambda x:(x[0],x[1]))
y1,x1,x2,y2,texts,node=candidates[0]
title=texts[0]
# If the 13.7.70 center overlay exposes a nested clickable node, use it explicitly.
target=(x1,y1,x2,y2)
for d in node.iter('node'):
    db=bounds(d)
    if d is not node and d.attrib.get('clickable')=='true' and db:
        dx1,dy1,dx2,dy2=db
        if dx1>=x1 and dx2<=x2 and dy1>=y1 and dy2<=y2:
            dw,dh=dx2-dx1,dy2-dy1
            if 40<=dw<=180 and 40<=dh<=180:
                target=db
                break
print('clicking visible browse song:',title,'card=',(x1,y1,x2,y2),'target=',target,'texts=',texts)
open('artifacts/selected-browse-title.txt','w').write(title+'\n')
tx1,ty1,tx2,ty2=target
subprocess.run(['adb','shell','input','tap',str((tx1+tx2)//2),str((ty1+ty2)//2)],check=True)
PY
sleep 20

dump_ui /sdcard/after-play.xml "$ARTIFACTS/browse-after-play.xml"
adb exec-out screencap -p > "$ARTIFACTS/browse-after-play.png"
adb shell dumpsys media_session > "$ARTIFACTS/browse-after-play-media-session.txt" || true
adb logcat -d -t 1800 > "$ARTIFACTS/browse-after-play-logcat.txt" || true

# Final semantic proof: the exact clicked card title must appear in the *upper* Dudu7
# player pane, and the empty-player placeholder must be gone.
python3 - <<'PY'
import re, xml.etree.ElementTree as ET
from pathlib import Path
title=Path('artifacts/selected-browse-title.txt').read_text().strip()
root=ET.parse('artifacts/browse-after-play.xml').getroot(); found=[]
for n in root.iter('node'):
    if n.attrib.get('text','').strip()!=title:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if m:
        b=tuple(map(int,m.groups()))
        if b[1]<960:
            found.append(b)
print('selected title in upper player:',title,found)
if not found:
    raise SystemExit(f'Clicked Browse title did not appear in upper player: {title!r}')
if any(n.attrib.get('text')=='Noch keine Wiedergabe' for n in root.iter('node')):
    raise SystemExit('Player still reports no playback after Browse song tap')
PY

grep -q 'package="com.metrolist.music.dudu7.debug"' "$ARTIFACTS/browse-after-play.xml"
