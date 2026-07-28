#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def update(path: str, transform) -> None:
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    changed = transform(original)
    if changed == original:
        print(f"No change required: {path}")
    else:
        target.write_text(changed, encoding="utf-8")
        print(f"Updated: {path}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source marker, found {count}")
    return text.replace(old, new, 1)


def patch_navigation(text: str) -> str:
    text = text.replace(
        "import com.metrolist.music.ui.screens.artist.EmbeddedArtistItemsScreen\n",
        "",
        1,
    )
    old = '''    ) {
        if (embeddedInPlayer) {
            EmbeddedArtistItemsScreen(navController)
        } else {
            ArtistItemsScreen(navController)
        }
    }
'''
    new = '''    ) {
        // The right Dudu7 pane owns its own NavHost, so it can host the original
        // MetroList category screen directly. Do not replace it with a copied
        // embedded list: the original screen already provides album/single grids,
        // pagination, menus and navigation to the existing AlbumScreen.
        ArtistItemsScreen(navController)
    }
'''
    return replace_once(text, old, new, "artist items route")


def patch_version(text: str) -> str:
    text = replace_once(text, "versionCode = 1370028", "versionCode = 1370029", "versionCode")
    text = replace_once(text, 'versionName = "13.7.19"', 'versionName = "13.7.20"', "versionName")
    return text


update("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt", patch_navigation)
update("app/build.gradle.kts", patch_version)

navigation = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt").read_text(encoding="utf-8")
build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")

required = [
    "The right Dudu7 pane owns its own NavHost",
    "ArtistItemsScreen(navController)",
]
for marker in required:
    if marker not in navigation:
        raise SystemExit(f"Missing navigation marker: {marker}")
if "EmbeddedArtistItemsScreen" in navigation:
    raise SystemExit("EmbeddedArtistItemsScreen is still wired into NavigationBuilder")
if "versionCode = 1370029" not in build or 'versionName = "13.7.20"' not in build:
    raise SystemExit("13.7.20 version markers are missing")

print("Applied original MetroList artist category routing for Dudu7 13.7.20")
