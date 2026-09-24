#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_count(path: Path, old: str, new: str, expected: int) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != expected:
        raise SystemExit(f"Expected {expected} occurrences in {path}, found {actual}: {old[:120]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


root = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Radio Browser: refresh a saved station by its stable UUID before playback.
# ---------------------------------------------------------------------------
radio_client = root / "app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt"
replace_once(
    radio_client,
    '    private const val SEARCH_ENDPOINT = "https://all.api.radio-browser.info/json/stations/search"\n',
    '    private const val SEARCH_ENDPOINT = "https://all.api.radio-browser.info/json/stations/search"\n'
    '    private const val STATION_BY_UUID_ENDPOINT = "https://all.api.radio-browser.info/json/stations/byuuid"\n',
)
replace_once(
    radio_client,
    '    private fun normalizeCountry(value: String): String =\n',
    '''    /**
     * Refresh a saved Radio Browser entry before playback. Radio Browser's
     * url_resolved can change while the station UUID remains stable, so a saved
     * favorite must not keep using a stale resolved URL forever.
     */
    suspend fun refreshStation(station: RadioStation): Result<RadioStation> =
        runCatching {
            withContext(Dispatchers.IO) {
                require(station.uuid.isNotBlank()) { "Sender-ID fehlt" }
                val endpoint = URL("$STATION_BY_UUID_ENDPOINT/${encode(station.uuid)}")
                val array = JSONArray(readText(endpoint, connectTimeoutMs = 2_500, readTimeoutMs = 3_500))
                require(array.length() > 0) { "Sender ist nicht mehr im Radio-Browser-Verzeichnis" }
                val item = array.getJSONObject(0)
                val streamUrl = item.optString("url_resolved").ifBlank { item.optString("url") }
                require(streamUrl.isNotBlank()) { "Aktuelle Stream-Adresse fehlt" }
                station.copy(
                    name = item.optString("name").trim().ifBlank { station.name },
                    streamUrl = streamUrl,
                    homepage = item.optString("homepage").ifBlank { station.homepage },
                    favicon =
                        if (station.manualFavicon) {
                            station.favicon
                        } else {
                            item.optString("favicon").ifBlank { station.favicon }
                        },
                    country = item.optString("country").ifBlank { station.country },
                    language = item.optString("language").ifBlank { station.language },
                    tags = item.optString("tags").ifBlank { station.tags },
                    codec = item.optString("codec").ifBlank { station.codec },
                    bitrate = item.optInt("bitrate", station.bitrate),
                )
            }
        }

    private fun normalizeCountry(value: String): String =
''',
)
replace_once(
    radio_client,
    '    private fun readText(url: URL): String {\n'
    '        val connection = (url.openConnection() as HttpURLConnection).apply {\n'
    '            connectTimeout = 12_000\n'
    '            readTimeout = 15_000\n',
    '    private fun readText(\n'
    '        url: URL,\n'
    '        connectTimeoutMs: Int = 12_000,\n'
    '        readTimeoutMs: Int = 15_000,\n'
    '    ): String {\n'
    '        val connection = (url.openConnection() as HttpURLConnection).apply {\n'
    '            connectTimeout = connectTimeoutMs\n'
    '            readTimeout = readTimeoutMs\n',
)

# ---------------------------------------------------------------------------
# Pure helpers used by UI and unit tests: retain user order while replacing
# stale station objects (especially streamUrl) from the store.
# ---------------------------------------------------------------------------
helper = root / "app/src/main/kotlin/com/metrolist/music/radio/RadioFavoriteQueue.kt"
helper.write_text(
    '''package com.metrolist.music.radio

/** Preserve the visible drag order while replacing stale station data. */
internal fun mergeSavedStationUpdates(
    ordered: List<RadioStation>,
    saved: List<RadioStation>,
): List<RadioStation> {
    val byId = saved.associateBy { it.uuid }
    val retainedOrder = ordered.mapNotNull { byId[it.uuid] }
    val retainedIds = retainedOrder.asSequence().map { it.uuid }.toHashSet()
    return retainedOrder + saved.filterNot { it.uuid in retainedIds }
}

/** Replace the selected station with a freshly resolved version in-place. */
internal fun replaceFavoriteStation(
    ordered: List<RadioStation>,
    selected: RadioStation,
): List<RadioStation> {
    val replaced = ordered.map { if (it.uuid == selected.uuid) selected else it }
    return if (replaced.any { it.uuid == selected.uuid }) replaced else replaced + selected
}
''',
    encoding="utf-8",
)

helper_test = root / "app/src/test/kotlin/com/metrolist/music/radio/RadioFavoriteQueueTest.kt"
helper_test.parent.mkdir(parents=True, exist_ok=True)
helper_test.write_text(
    '''package com.metrolist.music.radio

import kotlin.test.Test
import kotlin.test.assertEquals

class RadioFavoriteQueueTest {
    @Test
    fun `store updates replace stale URL without changing drag order`() {
        val aOld = RadioStation(uuid = "a", name = "A", streamUrl = "https://old/a")
        val bOld = RadioStation(uuid = "b", name = "B", streamUrl = "https://old/b")
        val aFresh = aOld.copy(streamUrl = "https://fresh/a")
        val bFresh = bOld.copy(streamUrl = "https://fresh/b")

        val merged = mergeSavedStationUpdates(listOf(bOld, aOld), listOf(aFresh, bFresh))

        assertEquals(listOf("b", "a"), merged.map { it.uuid })
        assertEquals("https://fresh/b", merged[0].streamUrl)
        assertEquals("https://fresh/a", merged[1].streamUrl)
    }

    @Test
    fun `fresh selected station replaces only its queue entry`() {
        val a = RadioStation(uuid = "a", name = "A", streamUrl = "https://old/a")
        val b = RadioStation(uuid = "b", name = "B", streamUrl = "https://old/b")
        val freshB = b.copy(streamUrl = "https://fresh/b")

        val result = replaceFavoriteStation(listOf(a, b), freshB)

        assertEquals(listOf("a", "b"), result.map { it.uuid })
        assertEquals("https://fresh/b", result[1].streamUrl)
    }
}
''',
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# Latest queue request wins. A slow older request must never overwrite a newer
# station selection after its asynchronous getInitialStatus() returns.
# ---------------------------------------------------------------------------
gate = root / "app/src/main/kotlin/com/metrolist/music/playback/LatestRequestGate.kt"
gate.write_text(
    '''package com.metrolist.music.playback

import java.util.concurrent.atomic.AtomicLong

internal class LatestRequestGate {
    private val generation = AtomicLong(0L)

    fun issue(): Long = generation.incrementAndGet()

    fun isCurrent(token: Long): Boolean = generation.get() == token
}
''',
    encoding="utf-8",
)

gate_test = root / "app/src/test/kotlin/com/metrolist/music/playback/LatestRequestGateTest.kt"
gate_test.parent.mkdir(parents=True, exist_ok=True)
gate_test.write_text(
    '''package com.metrolist.music.playback

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LatestRequestGateTest {
    @Test
    fun `only newest asynchronous queue request remains current`() {
        val gate = LatestRequestGate()
        val slowOldRequest = gate.issue()
        val newerRequest = gate.issue()

        assertFalse(gate.isCurrent(slowOldRequest))
        assertTrue(gate.isCurrent(newerRequest))
    }
}
''',
    encoding="utf-8",
)

music_service = root / "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
replace_once(
    music_service,
    '    private var currentQueue: Queue = EmptyQueue\n'
    '    var queueTitle: String? = null\n',
    '    private var currentQueue: Queue = EmptyQueue\n'
    '    private val explicitQueueRequestGate = LatestRequestGate()\n'
    '    var queueTitle: String? = null\n',
)
replace_once(
    music_service,
    '        currentQueue = queue\n'
    '        queueTitle = null\n',
    '        val queueRequestToken = explicitQueueRequestGate.issue()\n'
    '        currentQueue = queue\n'
    '        queueTitle = null\n',
)
replace_once(
    music_service,
    '            val initialStatus =\n'
    '                withContext(Dispatchers.IO) {\n'
    '                    queue\n'
    '                        .getInitialStatus()\n'
    '                        .filterExplicit(dataStore.get(HideExplicitKey, false))\n'
    '                        .filterVideoSongs(dataStore.get(HideVideoSongsKey, false))\n'
    '                }\n'
    '            if (queue.preloadItem != null && player.playbackState == STATE_IDLE) return@launch\n',
    '            val initialStatus =\n'
    '                withContext(Dispatchers.IO) {\n'
    '                    queue\n'
    '                        .getInitialStatus()\n'
    '                        .filterExplicit(dataStore.get(HideExplicitKey, false))\n'
    '                        .filterVideoSongs(dataStore.get(HideVideoSongsKey, false))\n'
    '                }\n'
    '            if (!explicitQueueRequestGate.isCurrent(queueRequestToken)) {\n'
    '                Timber.tag(TAG).d("Ignoring stale explicit queue request %d", queueRequestToken)\n'
    '                return@launch\n'
    '            }\n'
    '            if (queue.preloadItem != null && player.playbackState == STATE_IDLE) return@launch\n',
)

# ---------------------------------------------------------------------------
# WebRadio UI: refresh before favorite playback, persist fresh search entries,
# restart failed active streams, and merge changed station objects by UUID.
# ---------------------------------------------------------------------------
web_radio = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
replace_once(
    web_radio,
    'import androidx.lifecycle.compose.collectAsStateWithLifecycle\n',
    'import androidx.lifecycle.compose.collectAsStateWithLifecycle\nimport androidx.media3.common.Player\n',
)
replace_once(
    web_radio,
    'import androidx.compose.runtime.mutableStateListOf\n'
    'import androidx.compose.runtime.mutableStateOf\n',
    'import androidx.compose.runtime.mutableLongStateOf\n'
    'import androidx.compose.runtime.mutableStateListOf\n'
    'import androidx.compose.runtime.mutableStateOf\n',
)
replace_once(
    web_radio,
    'import com.metrolist.music.radio.RadioStationLogoResolver\n'
    'import com.metrolist.music.radio.RadioStationStore\n',
    'import com.metrolist.music.radio.RadioStationLogoResolver\n'
    'import com.metrolist.music.radio.RadioStationStore\n'
    'import com.metrolist.music.radio.mergeSavedStationUpdates\n'
    'import com.metrolist.music.radio.replaceFavoriteStation\n',
)
replace_once(
    web_radio,
    'import kotlinx.coroutines.launch\n',
    'import kotlinx.coroutines.Job\nimport kotlinx.coroutines.launch\nimport kotlinx.coroutines.withTimeoutOrNull\n',
)
replace_once(
    web_radio,
    '    val radioIsPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()\n'
    '    val currentRadioMediaId = currentMediaMetadata?.id?.takeIf { it.startsWith("radio:") }\n',
    '    val radioIsPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()\n'
    '    val radioPlaybackState by playerConnection.playbackState.collectAsStateWithLifecycle()\n'
    '    val radioPlaybackError by playerConnection.error.collectAsStateWithLifecycle()\n'
    '    val currentRadioMediaId = currentMediaMetadata?.id?.takeIf { it.startsWith("radio:") }\n',
)
replace_once(
    web_radio,
    '    var deletingStation by remember { mutableStateOf<RadioStation?>(null) }\n'
    '    var showAddDialog by remember { mutableStateOf(false) }\n',
    '    var deletingStation by remember { mutableStateOf<RadioStation?>(null) }\n'
    '    var showAddDialog by remember { mutableStateOf(false) }\n'
    '    var favoritePlayJob by remember { mutableStateOf<Job?>(null) }\n'
    '    var favoriteRequestId by remember { mutableLongStateOf(0L) }\n'
    '    val refreshedFavoriteCache = remember { mutableMapOf<String, Pair<Long, RadioStation>>() }\n',
)
replace_once(
    web_radio,
    '''    LaunchedEffect(savedStations, isDragging) {
        if (!isDragging && !wasDragging && orderedSavedStations.map { it.uuid } != savedStations.map { it.uuid }) {
            orderedSavedStations.clear()
            orderedSavedStations.addAll(savedStations)
        }
    }
''',
    '''    LaunchedEffect(savedStations, isDragging) {
        if (!isDragging && !wasDragging) {
            val merged = mergeSavedStationUpdates(orderedSavedStations, savedStations)
            if (merged != orderedSavedStations) {
                orderedSavedStations.clear()
                orderedSavedStations.addAll(merged)
            }
        }
    }
''',
)
replace_once(
    web_radio,
    '''    fun playSaved(station: RadioStation) {
        val stations = savedStations.ifEmpty { listOf(station) }
        val effectiveStations = if (stations.any { it.uuid == station.uuid }) stations else stations + station
        val startIndex = effectiveStations.indexOfFirst { it.uuid == station.uuid }.coerceAtLeast(0)
        playerConnection.playQueue(
            queue =
                ListQueue(
                    title = "WebRadio",
                    items = effectiveStations.map { it.toMediaItem() },
                    startIndex = startIndex,
                ),
            notifyUserSelection = false,
        )
    }
''',
    '''    fun playSaved(station: RadioStation) {
        favoriteRequestId += 1L
        val requestId = favoriteRequestId
        favoritePlayJob?.cancel()
        favoritePlayJob =
            scope.launch {
                val now = System.currentTimeMillis()
                val cached = refreshedFavoriteCache[station.uuid]?.takeIf { now - it.first < 5 * 60_000L }?.second
                val looksLikeRadioBrowserEntry =
                    station.country.isNotBlank() ||
                        station.language.isNotBlank() ||
                        station.tags.isNotBlank() ||
                        station.codec.isNotBlank() ||
                        station.bitrate > 0
                val refreshed =
                    cached ?: if (looksLikeRadioBrowserEntry) {
                        withTimeoutOrNull(4_500L) {
                            RadioBrowserClient.refreshStation(station).getOrNull()
                        }
                    } else {
                        null
                    }
                if (requestId != favoriteRequestId) return@launch

                val candidate = refreshed ?: station
                val resolvedUrl =
                    withTimeoutOrNull(4_500L) {
                        RadioBrowserClient.resolveStreamUrl(candidate.streamUrl).getOrNull()
                    } ?: candidate.streamUrl
                if (requestId != favoriteRequestId) return@launch

                val playable = candidate.copy(streamUrl = resolvedUrl)
                refreshedFavoriteCache[station.uuid] = now to playable
                if (playable != station) store.addOrUpdate(playable)

                val orderedSnapshot = orderedSavedStations.toList().ifEmpty { savedStations }
                val effectiveStations = replaceFavoriteStation(orderedSnapshot, playable)
                val startIndex = effectiveStations.indexOfFirst { it.uuid == playable.uuid }.coerceAtLeast(0)
                playerConnection.playQueue(
                    queue =
                        ListQueue(
                            title = "WebRadio",
                            items = effectiveStations.map { it.toMediaItem() },
                            startIndex = startIndex,
                        ),
                    notifyUserSelection = false,
                )
            }
    }
''',
)
replace_count(
    web_radio,
    'onPlay = { if (isActive) playerConnection.togglePlayPause() else playSaved(station) },',
    'onPlay = {\n'
    '                                        if (isActive && radioPlaybackState == Player.STATE_READY && radioPlaybackError == null) {\n'
    '                                            playerConnection.togglePlayPause()\n'
    '                                        } else {\n'
    '                                            playSaved(station)\n'
    '                                        }\n'
    '                                    },',
    2,
)
search_old = '''                                    onPlay = {
                                        if (isActive) playerConnection.togglePlayPause() else {
                                            playerConnection.playQueue(
                                                queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                                notifyUserSelection = false,
                                            )
                                        }
                                    },
'''
search_new = '''                                    onPlay = {
                                        if (isActive && radioPlaybackState == Player.STATE_READY && radioPlaybackError == null) {
                                            playerConnection.togglePlayPause()
                                        } else {
                                            if (savedStations.any { it.uuid == station.uuid }) store.addOrUpdate(station)
                                            playerConnection.playQueue(
                                                queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                                notifyUserSelection = false,
                                            )
                                        }
                                    },
'''
replace_count(web_radio, search_old, search_new, 2)

print("Applied WebRadio reliability round 3 patches")
