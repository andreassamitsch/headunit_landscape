#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
files = [
    root / "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt",
    root / "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
]

for path in files:
    text = path.read_text(encoding="utf-8")
    text = text.replace("import androidx.compose.foundation.layout.weight\n", "")
    path.write_text(text, encoding="utf-8")

print("Physical radio source imports prepared")
