from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Missing expected text in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# Version ---------------------------------------------------------------------
replace_once(
    "app/build.gradle.kts",
    'versionCode = 155\n        versionName = "13.6.6"',
    'versionCode = 156\n        versionName = "13.6.7"',
)

# WebRadio favorites: preserve saved order/start index, show active playback,
# and resolve each logo only once per station/homepage composition.
radio_screen = "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
replace_once(
    radio_screen,
    "    val savedStations by store.stations.collectAsStateWithLifecycle()\n    val scope = rememberCoroutineScope()",
    "    val savedStations by store.stations.collectAsStateWithLifecycle()\n"
    "    val currentMediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()\n"
    "    val radioIsPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()\n"
    "    val currentRadioMediaId = currentMediaMetadata?.id?.takeIf { it.startsWith(\"radio:\") }\n"
    "    val scope = rememberCoroutineScope()",
)
replace_once(
    radio_screen,
    '''    // Resolve missing or broken artwork in the background as soon as the saved
    // station library is visible. The resolved URL is persisted, so later starts
    // do not have to rediscover the logo.
    LaunchedEffect(savedStations.map { Triple(it.uuid, it.favicon, it.homepage) }) {
        savedStations.forEach { station ->
            RadioStationLogoResolver.resolve(station)?.let { logo ->
                if (logo != station.favicon) {
                    store.addOrUpdate(station.copy(favicon = logo))
                }
            }
        }
    }

''',
    "",
)
replace_once(
    radio_screen,
    '''    fun playSaved(station: RadioStation) {
        // ListQueue playback is most reliable from index 0. Rotate the saved list so
        // the explicitly selected favorite starts immediately while previous/next
        // can still switch through all saved stations.
        val stations = savedStations.ifEmpty { listOf(station) }
        val selected = stations.firstOrNull { it.uuid == station.uuid } ?: station
        val orderedStations = listOf(selected) + stations.filterNot { it.uuid == selected.uuid }
        playerConnection.playQueue(
            queue =
                ListQueue(
                    title = "WebRadio",
                    items = orderedStations.map { it.toMediaItem() },
                    startIndex = 0,
                ),
            notifyUserSelection = false,
        )
    }
''',
    '''    fun playSaved(station: RadioStation) {
        // Keep the persisted favorite order intact. Media3 supports a non-zero
        // start index, so favorite 3 remains queue position 3 and previous/next
        // follow the same order the user sees in the WebRadio list.
        val stations =
            if (savedStations.any { it.uuid == station.uuid }) {
                savedStations
            } else {
                savedStations + station
            }
        val startIndex = stations.indexOfFirst { it.uuid == station.uuid }.coerceAtLeast(0)
        playerConnection.playQueue(
            queue =
                ListQueue(
                    title = "WebRadio",
                    items = stations.map { it.toMediaItem() },
                    startIndex = startIndex,
                ),
            notifyUserSelection = false,
        )
    }
''',
)
replace_once(
    radio_screen,
    '''                            RadioStationRow(
                                station = station,
                                isSaved = true,
                                onPlay = { playSaved(station) },''',
    '''                            val isActive = currentRadioMediaId == station.mediaId
                            RadioStationRow(
                                station = station,
                                isSaved = true,
                                isActive = isActive,
                                isPlaying = isActive && radioIsPlaying,
                                onPlay = {
                                    if (isActive) playerConnection.togglePlayPause() else playSaved(station)
                                },''',
)
replace_once(
    radio_screen,
    '''                                RadioStationRow(
                                    station = station,
                                    isSaved = savedStations.any { it.uuid == station.uuid },
                                    onPlay = {
                                        playerConnection.playQueue(
                                            queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                            notifyUserSelection = false,
                                        )
                                    },''',
    '''                                val isActive = currentRadioMediaId == station.mediaId
                                RadioStationRow(
                                    station = station,
                                    isSaved = savedStations.any { it.uuid == station.uuid },
                                    isActive = isActive,
                                    isPlaying = isActive && radioIsPlaying,
                                    onPlay = {
                                        if (isActive) {
                                            playerConnection.togglePlayPause()
                                        } else {
                                            playerConnection.playQueue(
                                                queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                                notifyUserSelection = false,
                                            )
                                        }
                                    },''',
)
replace_once(
    radio_screen,
    '''private fun RadioStationRow(
    station: RadioStation,
    isSaved: Boolean,
    onPlay: () -> Unit,''',
    '''private fun RadioStationRow(
    station: RadioStation,
    isSaved: Boolean,
    isActive: Boolean = false,
    isPlaying: Boolean = false,
    onPlay: () -> Unit,''',
)
replace_once(
    radio_screen,
    '''    LaunchedEffect(station.uuid, station.favicon, station.homepage) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->''',
    '''    // Do not key this effect by favicon. Persisting a discovered image must
    // not immediately start a second discovery pass that can select another logo.
    LaunchedEffect(station.uuid, station.homepage) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->''',
)
replace_once(
    radio_screen,
    '''            Modifier
                .fillMaxWidth()
                .combinedClickable(onClick = onPlay, onLongClick = { onEdit?.invoke() })
                .padding(horizontal = 12.dp, vertical = 8.dp),''',
    '''            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(
                    if (isActive) {
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.48f)
                    } else {
                        MaterialTheme.colorScheme.surface.copy(alpha = 0f)
                    },
                )
                .combinedClickable(onClick = onPlay, onLongClick = { onEdit?.invoke() })
                .padding(horizontal = 12.dp, vertical = 8.dp),''',
)
replace_once(
    radio_screen,
    '''            Text(
                station.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            val details =''',
    '''            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    station.name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                if (isActive) {
                    Text(
                        text = if (isPlaying) "● LÄUFT" else "PAUSIERT",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (isPlaying) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                    )
                }
            }
            val details =''',
)

# Stable logo choice: a working raster URL is authoritative and must not be
# replaced by a different homepage candidate on every composition/app start.
logo_resolver = "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt"
replace_once(
    logo_resolver,
    '''            val homepage = station.homepage.trim().takeIf(::isHttpUrl)

            station.favicon.trim().takeIf(::isHttpUrl)?.let {
                candidates += Candidate(it, priority = if (isVectorUrl(it)) 120 else 520)
            }
''',
    '''            val homepage = station.homepage.trim().takeIf(::isHttpUrl)
            val existingArtwork = station.favicon.trim().takeIf(::isHttpUrl)

            // Once a usable raster image has been persisted, keep it stable.
            // This prevents stations such as kronehit from alternating between
            // multiple equally valid logos discovered on the same homepage.
            if (existingArtwork != null && !isVectorUrl(existingArtwork)) {
                resolveUsableImage(existingArtwork)?.let { return@withContext it }
            }

            existingArtwork?.let {
                candidates += Candidate(it, priority = if (isVectorUrl(it)) 120 else 520)
            }
''',
)

# Artist pages in the embedded pane must use their actual pane width, not the
# whole device width. Keep WebRadio in the back stack as well.
artist_screen = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    artist_screen,
    "import androidx.compose.foundation.layout.Box\n",
    "import androidx.compose.foundation.layout.Box\nimport androidx.compose.foundation.layout.BoxWithConstraints\n",
)
replace_once(
    artist_screen,
    "import androidx.compose.ui.platform.LocalResources\n",
    "",
)
replace_once(
    artist_screen,
    '''fun ArtistScreen(
    navController: NavController,
    viewModel: ArtistViewModel = hiltViewModel(),
) {''',
    '''fun ArtistScreen(
    navController: NavController,
    viewModel: ArtistViewModel = hiltViewModel(),
    embeddedInPlayer: Boolean = false,
) {''',
)
replace_once(
    artist_screen,
    '''    val density = LocalDensity.current

    // Calculate the offset value outside of the offset lambda''',
    '''    val density = LocalDensity.current
    val artistHeaderAspectRatio = if (embeddedInPlayer) 1.45f else 1f

    // Calculate the offset value outside of the offset lambda''',
)
replace_once(
    artist_screen,
    '''    Box(
        modifier = Modifier.fillMaxSize(),
    ) {''',
    '''    BoxWithConstraints(
        modifier = Modifier.fillMaxSize(),
    ) {
        val embeddedPaneWidth = maxWidth''',
)
replace_once(
    artist_screen,
    ".aspectRatio(1.1f),",
    ".aspectRatio(if (embeddedInPlayer) 1.45f else 1.1f),",
)
replace_once(
    artist_screen,
    ".aspectRatio(1f)\n                                        .offset {",
    ".aspectRatio(artistHeaderAspectRatio)\n                                        .offset {",
)
replace_once(
    artist_screen,
    '''                                        top =
                                            if (thumbnail != null) {
                                                // Position content at the bottom part of the image
                                                // Using screen width to calculate aspect ratio height minus overlap
                                                LocalResources.current.displayMetrics.widthPixels.let { screenWidth ->
                                                    with(density) {
                                                        ((screenWidth / 1.2f) - 144).toDp()
                                                    }
                                                }
                                            } else {
                                                16.dp
                                            },''',
    '''                                        top =
                                            if (thumbnail != null) {
                                                // BoxWithConstraints reports the real right-pane width.
                                                // The previous full-screen displayMetrics value pushed all
                                                // controls below the visible embedded area.
                                                (embeddedPaneWidth / artistHeaderAspectRatio -
                                                    if (embeddedInPlayer) 88.dp else 144.dp)
                                                    .coerceAtLeast(if (embeddedInPlayer) 180.dp else 240.dp)
                                            } else {
                                                16.dp
                                            },''',
)
replace_once(
    artist_screen,
    "                onLongClick = navController::backToMain,",
    '''                onLongClick = {
                    if (embeddedInPlayer) navController.navigateUp() else navController.backToMain()
                },''',
)

navigation_builder = "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt"
replace_once(
    navigation_builder,
    "        ArtistScreen(navController)\n",
    "        ArtistScreen(navController, embeddedInPlayer = embeddedInPlayer)\n",
)

vehicle_layout = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(
    vehicle_layout,
    '''                paneNavController.navigate(route) {
                    popUpTo(VEHICLE_QUEUE_ROUTE) {
                        saveState = true
                    }
                    launchSingleTop = true
                }''',
    '''                // Keep WebRadio in the pane back stack. Back from the artist
                // page now returns to the station list instead of the queue root.
                paneNavController.navigate(route) {
                    launchSingleTop = true
                }''',
)

# Radio always shows artwork instead of an empty lyrics view.
player_file = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
replace_once(
    player_file,
    "                    onToggleLyrics = { showInlineLyrics = !showInlineLyrics },",
    "                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },",
)
replace_once(
    player_file,
    "                            targetState = showInlineLyrics,",
    "                            targetState = showInlineLyrics && !isWebRadio,",
)

# Deterministic test server: add a kronehit-style SVG + homepage with two
# alternating equally valid raster logos. A correct client requests the page
# only until one raster logo is persisted and never toggles afterwards.
server = "scripts/icy_test_server.py"
replace_once(
    server,
    '''        if self.path == "/station3-home":
            self._bytes(
                200,
                b'<html><head><link rel="apple-touch-icon" sizes="512x512" href="/logo3.png"></head><body>Test Radio Three</body></html>',
                "text/html; charset=utf-8",
            )
            return
''',
    '''        if self.path == "/station3-home":
            self._bytes(
                200,
                b'<html><head><link rel="apple-touch-icon" sizes="512x512" href="/logo3.png"></head><body>Test Radio Three</body></html>',
                "text/html; charset=utf-8",
            )
            return
        if self.path == "/kronehit.svg":
            self._bytes(
                200,
                b'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#111"/><text x="20" y="140" fill="white">KRONEHIT</text></svg>',
                "image/svg+xml",
            )
            return
        if self.path == "/kronehit-home":
            count = getattr(self.server, "kronehit_home_requests", 0) + 1
            self.server.kronehit_home_requests = count
            logos = ("/logo1.png", "/logo2.png") if count % 2 else ("/logo2.png", "/logo1.png")
            body = (
                '<html><body><img class="station-logo" alt="kronehit logo" src="%s">'
                '<img class="station-logo" alt="kronehit logo" src="%s"></body></html>'
            ) % logos
            self._bytes(200, body.encode(), "text/html; charset=utf-8")
            return
''',
)
replace_once(
    server,
    '''        if self.path == "/station3":
            self._stream("Test Radio Three", "Station identification", self.server.audio3)
            return
''',
    '''        if self.path == "/station3":
            self._stream("Test Radio Three", "Station identification", self.server.audio3)
            return
        if self.path == "/station4":
            self._stream("kronehit", "Kronehit Artist - Kronehit Track", self.server.audio2)
            return
''',
)

# UI regression test -----------------------------------------------------------
test = "scripts/dudu7_webradio_reliability_smoke.sh"
replace_once(
    test,
    ''' {"uuid":"test-radio-three","name":"Test Radio Three","streamUrl":"http://10.0.2.2:8000/station3","homepage":"http://10.0.2.2:8000/station3-home","favicon":"","country":"Austria","language":"German","tags":"Test,Indie","codec":"MP3","bitrate":96},
 {"uuid":"9608a2aa-0601-11e8-ae97-52543be04c81","name":"Antenne Steiermark","streamUrl":"http://live.antenne.at/as","homepage":"http://www.antenne.at/","favicon":"https://upload.wikimedia.org/wikipedia/commons/6/63/Antenne_Logo.svg","country":"Austria","language":"German","tags":"Pop,Austria","codec":"MP3","bitrate":128}''',
    ''' {"uuid":"test-radio-three","name":"Test Radio Three","streamUrl":"http://10.0.2.2:8000/station3","homepage":"http://10.0.2.2:8000/station3-home","favicon":"","country":"Austria","language":"German","tags":"Test,Indie","codec":"MP3","bitrate":96},
 {"uuid":"test-radio-four","name":"kronehit","streamUrl":"http://10.0.2.2:8000/station4","homepage":"http://10.0.2.2:8000/kronehit-home","favicon":"http://10.0.2.2:8000/kronehit.svg","country":"Austria","language":"German","tags":"Hits,Austria","codec":"MP3","bitrate":96},
 {"uuid":"9608a2aa-0601-11e8-ae97-52543be04c81","name":"Antenne Steiermark","streamUrl":"http://live.antenne.at/as","homepage":"http://www.antenne.at/","favicon":"https://upload.wikimedia.org/wikipedia/commons/6/63/Antenne_Logo.svg","country":"Austria","language":"German","tags":"Pop,Austria","codec":"MP3","bitrate":128}''',
)
replace_once(
    test,
    '''assert_text "third saved station" 1 "=Test Radio Three"
assert_text "Antenne Steiermark saved station" 1 "=Antenne Steiermark"''',
    '''assert_text "third saved station" 1 "=Test Radio Three"
assert_text "kronehit saved station" 1 "=kronehit"
assert_text "Antenne Steiermark saved station" 1 "=Antenne Steiermark"''',
)
replace_once(
    test,
    '''echo "PASS: Antenne Steiermark received a persisted raster station logo"
capture "webradio-three-favorites"''',
    '''echo "PASS: Antenne Steiermark received a persisted raster station logo"
python3 - "$RESULTS_DIR/radio-prefs-after-logo.xml" > "$RESULTS_DIR/kronehit-logo-before.txt" <<'PY'
import html, json, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
raw=html.unescape(root.find("string").text or "[]")
station=next(x for x in json.loads(raw) if x["uuid"] == "test-radio-four")
print(station["favicon"])
PY
if grep -q 'kronehit.svg' "$RESULTS_DIR/kronehit-logo-before.txt"; then
    echo "FAIL: kronehit still uses SVG artwork" >&2
    exit 1
fi
capture "webradio-five-favorites"''',
)
replace_once(
    test,
    '''assert_text "radio artist page loaded inside right pane" 1 "Play All" "Alle wiedergeben"
adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
grep -E 'Resolved radio artist navigation: Rick Astley -> Rick Astley' "$RESULTS_DIR/radio-artist-navigation-log.txt"
echo "PASS: radio artist resolved to Rick Astley and opened inside the right pane"
capture "radio-artist-right-pane"
tap_tab "WebRadio" "=WebRadio"
''',
    '''assert_text "radio artist name visible in compact pane" 1 "=Rick Astley"
adb shell input swipe 1100 620 1100 230 500
sleep 3
assert_text "radio artist page scrolls and exposes content" 1 "Songs" "Alben" "Albums" "Never Gonna Give You Up"
adb logcat -d -v threadtime > "$RESULTS_DIR/radio-artist-navigation-log.txt" 2>&1 || true
grep -E 'Resolved radio artist navigation: Rick Astley -> Rick Astley' "$RESULTS_DIR/radio-artist-navigation-log.txt"
echo "PASS: radio artist resolved, rendered at pane width and scrolled inside the right pane"
capture "radio-artist-right-pane"
adb shell input keyevent KEYCODE_BACK
sleep 3
assert_text "back from artist returns to WebRadio favorites" 1 "=Gespeichert"
# Open it once more and exercise a real artist action. This must use the
# embedded navigator and normal music selection must return to the queue tab.
tap_text "station one favorite after artist back" 1 "=Test Radio One"
sleep 8
tap_text "radio artist link functional test" 0 "=Rick Astley"
sleep 10
tap_text "artist Radio action" 1 "=Radio"
sleep 15
assert_text "artist action opened normal music queue" 1 "Warteschlange" "Queue"
tap_tab "WebRadio" "=WebRadio"
''',
)
replace_once(
    test,
    '''# Exercise the rotated three-favorite queue in both directions.
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 10
assert_text "next from third reaches first" 0 "=Never Gonna Give You Up"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 10
assert_text "next reaches second" 0 "=Test Track Two"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous returns to first" 0 "=Never Gonna Give You Up"
''',
    '''# Start favorite 3 at its real saved-list index and exercise the unchanged
# order in both directions. The active indicator must follow every player skip.
assert_text "third favorite active indicator" 1 "● LÄUFT"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous from favorite three reaches favorite two" 0 "=Test Track Two"
assert_text "favorite two active indicator" 1 "● LÄUFT"
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 8
assert_text "previous again reaches favorite one" 0 "=Never Gonna Give You Up"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next returns to favorite two" 0 "=Test Track Two"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next returns to favorite three" 0 "=Station identification"
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 8
assert_text "next from favorite three reaches following kronehit favorite" 0 "=Kronehit Track"
assert_text "kronehit active indicator" 1 "● LÄUFT"
# Recreate the WebRadio screen repeatedly. The persisted kronehit raster logo
# must remain byte-for-byte the same and its alternating homepage must not be
# requested again.
for i in 1 2 3; do
    tap_tab "Warteschlange" "=Warteschlange" "=Queue"
    tap_tab "WebRadio" "=WebRadio"
done
sleep 8
adb shell run-as "$PACKAGE_NAME" cat shared_prefs/metrolist_webradio.xml > "$RESULTS_DIR/radio-prefs-after-reopen.xml"
python3 - "$RESULTS_DIR/radio-prefs-after-reopen.xml" > "$RESULTS_DIR/kronehit-logo-after.txt" <<'PY'
import html, json, sys, xml.etree.ElementTree as ET
root=ET.parse(sys.argv[1]).getroot()
raw=html.unescape(root.find("string").text or "[]")
station=next(x for x in json.loads(raw) if x["uuid"] == "test-radio-four")
print(station["favicon"])
PY
cmp "$RESULTS_DIR/kronehit-logo-before.txt" "$RESULTS_DIR/kronehit-logo-after.txt"
echo "PASS: kronehit logo stayed stable across repeated pane recreation"
''',
)
replace_once(
    test,
    '''assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Radio Three" "Test Track Two" "Station identification"''',
    '''assert_absent_right "radio station absent from music history" "Test Radio One" "Test Radio Two" "Test Radio Three" "kronehit" "Antenne Steiermark" "Test Track Two" "Station identification" "Kronehit Track"''',
)
replace_once(
    test,
    '''- Three saved stations repeatedly started and replaced
- Radio -> YouTube -> Radio -> YouTube -> Radio transitions passed
- ICY artist/title metadata visible in the left player
- Previous/next switches the three-station saved queue
- Missing station logo discovered from homepage and persisted''',
    '''- Five saved stations repeatedly started and replaced
- WebRadio stays open while radio playback and player skip controls are used
- Favorite 3 starts at queue index 3 with favorites 1/2 before and the rest after
- Active play indicator follows the currently playing favorite
- Radio -> YouTube -> Radio -> YouTube -> Radio transitions passed
- ICY artist/title metadata visible in the left player
- Radio always uses artwork rather than an empty lyrics panel
- Artist page renders at right-pane width, scrolls, navigates and plays content
- Missing station logo discovered from homepage and persisted
- kronehit logo remains stable instead of alternating''',
)

print("WebRadio 13.6.7 patch applied")

# Final embedded-artist and semantic test corrections -------------------------
replace_once(
    artist_screen,
    "                                                    playerConnection.playQueue(YouTubeQueue(radioEndpoint))",
    '''                                                    playerConnection.playQueue(YouTubeQueue(radioEndpoint))
                                                    if (embeddedInPlayer) {
                                                        navController.popBackStack("vehicle_queue", inclusive = false)
                                                    }''',
)
replace_once(
    artist_screen,
    "                                                        playerConnection.playQueue(YouTubeQueue(shuffleEndpoint))",
    '''                                                        playerConnection.playQueue(YouTubeQueue(shuffleEndpoint))
                                                        if (embeddedInPlayer) {
                                                            navController.popBackStack("vehicle_queue", inclusive = false)
                                                        }''',
)

replace_once(
    test,
    '''}

assert_absent_right() {''',
    '''}

assert_selected_tab() {
    local label="$1"; shift
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$@" <<'PY'
import sys, xml.etree.ElementTree as ET
path, *needles = sys.argv[1:]
needles = [n.casefold() for n in needles]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
for node in root.iter('node'):
    values = [node.attrib.get('text','').strip(), node.attrib.get('content-desc','').strip()]
    hay = ' '.join(v for v in values if v).casefold()
    if not hay or not any(n in hay for n in needles):
        continue
    cur = node
    while cur is not None:
        if cur.attrib.get('selected') == 'true':
            raise SystemExit(0)
        cur = parent.get(cur)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "selected-tab-failure"
        return 1
    fi
}

assert_station_active() {
    local label="$1"; local station="$2"
    dump_ui || return 1
    if python3 - "$RESULTS_DIR/current-window.xml" "$station" <<'PY'
import sys, xml.etree.ElementTree as ET
path, station = sys.argv[1:]
root = ET.parse(path).getroot()
parent = {child: node for node in root.iter() for child in node}
station_node = next((n for n in root.iter('node') if n.attrib.get('text','').strip() == station), None)
if station_node is None:
    raise SystemExit(1)
row = station_node
while row is not None and row.attrib.get('clickable') != 'true':
    row = parent.get(row)
if row is None:
    raise SystemExit(1)
for node in row.iter('node'):
    if 'LÄUFT' in node.attrib.get('text',''):
        raise SystemExit(0)
raise SystemExit(1)
PY
    then
        echo "PASS: $label"
    else
        echo "FAIL: $label" >&2
        capture "active-station-failure"
        return 1
    fi
}

assert_absent_right() {''',
)

replace_once(
    test,
    'assert_text "WebRadio tab remains open after favorite start" 1 "=Gespeichert"',
    '''assert_selected_tab "WebRadio tab remains selected after favorite start" "WebRadio"
assert_station_active "favorite two row shows active playback" "Test Radio Two"''',
)
replace_once(
    test,
    'assert_text "WebRadio tab remains open after second favorite" 1 "=Gespeichert"',
    '''assert_selected_tab "WebRadio tab remains selected after second favorite" "WebRadio"
assert_station_active "favorite one row shows active playback" "Test Radio One"''',
)
replace_once(
    test,
    'assert_text "artist action opened normal music queue" 1 "Warteschlange" "Queue"',
    '''assert_selected_tab "artist action selected normal music queue" "Warteschlange" "Queue"
assert_absent_anywhere "LIVE after artist radio action" "=LIVE"''',
)
replace_once(
    test,
    'assert_text "third favorite active indicator" 1 "● LÄUFT"',
    'assert_station_active "third favorite active indicator" "Test Radio Three"',
)
replace_once(
    test,
    'assert_text "favorite two active indicator" 1 "● LÄUFT"',
    'assert_station_active "favorite two active indicator" "Test Radio Two"',
)
replace_once(
    test,
    'assert_text "kronehit active indicator" 1 "● LÄUFT"',
    'assert_station_active "kronehit active indicator" "kronehit"',
)

print("WebRadio 13.6.7 final artist/test corrections applied")
