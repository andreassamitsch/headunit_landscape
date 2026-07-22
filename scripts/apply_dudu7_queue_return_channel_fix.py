#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one occurrence in {path}, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


connection = Path("app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt")
replace_once(
    connection,
    "import kotlinx.coroutines.flow.MutableSharedFlow\n",
    "import kotlinx.coroutines.channels.Channel\n",
)
replace_once(
    connection,
    "import kotlinx.coroutines.flow.asSharedFlow\n",
    "import kotlinx.coroutines.flow.receiveAsFlow\n",
)
replace_once(
    connection,
    """    private val _userSongSelections = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    val userSongSelections = _userSongSelections.asSharedFlow()

    fun notifyUserSongSelection() {
        _userSongSelections.tryEmit(Unit)
    }
""",
    """    private val userSongSelectionChannel = Channel<Unit>(capacity = Channel.BUFFERED)
    val userSongSelections = userSongSelectionChannel.receiveAsFlow()

    fun notifyUserSongSelection() {
        userSongSelectionChannel.trySend(Unit)
    }
""",
)

test = Path("scripts/dudu7_ui_smoke.sh")
replace_once(
    test,
    """    python3 - "$RESULTS_DIR/selected-tab.xml" "$@" <<'PY_SELECTED'
import sys
import xml.etree.ElementTree as ET
xml_path, *labels = sys.argv[1:]
labels = {label.casefold() for label in labels}
root = ET.parse(xml_path).getroot()
for node in root.iter("node"):
    values = {
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    }
    if values & labels and node.attrib.get("selected") == "true":
        raise SystemExit(0)
raise SystemExit(1)
PY_SELECTED
""",
    """    python3 - "$RESULTS_DIR/selected-tab.xml" "$@" <<'PY_SELECTED'
import sys
import xml.etree.ElementTree as ET
xml_path, *labels = sys.argv[1:]
labels = {label.casefold() for label in labels}
root = ET.parse(xml_path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter("node"):
    values = {
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    }
    if not values & labels:
        continue
    current = node
    while current is not None:
        if current.attrib.get("selected") == "true":
            raise SystemExit(0)
        current = parent.get(current)
raise SystemExit(1)
PY_SELECTED
""",
)
replace_once(
    test,
    """root = ET.parse(xml_path).getroot()
for node in root.iter("node"):
    values = [
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    ]
    haystack = " ".join(filter(None, values))
    if not any(value == needle for value in values for needle in exact) and not (
        haystack and any(needle in haystack for needle in partial)
    ):
        continue
    match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", node.attrib.get("bounds", ""))
    if not match:
        continue
    left, top, right, bottom = map(int, match.groups())
    if left < minimum_left or right <= left or bottom <= top:
        continue
    print(f"{(left + right) // 2} {(top + bottom) // 2}")
    raise SystemExit(0)
raise SystemExit(1)
PY_RIGHT
""",
    """root = ET.parse(xml_path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter("node"):
    values = [
        node.attrib.get("text", "").strip().casefold(),
        node.attrib.get("content-desc", "").strip().casefold(),
    ]
    haystack = " ".join(filter(None, values))
    if not any(value == needle for value in values for needle in exact) and not (
        haystack and any(needle in haystack for needle in partial)
    ):
        continue

    current = node
    fallback = None
    while current is not None:
        match = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", current.attrib.get("bounds", ""))
        if match:
            left, top, right, bottom = map(int, match.groups())
            if left >= minimum_left and right > left and bottom > top:
                fallback = (left, top, right, bottom)
                if current.attrib.get("clickable") == "true":
                    print(f"{(left + right) // 2} {(top + bottom) // 2}")
                    raise SystemExit(0)
        current = parent.get(current)

    if fallback is not None:
        left, top, right, bottom = fallback
        print(f"{(left + right) // 2} {(top + bottom) // 2}")
        raise SystemExit(0)
raise SystemExit(1)
PY_RIGHT
""",
)

verify = Path("scripts/verify_dudu7_architecture.py")
text = verify.read_text(encoding="utf-8")
old = '    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n'
new = '''    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt": (
        "Channel.BUFFERED",
        "userSongSelectionChannel.receiveAsFlow()",
        "userSongSelectionChannel.trySend(Unit)",
    ),
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (
'''
if "Channel.BUFFERED" not in text:
    if old not in text:
        raise SystemExit("Verification insertion anchor missing")
    verify.write_text(text.replace(old, new, 1), encoding="utf-8")

print("Dudu7 queue-return channel and UI-test targeting patch applied")
