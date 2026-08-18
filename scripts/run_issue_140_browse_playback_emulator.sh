#!/usr/bin/env bash
set -euxo pipefail

# Stable workflow entry point for Issue #140.
# The reported path is Home -> visible mood/genre tile -> Browse -> Playlist.
# The older driver incorrectly tapped the "Mood & Genres" section heading and
# then expected a separate MoodAndGenresScreen. That is not the Dudu7 Home path:
# Home already renders the real mood/genre buttons directly.
cp scripts/run_issue_140_browse_playback_emulator_v2.sh /tmp/run_issue_140.sh
python3 - <<'PY'
from pathlib import Path
p = Path('/tmp/run_issue_140.sh')
s = p.read_text()
start = s.index('# Open the original MetroList MoodAndGenresScreen via a real touch.')
end = s.index('# Select a specifically identified PlaylistItem from the actual rendered card')
replacement = r'''# Tap a real visible mood/genre button directly on Home. This is the actual
# Dudu7 path reported in Issue #140; there is no mandatory intermediate
# MoodAndGenresScreen when using the Home section.
adb logcat -c
python3 - <<'PYHOMEGENRE'
import json, re, subprocess, xml.etree.ElementTree as ET
p='artifacts/mood-title-visible.xml'
root=ET.parse(p).getroot()

# Locate the visible Mood/Genre section heading first so candidate buttons are
# constrained to its four-row grid instead of unrelated Home cards.
title_bounds=[]
for n in root.iter('node'):
    text=n.attrib.get('text','').strip()
    if 'Genres' not in text:
        continue
    m=re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]',n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    if 1080 <= y1 < y2 <= 1910:
        title_bounds.append((x1,y1,x2,y2,text))
if not title_bounds:
    raise SystemExit('Visible Home Mood/Genres heading not found')
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
    # At 420 dpi the 48dp MoodAndGenresButton is ~126px high. Restrict the
    # candidate to that geometry and to the four rows directly below heading.
    if not (title_bottom <= y1 < y2 <= 1910):
        continue
    if y1 > title_bottom + 760:
        continue
    if not (140 <= w <= 760 and 70 <= h <= 180):
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
    raise SystemExit('No real Home mood/genre button found below section heading')
candidates.sort()
y1,x1,x2,y2,text=candidates[0]
selected={'title':text,'bounds':[x1,y1,x2,y2],'center':[(x1+x2)//2,(y1+y2)//2]}
print('selected Home genre tile:',selected)
with open('artifacts/selected-home-genre.json','w',encoding='utf-8') as f:
    json.dump(selected,f,ensure_ascii=False,indent=2)
subprocess.run(['adb','shell','input','tap',str(selected['center'][0]),str(selected['center'][1])],check=True)
PYHOMEGENRE
sleep 15

# Prove that the physical Home-tile tap actually navigated to Browse. Browse
# logs every rendered target from its onGloballyPositioned callback, so this is
# stronger than merely seeing some text change in UIAutomator.
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
