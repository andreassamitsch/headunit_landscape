#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = path.read_text(encoding="utf-8")
old = "                                        trailingContent = null,"
count = text.count(old)
if count == 0:
    if text.count("                                        trailingContent = {},") < 2:
        raise SystemExit("Embedded artist trailing content markers missing")
else:
    if count != 2:
        raise SystemExit(f"Expected exactly two embedded null trailing slots, found {count}")
    text = text.replace(old, "                                        trailingContent = {},")

path.write_text(text, encoding="utf-8")
print("Replaced the two non-null embedded artist trailing slots with empty composables")
