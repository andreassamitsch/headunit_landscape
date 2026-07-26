from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoCache.kt")
text = path.read_text(encoding="utf-8")
for invalid_import in (
    "import coil3.request.diskCachePolicy\n",
    "import coil3.request.memoryCachePolicy\n",
    "import coil3.request.scale\n",
    "import coil3.request.size\n",
):
    text = text.replace(invalid_import, "")
path.write_text(text, encoding="utf-8")
print("Applied Coil 3 ImageRequest builder import compatibility fix")
