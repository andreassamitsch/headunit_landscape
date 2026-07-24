#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
player = root / "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt"
text = player.read_text(encoding="utf-8")
marker = "import androidx.compose.foundation.layout.height\n"
addition = marker + "import androidx.compose.foundation.layout.weight\n"
if "import androidx.compose.foundation.layout.weight\n" not in text:
    if marker not in text:
        raise RuntimeError("PhysicalRadioPlayerPane import marker missing")
    text = text.replace(marker, addition, 1)
player.write_text(text, encoding="utf-8")
print("Physical radio source imports prepared")
