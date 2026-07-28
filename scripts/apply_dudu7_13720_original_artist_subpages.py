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


def patch_artist_items(text: str) -> str:
    import_marker = "import com.metrolist.music.ui.component.LocalMenuState\n"
    import_replacement = (
        "import com.metrolist.music.ui.component.LocalMenuState\n"
        "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n"
    )
    text = replace_once(text, import_marker, import_replacement, "right pane import")

    local_marker = "    val menuState = LocalMenuState.current\n"
    local_replacement = (
        "    val menuState = LocalMenuState.current\n"
        "    val embeddedInPlayer = LocalRightPaneScrollBridge.current != null\n"
    )
    text = replace_once(text, local_marker, local_replacement, "right pane detection")

    grid_animation_marker = '''                            ).animateItem(),
'''
    grid_animation_replacement = '''                            ).then(
                                // Lazy grid appearance layers can remain at alpha 0 when the
                                // original screen is hosted inside the nested Dudu7 NavHost.
                                // Keep the original grid and interactions, but omit only this
                                // optional item animation in the right pane.
                                if (embeddedInPlayer) Modifier else Modifier.animateItem(),
                            ),
'''
    text = replace_once(text, grid_animation_marker, grid_animation_replacement, "grid item animation")

    placeholder_marker = "                    ShimmerHost(Modifier.animateItem()) {\n"
    placeholder_replacement = (
        "                    ShimmerHost(\n"
        "                        if (embeddedInPlayer) Modifier else Modifier.animateItem(),\n"
        "                    ) {\n"
    )
    text = replace_once(text, placeholder_marker, placeholder_replacement, "grid placeholder animation")
    return text


def patch_version(text: str) -> str:
    text = replace_once(text, "versionCode = 1370028", "versionCode = 1370029", "versionCode")
    text = replace_once(text, 'versionName = "13.7.19"', 'versionName = "13.7.20"', "versionName")
    return text


update("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt", patch_navigation)
update("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt", patch_artist_items)
update("app/build.gradle.kts", patch_version)

navigation = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt").read_text(encoding="utf-8")
artist_items = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt").read_text(encoding="utf-8")
build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")

for marker in ["The right Dudu7 pane owns its own NavHost", "ArtistItemsScreen(navController)"]:
    if marker not in navigation:
        raise SystemExit(f"Missing navigation marker: {marker}")
if "EmbeddedArtistItemsScreen" in navigation:
    raise SystemExit("EmbeddedArtistItemsScreen is still wired into NavigationBuilder")
for marker in [
    "LocalRightPaneScrollBridge.current != null",
    "if (embeddedInPlayer) Modifier else Modifier.animateItem()",
    "Lazy grid appearance layers can remain at alpha 0",
]:
    if marker not in artist_items:
        raise SystemExit(f"Missing embedded grid visibility marker: {marker}")
if "versionCode = 1370029" not in build or 'versionName = "13.7.20"' not in build:
    raise SystemExit("13.7.20 version markers are missing")

print("Applied original MetroList artist category routing and visible right-pane grids for Dudu7 13.7.20")
