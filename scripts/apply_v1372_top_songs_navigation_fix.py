#!/usr/bin/env python3
from pathlib import Path


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")
old_section = '''                    artistPage?.sections?.forEachIndexed { index, section ->
                        if (section.items.isNotEmpty()) {
                            item(key = "section_${section.title}") {
                                NavigationTitle(
                                    title = section.title,
                                    modifier = Modifier.animateItem(),
                                    onClick =
                                        section.moreEndpoint?.let {
                                            {
                                                navController.navigate(
                                                    "artist/${viewModel.artistId}/items?browseId=${android.net.Uri.encode(it.browseId)}&params=${android.net.Uri.encode(it.params.orEmpty())}",
                                                )
                                            }
                                        },
                                )
                            }
                        }

                        if ((section.items.firstOrNull() as? SongItem)?.album != null) {
'''
new_section = '''                    artistPage?.sections?.forEachIndexed { index, section ->
                        val isSongSection = (section.items.firstOrNull() as? SongItem)?.album != null
                        val moreEndpoint = section.moreEndpoint
                        val openSection: (() -> Unit)? =
                            when {
                                moreEndpoint != null -> {
                                    {
                                        timber.log.Timber.tag("Dudu7ArtistNavigation").d(
                                            "Opening artist section title=%s browseId=%s fallback=false",
                                            section.title,
                                            moreEndpoint.browseId,
                                        )
                                        navController.navigate(
                                            "artist/${viewModel.artistId}/items?browseId=${android.net.Uri.encode(moreEndpoint.browseId)}&params=${android.net.Uri.encode(moreEndpoint.params.orEmpty())}",
                                        )
                                    }
                                }

                                isSongSection -> {
                                    {
                                        timber.log.Timber.tag("Dudu7ArtistNavigation").d(
                                            "Opening artist section title=%s browseId=none fallback=true",
                                            section.title,
                                        )
                                        navController.navigate(
                                            "artist/${viewModel.artistId}/items?browseId=&params=",
                                        )
                                    }
                                }

                                else -> null
                            }

                        if (section.items.isNotEmpty()) {
                            item(key = "section_${section.title}") {
                                NavigationTitle(
                                    title = section.title,
                                    modifier = Modifier.animateItem(),
                                    onClick = openSection,
                                )
                            }
                        }

                        if (isSongSection) {
'''
if new_section not in artist:
    if old_section not in artist:
        raise SystemExit("ArtistScreen online section marker missing")
    artist = artist.replace(old_section, new_section, 1)
artist_path.write_text(artist, encoding="utf-8")

smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")

clickable_helpers = r'''
find_clickable_coords() {
    local right_only="$1"; shift
    dump_ui "$RESULTS_DIR/current-window.xml" || return 1
    python3 - "$RESULTS_DIR/current-window.xml" "$DUDU_WIDTH" "$right_only" "$@" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width, right_only, *needles = sys.argv[1:]
width = int(width)
exact = [n[1:].casefold() for n in needles if n.startswith('=')]
partial = [n.casefold() for n in needles if not n.startswith('=')]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter('node'):
    values = [node.attrib.get('text','').strip().casefold(), node.attrib.get('content-desc','').strip().casefold()]
    hay = ' '.join(v for v in values if v)
    if not any(v == n for v in values for n in exact) and not (hay and any(n in hay for n in partial)):
        continue
    cur = node
    while cur is not None:
        m = re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', cur.attrib.get('bounds',''))
        if m:
            l,t,r,b = map(int,m.groups())
            if (right_only != '1' or l >= width//2) and r > l and b > t and cur.attrib.get('clickable') == 'true':
                print((l+r)//2, (t+b)//2)
                raise SystemExit(0)
        cur = parent.get(cur)
raise SystemExit(1)
PY
}

tap_clickable_text() {
    local label="$1"; local right="$2"; shift 2
    local coords
    coords=$(find_clickable_coords "$right" "$@") || return 1
    echo "Tapping clickable $label at $coords"
    adb shell input tap $coords
    sleep 3
}
'''
marker = '''}

tap_text() {'''
if "find_clickable_coords()" not in smoke:
    if marker not in smoke:
        raise SystemExit("Smoke tap_text marker missing")
    smoke = smoke.replace(marker, "}\n" + clickable_helpers + "\ntap_text() {", 1)

assert_detail = r'''
assert_artist_items_detail() {
    local xml="$1"
    python3 - "$xml" "$DUDU_WIDTH" <<'PY'
import re, sys, xml.etree.ElementTree as ET
path, width = sys.argv[1], int(sys.argv[2])
root = ET.parse(path).getroot()
texts=[]
for node in root.iter('node'):
    value=(node.attrib.get('text','').strip() or node.attrib.get('content-desc','').strip())
    if not value:
        continue
    m=re.fullmatch(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', node.attrib.get('bounds',''))
    if not m:
        continue
    l,t,r,b=map(int,m.groups())
    if l < width//2:
        continue
    texts.append((value.casefold(), value, l,t,r,b))
appbar_titles=[row for row in texts if row[0] in {'top songs','top-titel','songs'} and row[3] < 190]
about=[row for row in texts if row[0] in {'about','über den künstler','über den interpreten'}]
songs=[row for row in texts if row[0] in {'never gonna give you up','together forever','never gonna give you up (2022 remaster)'} and row[3] >= 170]
if not appbar_titles:
    raise SystemExit('Top Songs detail app bar title is missing')
if about:
    raise SystemExit(f'Artist overview is still visible after Top Songs tap: {about}')
if len({row[0] for row in songs}) < 2:
    raise SystemExit(f'Top Songs detail list is missing expected songs: {songs}')
print(f'PASS: real Top Songs detail screen opened: title={appbar_titles[0][1]}, songs={len(songs)}')
PY
}
'''
marker = '''}

adb wait-for-device'''
if "assert_artist_items_detail()" not in smoke:
    if marker not in smoke:
        raise SystemExit("Smoke adb start marker missing")
    smoke = smoke.replace(marker, "}\n" + assert_detail + "\nadb wait-for-device", 1)

old_test = '''    if ! tap_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
        sleep 3
        tap_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
    sleep 10
    assert_text "artist songs detail content" 1 "=Never Gonna Give You Up" "=Together Forever"
    capture "artist-songs-detail"
'''
new_test = '''    adb logcat -c || true
    if ! tap_clickable_text "artist songs section" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"; then
        adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 700
        sleep 3
        tap_clickable_text "artist songs section retry" 1 "=Songs" "=Top songs" "=Top Songs" "=Top-Titel"
    fi
    sleep 10
    dump_ui "$RESULTS_DIR/artist-songs-detail.xml"
    assert_artist_items_detail "$RESULTS_DIR/artist-songs-detail.xml"
    adb logcat -d -v threadtime > "$RESULTS_DIR/artist-items-navigation-log.txt" || true
    grep -q "Dudu7ArtistNavigation" "$RESULTS_DIR/artist-items-navigation-log.txt"
    grep -q "Dudu7ArtistItems" "$RESULTS_DIR/artist-items-navigation-log.txt"
    capture "artist-songs-detail"
'''
if new_test not in smoke:
    if old_test not in smoke:
        raise SystemExit("Deterministic Top Songs test marker missing")
    smoke = smoke.replace(old_test, new_test, 1)

smoke_path.write_text(smoke, encoding="utf-8")
print("Applied real Top Songs navigation and strict detail validation")
