#!/usr/bin/env bash
set -euxo pipefail

ARTIFACTS=artifacts
mkdir -p "$ARTIFACTS"

# Reuse the complete Issue #140 physical-touch path first. It installs the
# x86_64 Dudu7 APK and leaves the emulator on the opened OnlinePlaylistScreen.
bash scripts/run_issue_140_browse_playback_emulator.sh

cp "$ARTIFACTS/playlist-after-tap.xml" "$ARTIFACTS/playlist-before-scroll.xml"
cp "$ARTIFACTS/playlist-after-tap.png" "$ARTIFACTS/playlist-before-scroll.png"

python3 - <<'PY'
import json
from pathlib import Path
selected=json.loads(Path('artifacts/selected-playlist.json').read_text(encoding='utf-8'))
Path('artifacts/playlist-scroll-target.txt').write_text(selected['title']+'\n',encoding='utf-8')
print('playlist scroll target:', selected['title'])
PY

# A real finger-like vertical gesture in the middle of the Dudu7 content pane.
# Use three swipes so the large playlist header must leave first-visible-item
# position when native LazyColumn scrolling is working.
adb logcat -c
for attempt in 1 2 3; do
  adb shell input swipe 700 1760 700 1210 700
  sleep 2
done

adb shell uiautomator dump /sdcard/playlist-after-scroll.xml
adb pull /sdcard/playlist-after-scroll.xml "$ARTIFACTS/playlist-after-scroll.xml"
adb exec-out screencap -p > "$ARTIFACTS/playlist-after-scroll.png"
adb logcat -d -v brief > "$ARTIFACTS/playlist-after-scroll-logcat.txt"

# OnlinePlaylistScreen only puts the playlist title into the TopAppBar when
# lazyListState.firstVisibleItemIndex > 0. Before scrolling the same title is in
# the large header lower in the pane. Seeing it in the fixed top-bar band after
# real adb swipes therefore proves that the LazyColumn itself changed scroll
# position, rather than merely receiving a gesture/focus event.
python3 - <<'PY'
import json, re, xml.etree.ElementTree as ET
from pathlib import Path

selected=json.loads(Path('artifacts/selected-playlist.json').read_text(encoding='utf-8'))
title=selected['title'].strip()
before=ET.parse('artifacts/playlist-before-scroll.xml').getroot()
after=ET.parse('artifacts/playlist-after-scroll.xml').getroot()
rx=re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')

def title_nodes(root):
    found=[]
    for n in root.iter('node'):
        text=n.attrib.get('text','').strip()
        if not text or (text != title and title not in text and text not in title):
            continue
        m=rx.match(n.attrib.get('bounds',''))
        if not m:
            continue
        found.append((*map(int,m.groups()),text))
    return found

before_nodes=title_nodes(before)
after_nodes=title_nodes(after)
print('playlist title before scroll:',before_nodes)
print('playlist title after scroll:',after_nodes)

# Dudu7 embedded content begins below the tab row. The playlist TopAppBar title
# lives near the top of that pane; the large header title starts much lower.
TOP_MIN=1070
TOP_MAX=1290
before_top=[n for n in before_nodes if TOP_MIN <= n[1] < n[3] <= TOP_MAX]
after_top=[n for n in after_nodes if TOP_MIN <= n[1] < n[3] <= TOP_MAX]

if before_top:
    raise SystemExit(f'Precondition invalid: playlist title was already in TopAppBar: {before_top}')
if not after_top:
    raise SystemExit(f'Real vertical swipes did not advance OnlinePlaylistScreen past header; after={after_nodes}')

# Also require the XML to materially change so a static overlay cannot satisfy
# the title assertion accidentally.
before_text=Path('artifacts/playlist-before-scroll.xml').read_text(encoding='utf-8',errors='replace')
after_text=Path('artifacts/playlist-after-scroll.xml').read_text(encoding='utf-8',errors='replace')
if before_text == after_text:
    raise SystemExit('Playlist UI hierarchy did not change after real swipes')

print('PASS: real adb swipes scrolled OnlinePlaylistScreen; TopAppBar title is visible:',after_top)
PY

# A short touch after the swipe must still be treated as a row tap, not as a
# drag. Find a visible enabled song row away from the trailing overflow button,
# tap its left/centre area, then require the existing playback marker.
adb logcat -c
python3 - <<'PY'
import re, subprocess, xml.etree.ElementTree as ET
root=ET.parse('artifacts/playlist-after-scroll.xml').getroot()
rx=re.compile(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]')
ignored={'Home','Warteschlange','Bibliothek','WebRadio','FM','Suche','Hörverlauf'}
candidates=[]
for n in root.iter('node'):
    text=n.attrib.get('text','').strip()
    if not text or text in ignored:
        continue
    m=rx.match(n.attrib.get('bounds',''))
    if not m:
        continue
    x1,y1,x2,y2=map(int,m.groups())
    # Song titles occupy the main text area of ~60dp rows. Stay below the
    # TopAppBar and above system navigation, and avoid the trailing menu area.
    if 1290 <= y1 < y2 <= 1880 and x1 < 850 and 20 <= (y2-y1) <= 110:
        candidates.append((y1,x1,x2,y2,text))
if not candidates:
    raise SystemExit('No visible playlist row text found after scroll')
candidates.sort()
y1,x1,x2,y2,text=candidates[0]
x=min(700,max(180,(x1+x2)//2))
y=(y1+y2)//2
print('tapping visible playlist row after scroll:',text,(x,y))
subprocess.run(['adb','shell','input','tap',str(x),str(y)],check=True)
PY
sleep 5
adb logcat -d -v brief > "$ARTIFACTS/playlist-row-after-scroll-tap-logcat.txt"
if ! grep -q 'Dudu7PlaylistPlayback.*play row' "$ARTIFACTS/playlist-row-after-scroll-tap-logcat.txt"; then
  echo 'Visible row tap after scrolling did not reach playlist playback path' >&2
  grep -E 'Dudu7Playlist|Dudu7RightPane' "$ARTIFACTS/playlist-row-after-scroll-tap-logcat.txt" || true
  exit 1
fi

echo 'PASS: Issue #150 playlist native touch scrolling and post-scroll row tap verified'
