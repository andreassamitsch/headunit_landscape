#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
text = path.read_text(encoding="utf-8")
if "import androidx.compose.foundation.layout.heightIn\n" not in text:
    text = text.replace(
        "import androidx.compose.foundation.layout.height\n",
        "import androidx.compose.foundation.layout.height\nimport androidx.compose.foundation.layout.heightIn\n",
        1,
    )
if "import androidx.compose.foundation.rememberScrollState\n" not in text:
    text = text.replace(
        "import androidx.compose.foundation.ExperimentalFoundationApi\n",
        "import androidx.compose.foundation.ExperimentalFoundationApi\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n",
        1,
    )
path.write_text(text, encoding="utf-8")
for needle in (
    "import androidx.compose.foundation.layout.heightIn",
    "import androidx.compose.foundation.rememberScrollState",
    "import androidx.compose.foundation.verticalScroll",
):
    if needle not in text:
        raise SystemExit(f"missing {needle}")
print("WebRadio editor scroll imports fixed")
