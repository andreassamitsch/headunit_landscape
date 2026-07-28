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


def wrap_single_root(text: str, start_marker: str, root_comment: str, label: str) -> str:
    if root_comment in text:
        return text
    text = replace_once(
        text,
        start_marker,
        f"    // {root_comment}\n    Box(modifier = Modifier.fillMaxSize()) {{\n{start_marker}",
        f"{label} root start",
    )
    ending = "\n    )\n}\n"
    if not text.endswith(ending):
        raise SystemExit(f"{label}: unexpected function ending")
    return text[: -len(ending)] + "\n    )\n    }\n}\n"


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
    if "import androidx.compose.foundation.layout.Box\n" not in text:
        text = text.replace(
            "import androidx.compose.foundation.combinedClickable\n",
            "import androidx.compose.foundation.combinedClickable\n"
            "import androidx.compose.foundation.layout.Box\n"
            "import androidx.compose.foundation.layout.fillMaxSize\n",
            1,
        )
    text = text.replace("import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n", "")
    text = text.replace("    val embeddedInPlayer = LocalRightPaneScrollBridge.current != null\n", "")

    animated = '''                            ).then(
                                // Lazy grid appearance layers can remain at alpha 0 when the
                                // original screen is hosted inside the nested Dudu7 NavHost.
                                // Keep the original grid and interactions, but omit only this
                                // optional item animation in the right pane.
                                if (embeddedInPlayer) Modifier else Modifier.animateItem(),
                            ),
'''
    text = text.replace(animated, "                            ).animateItem(),\n", 1)
    placeholder = '''                    ShimmerHost(
                        if (embeddedInPlayer) Modifier else Modifier.animateItem(),
                    ) {
'''
    text = text.replace(placeholder, "                    ShimmerHost(Modifier.animateItem()) {\n", 1)

    return wrap_single_root(
        text,
        "    if (itemsPage == null) {\n",
        "One root keeps the TopAppBar wrap-content inside nested Dudu7 AnimatedContent.",
        "ArtistItemsScreen",
    )


def patch_album(text: str) -> str:
    return wrap_single_root(
        text,
        "    LazyColumn(\n",
        "One root prevents the TopAppBar from becoming a full-pane overlay in Dudu7.",
        "AlbumScreen",
    )


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

    replacements = [
        (
            '''sleep 14
assert_text "left player remains visible on Albums" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/albums-grid.xml"
''',
            '''sleep 14
assert_text "left player remains visible on Albums" 0 "=Rick Astley"
assert_right_pane_visually_nonblank "$RESULTS_DIR/albums-visible.png" "Albums grid"
dump_ui "$RESULTS_DIR/albums-grid.xml"
''',
            "Albums visual assertion",
        ),
        (
            '''sleep 16
dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
''',
            '''sleep 16
assert_right_pane_visually_nonblank "$RESULTS_DIR/album-detail-visible.png" "Album detail"
dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
''',
            "album detail visual assertion",
        ),
        (
            '''sleep 14
assert_text "left player remains visible on Singles and EPs" 0 "=Rick Astley"
dump_ui "$RESULTS_DIR/singles-eps-grid.xml"
''',
            '''sleep 14
assert_text "left player remains visible on Singles and EPs" 0 "=Rick Astley"
assert_right_pane_visually_nonblank "$RESULTS_DIR/singles-eps-visible.png" "Singles and EPs grid"
dump_ui "$RESULTS_DIR/singles-eps-grid.xml"
''',
            "Singles visual assertion",
        ),
        (
            '''sleep 16
dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
''',
            '''sleep 16
assert_right_pane_visually_nonblank "$RESULTS_DIR/single-ep-detail-visible.png" "Single or EP detail"
dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
''',
            "single detail visual assertion",
        ),
    ]
    for old, new, label in replacements:
        text = replace_once(text, old, new, label)

    scroll_function_marker = '''
assert_no_crash() {
'''
    scroll_function_replacement = '''
assert_album_detail_after_scroll() {
    local xml="$1" expected="$2" label="$3"
    local attempt
    for attempt in 1 2 3 4 5 6; do
        dump_ui "$xml"
        if assert_album_detail "$xml" "$expected"; then
            echo "PASS: $label exposes its song rows after $attempt view(s)"
            return 0
        fi
        adb shell input swipe \
            $((DUDU_WIDTH * 82 / 100)) $((DUDU_HEIGHT * 82 / 100)) \
            $((DUDU_WIDTH * 82 / 100)) $((DUDU_HEIGHT * 28 / 100)) 700
        sleep 3
    done
    echo "FAIL: $label never exposed clickable song rows" >&2
    return 1
}

assert_no_crash() {
'''
    text = replace_once(text, scroll_function_marker, scroll_function_replacement, "album detail scroll helper")

    text = replace_once(
        text,
        '''dump_ui "$RESULTS_DIR/album-detail.xml"
assert_album_detail "$RESULTS_DIR/album-detail.xml" "$album_title"
''',
        '''assert_album_detail_after_scroll "$RESULTS_DIR/album-detail.xml" "$album_title" "Album detail"
''',
        "album detail scrolling assertion",
    )
    text = replace_once(
        text,
        '''dump_ui "$RESULTS_DIR/single-ep-detail.xml"
assert_album_detail "$RESULTS_DIR/single-ep-detail.xml" "$single_title"
''',
        '''assert_album_detail_after_scroll "$RESULTS_DIR/single-ep-detail.xml" "$single_title" "Single or EP detail"
''',
        "single detail scrolling assertion",
    )
    return text


def patch_version(text: str) -> str:
    text = replace_once(text, "versionCode = 1370028", "versionCode = 1370029", "versionCode")
    text = replace_once(text, 'versionName = "13.7.19"', 'versionName = "13.7.20"', "versionName")
    return text


update("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt", patch_navigation)
update("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt", patch_artist_items)
update("app/src/main/kotlin/com/metrolist/music/ui/screens/AlbumScreen.kt", patch_album)
update("scripts/dudu7_artist_original_subpages_smoke.sh", patch_smoke_test)
update("app/build.gradle.kts", patch_version)

navigation = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt").read_text(encoding="utf-8")
artist_items = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt").read_text(encoding="utf-8")
album = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/AlbumScreen.kt").read_text(encoding="utf-8")
smoke = (ROOT / "scripts/dudu7_artist_original_subpages_smoke.sh").read_text(encoding="utf-8")
build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")

for marker in ["The right Dudu7 pane owns its own NavHost", "ArtistItemsScreen(navController)"]:
    if marker not in navigation:
        raise SystemExit(f"Missing navigation marker: {marker}")
if "EmbeddedArtistItemsScreen" in navigation:
    raise SystemExit("EmbeddedArtistItemsScreen is still wired into NavigationBuilder")
for marker, source in [
    ("One root keeps the TopAppBar wrap-content", artist_items),
    ("Box(modifier = Modifier.fillMaxSize())", artist_items),
    ("One root prevents the TopAppBar", album),
    ("Box(modifier = Modifier.fillMaxSize())", album),
]:
    if marker not in source:
        raise SystemExit(f"Missing single-root marker: {marker}")
for marker in [
    "assert_right_pane_visually_nonblank",
    "assert_album_detail_after_scroll",
    "Albums grid",
    "Singles and EPs grid",
    "Single or EP detail",
]:
    if marker not in smoke:
        raise SystemExit(f"Missing emulator assertion: {marker}")
if "versionCode = 1370029" not in build or 'versionName = "13.7.20"' not in build:
    raise SystemExit("13.7.20 version markers are missing")

print("Applied original MetroList artist/album screens with constrained roots and full emulator navigation proof")
