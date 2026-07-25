from pathlib import Path

path = Path("scripts/dudu7_webradio_reliability_smoke.sh")
text = path.read_text(encoding="utf-8")
old = r'''assert_station_active() {
    local label="$1"; local station="$2"
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$station" <<'PY'
import sys, xml.etree.ElementTree as ET
path, station = sys.argv[1:]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
station_node = next((n for n in root.iter('node') if n.attrib.get('text','').strip() == station), None)
if station_node is None:
    raise SystemExit(1)
row = station_node
while row is not None and row.attrib.get('clickable') != 'true':
    row = parent.get(row)
if row is None:
    raise SystemExit(1)
for node in row.iter('node'):
    if 'LÄUFT' in node.attrib.get('text',''):
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "active-station-failure"
        return 1
    fi
}
'''
new = r'''assert_station_active() {
    local label="$1"; local station="$2"
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$station" "$DUDU_WIDTH" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, station, width = sys.argv[1:]
width = int(width)
root = ET.parse(path).getroot()

def bounds(node):
    match = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds', ''))
    return tuple(map(int, match.groups())) if match else None

# The current station name is also shown in the left player. Only consider the
# saved-station row in the right pane, otherwise the assertion can select the
# player artist label and miss the visible sibling indicator.
stations = [
    node for node in root.iter('node')
    if node.attrib.get('text', '').strip() == station
    and bounds(node) is not None
    and bounds(node)[0] >= width // 2
]
indicators = [
    node for node in root.iter('node')
    if 'LÄUFT' in node.attrib.get('text', '')
    and bounds(node) is not None
    and bounds(node)[0] >= width // 2
]
for station_node in stations:
    sl, st, sr, sb = bounds(station_node)
    station_center = (st + sb) / 2
    for indicator in indicators:
        il, it, ir, ib = bounds(indicator)
        indicator_center = (it + ib) / 2
        if abs(station_center - indicator_center) <= 32:
            raise SystemExit(0)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "active-station-failure"
        return 1
    fi
}
'''
if old not in text:
    if 'and bounds(node)[0] >= width // 2' in text:
        print("Right-pane active station assertion already applied")
        raise SystemExit(0)
    raise SystemExit("Original active station assertion not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Active station assertion now ignores the duplicate left-player artist label")
