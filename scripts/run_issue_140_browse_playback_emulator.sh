#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point for Issue #140.
# The reported path is Home -> visible mood/genre tile -> Browse -> Playlist.
# Home's mood/genre data comes from a separate asynchronous YouTube Explore
# request, so the E2E driver retries that external feed without weakening any
# touch/navigation assertion. Once the section is found, it is deliberately
# scrolled away from the system-navigation edge before the real adb tap.
cp scripts/run_issue_140_browse_playback_emulator_v2.sh /tmp/run_issue_140.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/run_issue_140.sh')
s = p.read_text()

scan_start = s.index('# Scroll only the lower Dudu7 pane until the real Home section')
scan_end = s.index('# Open the original MetroList MoodAndGenresScreen via a real touch.')
scan_replacement = r'''# Wait for the asynchronously loaded Explore mood/genre feed. A missing Explore
# response is not a touch failure: restart the app process and retry the same
# real Home path so HomeViewModel issues a fresh YouTube.explore() request.
rm -f "$ARTIFACTS/mood-title-visible.xml"
for feed_attempt in 1 2 3; do
  sleep 12
  for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16; do
    dump_ui /sdcard/home-scroll.xml "$ARTIFACTS/home-feed-${feed_attempt}-scroll-$attempt.xml"
    adb exec-out screencap -p > "$ARTIFACTS/home-feed-${feed_attempt}-scroll-$attempt.png" || true
    if python3 - "$ARTIFACTS/home-feed-${feed_attempt}-scroll-$attempt.xml" <<'PYFEED'
import re, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
for n in root.iter('node'):
    if 'Genres' not in n.attrib.get('text',''):
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if 1050 <= y1 < y2 <= 1910 and x2>x1:
        raise SystemExit(0)
raise SystemExit(1)
PYFEED
    then
      # The first visible row can still be clipped by the bottom system area.
      # Move the whole section into the safe center of the app before selecting
      # a tile. This keeps the test a genuine coordinate touch, not semantics.
      adb shell input swipe 800 1740 800 1280 550
      sleep 3
      dump_ui /sdcard/mood-safe.xml "$ARTIFACTS/mood-title-visible.xml"
      adb exec-out screencap -p > "$ARTIFACTS/mood-title-visible.png" || true
      break
    fi
    adb shell input swipe 800 1770 800 1180 650
    sleep 2
  done

  if test -f "$ARTIFACTS/mood-title-visible.xml"; then
    echo "Home mood/genre feed available on attempt $feed_attempt"
    break
  fi

  adb logcat -d -v brief > "$ARTIFACTS/home-feed-${feed_attempt}-missing-logcat.txt" || true
  adb shell am force-stop "$PACKAGE"
  sleep 2
  adb shell am start -W -n "$PACKAGE/$ACTIVITY"
  sleep 18
done
test -f "$ARTIFACTS/mood-title-visible.xml"

'''
s = s[:scan_start] + scan_replacement + s[scan_end:]

start = s.index('# Open the original MetroList MoodAndGenresScreen via a real touch.')
end = s.index('# Select a specifically identified PlaylistItem from the actual rendered card')
replacement = r'''# Tap a fully visible real mood/genre button directly on Home.
adb logcat -c
python3 - <<'PYHOMEGENRE'
import json, re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-title-visible.xml'
root=ET.parse(p).getroot()

title_bounds=[]
for n in root.iter('node'):
    text=n.attrib.get('text','').strip()
    if 'Genres' not in text:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if 700 <= y1 < y2 <= 1800:
        title_bounds.append((x1,y1,x2,y2,text))
if not title_bounds:
    raise SystemExit('Visible Home Mood/Genres heading not found in safe area')
title=min(title_bounds,key=lambda b:b[1])
title_bottom=title[3]

ignored={'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}
candidates=[]
seen=set()
for n in root.iter('node'):
    if n.attrib.get('clickable') != 'true':
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups()); w=x2-x1; h=y2-y1
    center_y=(y1+y2)//2
    if not (title_bottom <= y1 < y2 <= 1780):
        continue
    if y1 > title_bottom + 760:
        continue
    # 48dp at 420dpi is ~126 px. Require a substantially complete tile so a
    # clipped edge item can never be mistaken for a valid touch target.
    if not (140 <= w <= 760 and 105 <= h <= 180 and 850 <= center_y <= 1720):
        continue
    text=n.attrib.get('text','').strip()
    if not text:
        for d in n.iter('node'):
            t=d.attrib.get('text','').strip()
            if t:
                text=t
                break
    if not text or text in ignored or 'Genres' in text:
        continue
    key=(x1,y1,x2,y2)
    if key in seen:
        continue
    seen.add(key)
    candidates.append((y1,x1,x2,y2,text))
if not candidates:
    raise SystemExit('No fully visible Home mood/genre button found in safe touch area')
candidates.sort()
y1,x1,x2,y2,text=candidates[0]
selected={'title':text,'bounds':[x1,y1,x2,y2],'center':[(x1+x2)//2,(y1+y2)//2]}
print('selected safe Home genre tile:',selected)
with open('artifacts/selected-home-genre.json','w',encoding='utf-8') as f:
    json.dump(selected,f,ensure_ascii=False,indent=2)
subprocess.run(['adb','shell','input','tap',str(selected['center'][0]),str(selected['center'][1])],check=True)
PYHOMEGENRE
sleep 15

adb logcat -d -v brief > "$ARTIFACTS/home-genre-after-tap-logcat.txt"
dump_ui /sdcard/browse.xml "$ARTIFACTS/browse-page.xml"
adb exec-out screencap -p > "$ARTIFACTS/browse-page.png"
python3 - <<'PYBROWSE'
from pathlib import Path
log=Path('artifacts/home-genre-after-tap-logcat.txt').read_text(encoding='utf-8',errors='replace')
if 'Dudu7BrowseTarget' not in log:
    relevant='\n'.join(line for line in log.splitlines() if 'Dudu7RightPaneTap' in line or 'Dudu7Browse' in line)
    print(relevant)
    raise SystemExit('Home genre touch did not reach/render BrowseScreen')
xml=Path('artifacts/browse-page.xml').read_text(encoding='utf-8',errors='replace')
if "isn\'t responding" in xml:
    raise SystemExit('System ANR dialog covered Browse after Home genre tap')
print('PASS: real Home mood/genre touch reached BrowseScreen')
PYBROWSE

'''
s = s[:start] + replacement + s[end:]
p.write_text(s)
PY
exec bash /tmp/run_issue_140.sh
