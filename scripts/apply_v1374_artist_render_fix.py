#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

animation_count = artist.count(".animateItem()")
if animation_count:
    # The embedded Dudu7 pane scrolls the LazyColumn from its parent gesture bridge.
    # Lazy item placement animation kept semantic bounds up to date, but the actual
    # graphics layers stayed outside the clipped pane after a drag, producing an
    # all-white artist body. These animations are cosmetic, so remove them from the
    # artist screen while preserving every item, action and navigation target.
    artist = artist.replace(".animateItem()", "")

if ".animateItem()" in artist:
    raise SystemExit("Artist item placement animations are still present")
artist_path.write_text(artist, encoding="utf-8")


smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")

pixel_helper = r'''
assert_artist_pixels_not_blank() {
    local image="$1"
    python3 - "$image" "$DUDU_WIDTH" "$DUDU_HEIGHT" <<'PY'
from PIL import Image
import numpy as np
import sys

path, width, height = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
image = Image.open(path).convert('RGB')
# Exclude tabs and top app bar. The remaining crop is exactly the artist body that
# became white on the Dudu7 video although accessibility XML still contained nodes.
left = width // 2 + 18
top = 185
right = width - 18
bottom = height - 18
crop = np.asarray(image.crop((left, top, right, bottom)), dtype=np.int16)
brightness = crop.mean(axis=2)
chroma = crop.max(axis=2) - crop.min(axis=2)
dark_fraction = float((brightness < 235).mean())
colored_fraction = float((chroma > 15).mean())
std = float(crop.std())
print(
    f'Artist pixel evidence: dark={dark_fraction:.5f} '
    f'colored={colored_fraction:.5f} std={std:.3f}'
)
# The reproduced white failure had dark ~= 0.004, colored == 0 and std ~= 10.
# Require clear visual content, not merely logical UI nodes.
if dark_fraction < 0.012 and colored_fraction < 0.004 and std < 16.0:
    raise SystemExit('Artist pane is visually blank/white after scrolling')
print('PASS: artist pane has real rendered pixels after scrolling')
PY
}
'''
if "assert_artist_pixels_not_blank()" not in smoke:
    marker = """assert_artist_not_blank() {
"""
    if marker not in smoke:
        raise SystemExit("Smoke XML blank helper marker missing")
    smoke = smoke.replace(marker, pixel_helper + "\n" + marker, 1)

old_scroll_block = '''    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-scroll.xml"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) 350
    sleep 3
    dump_ui "$RESULTS_DIR/artist-after-strong-scroll.xml"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-strong-scroll.xml"
'''
new_scroll_block = '''    dump_ui "$RESULTS_DIR/artist-after-scroll.xml"
    adb exec-out screencap -p > "$RESULTS_DIR/artist-after-scroll.png"
    assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-scroll.xml"
    assert_artist_pixels_not_blank "$RESULTS_DIR/artist-after-scroll.png"
    adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) 350
    sleep 3
    dump_ui "$RESULTS_DIR/artist-after-strong-scroll.xml"
    adb exec-out screencap -p > "$RESULTS_DIR/artist-after-strong-scroll.png"
    assert_artist_not_blank "$RESULTS_DIR/artist-after-strong-scroll.xml"
    assert_artist_pixels_not_blank "$RESULTS_DIR/artist-after-strong-scroll.png"
'''
smoke = replace_once(smoke, old_scroll_block, new_scroll_block, "Smoke screenshot pixel assertions")

old_retry = '''    if ! tap_clickable_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
        sleep 3
        tap_clickable_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
'''
new_retry = '''    if ! tap_clickable_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        # The stress scroll may have passed the title. Return toward the beginning
        # instead of scrolling even farther away as the previous test did.
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*22/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*88/100)) 450
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*22/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*88/100)) 450
        sleep 4
        tap_clickable_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
'''
smoke = replace_once(smoke, old_retry, new_retry, "Smoke Top Songs recovery direction")

smoke = smoke.replace(
    "- PASS: artist content visibly moved and stayed populated after repeated strong swipes\n",
    "- PASS: artist content visibly moved and real screenshot pixels stayed rendered after repeated strong swipes\n",
    1,
)

smoke_path.write_text(smoke, encoding="utf-8")
print(f"Removed {animation_count} artist item animations and added screenshot-based blank-pane validation")
