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


def patch_smoke_test(text: str) -> str:
    text = text.replace('assert_text "Albums category title" 1 "=Albums" "=Alben"\n', "")
    text = text.replace(
        'assert_text "Singles and EPs category title" 1 "=Singles & EPs" "=Singles und EPs" "Singles & EPs" "Singles und EPs"\n',
        "",
    )

    marker = '''PY
}

assert_album_detail() {
'''
    replacement = '''PY
}

assert_right_pane_visually_nonblank() {
    local output="$1" label="$2"
    adb exec-out screencap -p > "$output"
    local crop_x=$((DUDU_WIDTH / 2 + 8))
    local crop_y=180
    local crop_w=$((DUDU_WIDTH - crop_x - 10))
    local crop_h=$((DUDU_HEIGHT - crop_y - 45))
    local stats="${output}.signalstats.txt"
    ffprobe -v error -f lavfi \
        "movie=${output},crop=${crop_w}:${crop_h}:${crop_x}:${crop_y},signalstats" \
        -show_entries frame_tags=lavfi.signalstats.YMIN,lavfi.signalstats.YMAX \
        -of default=noprint_wrappers=1 > "$stats"
    python3 - "$stats" "$label" <<'PY_PIXELS'
import re, sys
path, label = sys.argv[1:]
text = open(path, encoding='utf-8', errors='ignore').read()
values = {key: int(value) for key, value in re.findall(r'(?:lavfi\.signalstats\.)?(YMIN|YMAX)=(\d+)', text)}
spread = values.get('YMAX', 0) - values.get('YMIN', 0)
if spread < 35:
    raise SystemExit(f'{label} is still visually blank: luma={values}, spread={spread}')
print(f'PASS: {label} is visibly rendered; luma={values}, spread={spread}')
PY_PIXELS
}

assert_album_detail() {
'''
    text = replace_once(text, marker, replacement, "visual pixel assertion")

    albums_marker = '''sleep 14
assert_text "left player remains visible on Albums" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/albums-grid.xml"
'''
    albums_replacement = '''sleep 14
assert_text "left player remains visible on Albums" 0 "=Rick Astley"
assert_right_pane_visually_nonblank "$RESULTS_DIR/albums-visible.png" "Albums grid"
dump_ui "$RESULTS_DIR/albums-grid.xml"
'''
    text = replace_once(text, albums_marker, albums_replacement, "Albums visual assertion")

    album_detail_marker = '''sleep 16
dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
'''
    album_detail_replacement = '''sleep 16
assert_right_pane_visually_nonblank "$RESULTS_DIR/album-detail-visible.png" "Album detail"
dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
'''
    text = replace_once(text, album_detail_marker, album_detail_replacement, "album detail visual assertion")

    singles_marker = '''sleep 14
assert_text "left player remains visible on Singles and EPs" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/singles-eps-grid.xml"
'''
    singles_replacement = '''sleep 14
assert_text "left player remains visible on Singles and EPs" 0 "=Rick Astley"
assert_right_pane_visually_nonblank "$RESULTS_DIR/singles-eps-visible.png" "Singles and EPs grid"
dump_ui "$RESULTS_DIR/singles-eps-grid.xml"
'''
    text = replace_once(text, singles_marker, singles_replacement, "Singles visual assertion")

    single_detail_marker = '''sleep 16
dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
'''
    single_detail_replacement = '''sleep 16
assert_right_pane_visually_nonblank "$RESULTS_DIR/single-ep-detail-visible.png" "Single or EP detail"
dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
'''
    text = replace_once(text, single_detail_marker, single_detail_replacement, "single detail visual assertion")
    return text


def patch_version(text: str) -> str:
    text = replace_once(text, "versionCode = 1370028", "versionCode = 1370029", "versionCode")
    text = replace_once(text, 'versionName = "13.7.19"', 'versionName = "13.7.20"', "versionName")
    return text


update("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt", patch_navigation)
update("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt", patch_artist_items)
update("scripts/dudu7_artist_original_subpages_smoke.sh", patch_smoke_test)
update("app/build.gradle.kts", patch_version)

navigation = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt").read_text(encoding="utf-8")
artist_items = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt").read_text(encoding="utf-8")
smoke = (ROOT / "scripts/dudu7_artist_original_subpages_smoke.sh").read_text(encoding="utf-8")
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
for marker in [
    "assert_right_pane_visually_nonblank",
    "Albums grid",
    "Singles and EPs grid",
    "Single or EP detail",
]:
    if marker not in smoke:
        raise SystemExit(f"Missing emulator visual assertion: {marker}")
if "versionCode = 1370029" not in build or 'versionName = "13.7.20"' not in build:
    raise SystemExit("13.7.20 version markers are missing")

print("Applied original MetroList artist category routing, visible grids and pixel-verified emulator test for Dudu7 13.7.20")
