#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# On Dudu7 the full player is permanently expanded. Disabling the sheet's drag
# detector prevents it from competing with every vertical LazyColumn in the
# right pane. Phone/tablet behavior remains unchanged.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt",
    '''    BottomSheet(
        state = state,
        modifier = modifier,
        background = {''',
    '''    BottomSheet(
        state = state,
        modifier = modifier,
        isExpandable = !VehicleVariantConfig.isDudu7,
        background = {''',
)

# Compose tabs do not expose clickable=true in the uiautomator hierarchy. The
# split assertion must inspect the selected tab/pane ancestor instead of making
# clickability a prerequisite.
replace_once(
    "scripts/dudu7_v1371_regression_smoke.sh",
    '''for node in root.iter('node'):
    values = {node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()}
    if not values & labels:
        continue
    cur = node
    while cur is not None:
        m = re.fullmatch(r'\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]', cur.attrib.get('bounds',''))
        if m and cur.attrib.get('clickable') == 'true':
            l,t,r,b = map(int,m.groups())
            expected = width // 2
            if expected - 55 <= l <= expected + 100:
                print(f'PASS: right pane begins near half width: left={l}, expected={expected}')
                raise SystemExit(0)
        cur = parent.get(cur)
raise SystemExit('Right pane does not begin near the 50/50 split')''',
    '''for node in root.iter('node'):
    values = {node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()}
    if not values & labels:
        continue
    cur = node
    candidates = []
    while cur is not None:
        m = re.fullmatch(r'\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            if r > width // 2 and b > t:
                candidates.append((l,t,r,b,cur.attrib.get('selected') == 'true'))
        cur = parent.get(cur)
    expected = width // 2
    for l,t,r,b,selected in candidates:
        if expected - 55 <= l <= expected + 100 and (selected or r >= width - 20):
            print(f'PASS: right pane begins near half width: left={l}, expected={expected}, selected={selected}')
            raise SystemExit(0)
raise SystemExit('Right pane does not begin near the 50/50 split')''',
)
