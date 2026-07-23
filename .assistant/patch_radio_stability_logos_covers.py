from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected block: {label}")
    return text.replace(old, new, 1)

# Radio Browser: logo enrichment and more robust playlist/redirect resolution.
client_path = Path('app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt')
client = client_path.read_text(encoding='utf-8')
client = client.replace('MetrolistHU/13.6.4 (Android WebRadio)', 'MetrolistHU/13.6.5 (Android WebRadio)')
insert = '''
    suspend fun findStationLogo(station: RadioStation): Result<String?> =
        runCatching {
            if (station.favicon.isNotBlank()) return@runCatching station.favicon
            val candidates = search(station.name).getOrThrow()
            val stationHost = runCatching { URI(station.streamUrl).host.orEmpty().removePrefix("www.") }.getOrDefault("")
            candidates
                .asSequence()
                .filter { it.favicon.isNotBlank() }
                .sortedByDescending { candidate ->
                    var score = 0
                    if (candidate.uuid == station.uuid) score += 100
                    if (candidate.name.equals(station.name, ignoreCase = true)) score += 50
                    val candidateHost = runCatching { URI(candidate.streamUrl).host.orEmpty().removePrefix("www.") }.getOrDefault("")
                    if (stationHost.isNotBlank() && candidateHost == stationHost) score += 30
                    score
                }
                .firstOrNull()
                ?.favicon
                ?.takeIf { it.startsWith("http://") || it.startsWith("https://") }
        }

'''
client = replace_once(client, '    suspend fun resolveStreamUrl(input: String): Result<String> =\n', insert + '    suspend fun resolveStreamUrl(input: String): Result<String> =\n', 'logo lookup insertion')
client_path.write_text(client, encoding='utf-8')

# WebRadio UI: resolve selected favorite on every start, refresh missing logos, and keep a stable queue.
screen_path = Path('app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt')
screen = screen_path.read_text(encoding='utf-8')
screen = screen.replace('import androidx.compose.runtime.Composable\n', 'import androidx.compose.runtime.Composable\nimport androidx.compose.runtime.LaunchedEffect\n', 1)
old_play = '''    fun playSaved(station: RadioStation) {
        // ListQueue playback is most reliable from index 0. Rotate the saved list so
        // the explicitly selected favorite starts immediately while previous/next
        // can still switch through all saved stations.
        val stations = savedStations.ifEmpty { listOf(station) }
        val selected = stations.firstOrNull { it.uuid == station.uuid } ?: station
        val orderedStations = listOf(selected) + stations.filterNot { it.uuid == selected.uuid }
        playerConnection.playQueue(
            ListQueue(
                title = "WebRadio",
                items = orderedStations.map { it.toMediaItem() },
                startIndex = 0,
            ),
        )
    }
'''
new_play = '''    fun playSaved(station: RadioStation) {
        scope.launch {
            isLoading = true
            errorMessage = null
            val selected =
                RadioBrowserClient.resolveStreamUrl(station.streamUrl)
                    .getOrElse {
                        errorMessage = it.message ?: "Stream konnte nicht geöffnet werden"
                        isLoading = false
                        return@launch
                    }.let { resolved -> station.copy(streamUrl = resolved) }
            if (selected != station) store.addOrUpdate(selected)
            val stations = savedStations.ifEmpty { listOf(selected) }
            val orderedStations = listOf(selected) + stations.filterNot { it.uuid == selected.uuid }
            // Explicitly stop the previous source before replacing a YouTube or radio queue.
            // This also makes repeated starts of the same favorite deterministic.
            playerConnection.player.stop()
            playerConnection.playQueue(
                ListQueue(
                    title = "WebRadio",
                    items = orderedStations.map { it.toMediaItem() },
                    startIndex = 0,
                ),
            )
            isLoading = false
        }
    }
'''
screen = replace_once(screen, old_play, new_play, 'saved playback')
anchor = '    fun performSearch() {\n'
logo_effect = '''    LaunchedEffect(savedStations.map { "${it.uuid}:${it.favicon}" }) {
        savedStations.filter { it.favicon.isBlank() }.forEach { station ->
            RadioBrowserClient.findStationLogo(station).getOrNull()?.let { logo ->
                if (logo.isNotBlank()) store.addOrUpdate(station.copy(favicon = logo))
            }
        }
    }

'''
screen = replace_once(screen, anchor, logo_effect + anchor, 'logo effect')
# Enrich stations when saving search results.
screen = replace_once(screen, '                                    onSave = {\n                                        store.addOrUpdate(station)\n                                    },\n', '''                                    onSave = {
                                        scope.launch {
                                            val logo = RadioBrowserClient.findStationLogo(station).getOrNull()
                                            store.addOrUpdate(if (logo.isNullOrBlank()) station else station.copy(favicon = logo))
                                        }
                                    },
''', 'search save logo')
screen_path.write_text(screen, encoding='utf-8')

# Strict radio title parsing and high-resolution, verified cover selection.
player_path = Path('app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt')
player = player_path.read_text(encoding='utf-8')
old_parse = '''    private fun parseRadioStreamTitle(raw: String): Pair<String?, String> {
        val cleaned = raw.substringBefore(" [").trim()
        val separator = listOf(" - ", " – ", " — ", " | ").firstOrNull { it in cleaned }
        if (separator == null) return null to cleaned
        val artist = cleaned.substringBefore(separator).trim().takeIf { it.isNotBlank() }
        val title = cleaned.substringAfter(separator).trim().ifBlank { cleaned }
        return artist to title
    }
'''
new_parse = '''    private fun parseRadioStreamTitle(raw: String): Pair<String?, String> {
        val cleaned = raw.substringBefore(" [").trim()
        val separator = listOf(" - ", " – ", " — ").firstOrNull { it in cleaned }
        if (separator == null) return null to cleaned
        val artist = cleaned.substringBefore(separator).trim()
        val title = cleaned.substringAfter(separator).trim()
        val invalidTokens = listOf("http://", "https://", "www.", "radio", "unknown", "advert", "werbung")
        val isClear =
            artist.length in 2..100 && title.length in 2..160 &&
                invalidTokens.none { token -> artist.equals(token, true) || title.equals(token, true) } &&
                !artist.equals(title, ignoreCase = true)
        return if (isClear) artist to title else null to cleaned
    }
'''
player = replace_once(player, old_parse, new_parse, 'strict title parsing')
old_lookup_core = '''                        YouTube.search("$artist $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull()
                            ?.thumbnail
'''
new_lookup_core = '''                        val normalizedArtist = normalizeRadioText(artist)
                        val normalizedTitle = normalizeRadioText(title)
                        YouTube.search("$artist $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { item ->
                                normalizeRadioText(item.title) == normalizedTitle &&
                                    item.artists.any { resultArtist ->
                                        val candidate = normalizeRadioText(resultArtist.name)
                                        candidate == normalizedArtist || candidate.contains(normalizedArtist) || normalizedArtist.contains(candidate)
                                    }
                            }
                            ?.thumbnail
                            ?.let(::highResolutionRadioCover)
'''
player = replace_once(player, old_lookup_core, new_lookup_core, 'verified cover selection')
helper_anchor = '    override fun onTimelineChanged(\n'
helpers = '''    private fun normalizeRadioText(value: String): String =
        value.lowercase()
            .replace(Regex("[^a-z0-9äöüß]+"), " ")
            .trim()

    private fun highResolutionRadioCover(url: String): String {
        val sizePattern = Regex("=w\\d+-h\\d+([^?]*)$")
        return when {
            sizePattern.containsMatchIn(url) -> url.replace(sizePattern, "=w1200-h1200-l90-rj")
            "googleusercontent.com" in url -> url.substringBefore('=') + "=w1200-h1200-l90-rj"
            else -> url
        }
    }

'''
player = replace_once(player, helper_anchor, helpers + helper_anchor, 'cover helpers')
player_path.write_text(player, encoding='utf-8')

# Version bump.
build_path = Path('app/build.gradle.kts')
build = build_path.read_text(encoding='utf-8')
build = replace_once(build, 'versionCode = 153', 'versionCode = 154', 'version code')
build = replace_once(build, 'versionName = "13.6.4"', 'versionName = "13.6.5"', 'version name')
build_path.write_text(build, encoding='utf-8')

# Extended deterministic smoke sequence: multiple favorites and YouTube/radio transitions.
test_path = Path('scripts/dudu7_webradio_smoke.sh')
test = test_path.read_text(encoding='utf-8')
insert_before = '# Verify URL/M3U editor exists.\n'
extended = '''# Repeat several favorite starts and switch between YouTube and WebRadio.
tap_tab "WebRadio" "=WebRadio"
tap_text "first favorite after second" 1 "=Test Radio One"
sleep 10
assert_text "first favorite repeated start" 0 "Test Track One"
tap_tab "WebRadio" "=WebRadio"
tap_text "second favorite repeated" 1 "=Test Radio Two"
sleep 10
assert_text "second favorite repeated start" 0 "Test Track Two"

# Switch back to a normal YouTube item, then return to the saved radio again.
adb shell am start -W -a android.intent.action.VIEW -d "$TEST_URL" "$PACKAGE_NAME" >/dev/null || true
sleep 18
assert_text "YouTube title after radio" 0 "=Never Gonna Give You Up"
tap_tab "WebRadio" "=WebRadio"
tap_text "favorite after YouTube" 1 "=Test Radio One"
sleep 10
assert_text "radio restarts after YouTube" 0 "Test Track One"

'''
test = replace_once(test, insert_before, extended + insert_before, 'extended transitions')
test_path.write_text(test, encoding='utf-8')

for path, needles in {
    client_path: ['findStationLogo', '13.6.5'],
    screen_path: ['playerConnection.player.stop()', 'LaunchedEffect(savedStations.map'],
    player_path: ['normalizeRadioText', 'highResolutionRadioCover', 'firstOrNull { item ->'],
    test_path: ['favorite after YouTube', 'second favorite repeated'],
}.items():
    text = path.read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            raise SystemExit(f'Missing {needle} in {path}')
