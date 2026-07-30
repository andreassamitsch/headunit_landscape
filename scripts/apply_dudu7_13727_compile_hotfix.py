#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def update(path: str, transform) -> None:
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    changed = transform(original)
    if changed == original:
        raise SystemExit(f"{path}: expected compiler hotfix made no change")
    target.write_text(changed, encoding="utf-8")


def make_regex_literals_raw(text: str) -> str:
    # The consolidated Python generator emits Kotlin normal strings. Backslash
    # escapes such as \s are regex escapes, not Kotlin string escapes, so convert
    # only Regex("...") literals containing a backslash to Kotlin raw strings.
    pattern = re.compile(r'Regex\("([^"\n]*\\[^"\n]*)"\)')
    return pattern.sub(lambda match: 'Regex("""' + match.group(1) + '""")', text)


update(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt",
    make_regex_literals_raw,
)
update(
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrOfficialProgramIndex.kt",
    make_regex_literals_raw,
)


def fix_room_state_revision(text: str) -> str:
    old = "revision = proto.revision,"
    if text.count(old) != 1:
        raise SystemExit(f"MessageCodec.kt: expected one RoomState revision occurrence, found {text.count(old)}")
    return text.replace(
        old,
        "revision = 0L, // RoomState protobuf v1 has no revision field",
        1,
    )


update(
    "app/src/main/kotlin/com/metrolist/music/listentogether/MessageCodec.kt",
    fix_room_state_revision,
)

print("Applied 13.7.27 compiler hotfix")
