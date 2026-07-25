#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected block missing in {path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[1]

queue = root / "app/src/main/kotlin/com/metrolist/music/radio/RadioFavoriteQueue.kt"
queue_text = queue.read_text(encoding="utf-8")
helper = """

/** Return the adjacent saved station without handing the full list to ExoPlayer. */
internal fun radioFavoriteNeighbor(
    ordered: List<RadioStation>,
    currentMediaId: String?,
    direction: Int,
): RadioStation? {
    if (direction != -1 && direction != 1) return null
    val currentIndex = ordered.indexOfFirst { it.mediaId == currentMediaId }
    if (currentIndex < 0) return null
    return ordered.getOrNull(currentIndex + direction)
}
"""
if "internal fun radioFavoriteNeighbor(" not in queue_text:
    queue.write_text(queue_text.rstrip() + helper, encoding="utf-8")

web = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt"
web_text = web.read_text(encoding="utf-8")
web_text = web_text.replace("import com.metrolist.music.radio.replaceFavoriteStation\n", "")
web.write_text(web_text, encoding="utf-8")
replace_once(
    web,
    '''        fun startFavorite(playable: RadioStation) {
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
''',
    '''        fun startFavorite(playable: RadioStation) {
            playerConnection.playQueue(
                queue =
                    ListQueue(
                        title = playable.name,
                        items = listOf(playable.toMediaItem()),
                    ),
                notifyUserSelection = false,
            )
        }
''',
)

player = root / "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt"
replace_once(
    player,
    "import com.metrolist.music.playback.queues.Queue\n",
    "import com.metrolist.music.playback.queues.ListQueue\nimport com.metrolist.music.playback.queues.Queue\n",
)
replace_once(
    player,
    "import com.metrolist.music.radio.isRadioMediaId\n",
    "import com.metrolist.music.radio.RadioStationStore\nimport com.metrolist.music.radio.isRadioMediaId\nimport com.metrolist.music.radio.radioFavoriteNeighbor\n",
)
replace_once(
    player,
    '''    val service = binder.service
    private val playerReadinessFlow = service.isPlayerReady
''',
    '''    val service = binder.service
    private val radioStationStore = RadioStationStore.get(context.applicationContext)
    private val playerReadinessFlow = service.isPlayerReady
''',
)
replace_once(
    player,
    '''        scope.launch {
            playerReadinessFlow.collect { ready ->
                isPlayerInitialized.value = ready
                if (ready) {
                    Timber.tag(TAG).d("Service player initialization detected by PlayerConnection")
                }
            }
        }

        Timber.tag(TAG).d("PlayerConnection state flows initialized successfully")
''',
    '''        scope.launch {
            playerReadinessFlow.collect { ready ->
                isPlayerInitialized.value = ready
                if (ready) {
                    Timber.tag(TAG).d("Service player initialization detected by PlayerConnection")
                }
            }
        }
        scope.launch {
            radioStationStore.stations.collect {
                if (isRadioMediaId(getPlayerOrNull()?.currentMediaItem?.mediaId)) {
                    updateCanSkipPreviousAndNext()
                }
            }
        }

        Timber.tag(TAG).d("PlayerConnection state flows initialized successfully")
''',
)
replace_once(
    player,
    '''    fun seekToNext() {
        try {
            // When casting, use Cast skip instead of local player
''',
    '''    private fun playAdjacentRadioFavorite(direction: Int): Boolean {
        val activePlayer = getPlayerOrNull() ?: return false
        val currentMediaId = activePlayer.currentMediaItem?.mediaId
        if (!isRadioMediaId(currentMediaId)) return false
        val target =
            radioFavoriteNeighbor(
                ordered = radioStationStore.stations.value,
                currentMediaId = currentMediaId,
                direction = direction,
            ) ?: return false
        playQueue(
            queue = ListQueue(title = target.name, items = listOf(target.toMediaItem())),
            notifyUserSelection = false,
        )
        return true
    }

    fun seekToNext() {
        try {
            // When casting, use Cast skip instead of local player
''',
)
replace_once(
    player,
    '''            player.seekToNext()
            if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
''',
    '''            if (isRadioMediaId(player.currentMediaItem?.mediaId)) {
                if (playAdjacentRadioFavorite(1)) onSkipNext?.invoke()
                return
            }
            player.seekToNext()
            if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
''',
)
replace_once(
    player,
    '''            // A live radio stream has no meaningful "restart current item" position.
            // Previous must always select the previous saved station.
            if (isRadioMediaId(player.currentMediaItem?.mediaId) && player.hasPreviousMediaItem()) {
                player.seekToPreviousMediaItem()
                if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
                    player.prepare()
                }
                player.playWhenReady = true
                onSkipPrevious?.invoke()
                return
            }

            // Logic to mimic standard seekToPrevious behavior but with explicit callbacks
''',
    '''            // A live radio stream has no seek position. Resolve the previous
            // saved favorite ourselves and keep ExoPlayer on a single stream.
            if (isRadioMediaId(player.currentMediaItem?.mediaId)) {
                if (playAdjacentRadioFavorite(-1)) onSkipPrevious?.invoke()
                return
            }

            // Logic to mimic standard seekToPrevious behavior but with explicit callbacks
''',
)
replace_once(
    player,
    '''    private fun updateCanSkipPreviousAndNext() {
        if (!player.currentTimeline.isEmpty) {
''',
    '''    private fun updateCanSkipPreviousAndNext() {
        val currentMediaId = player.currentMediaItem?.mediaId
        if (isRadioMediaId(currentMediaId)) {
            val favorites = radioStationStore.stations.value
            canSkipPrevious.value = radioFavoriteNeighbor(favorites, currentMediaId, -1) != null
            canSkipNext.value = radioFavoriteNeighbor(favorites, currentMediaId, 1) != null
            return
        }
        if (!player.currentTimeline.isEmpty) {
''',
)

gradle = root / "app/build.gradle.kts"
replace_once(
    gradle,
    '        versionCode = 160\n        versionName = "13.7.1"\n',
    '        versionCode = 161\n        versionName = "13.7.2"\n',
)

test = root / "app/src/test/kotlin/com/metrolist/music/radio/RadioFavoriteNavigationTest.kt"
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text(
    '''package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RadioFavoriteNavigationTest {
    private val stations =
        listOf(
            RadioStation("broken-before", "Broken Before", "http://invalid/before"),
            RadioStation("one", "Favorite One", "http://valid/one"),
            RadioStation("two", "Favorite Two", "http://valid/two"),
            RadioStation("broken-after", "Broken After", "http://invalid/after"),
        )

    @Test
    fun nextAndPreviousUsePersistedOrder() {
        assertEquals("two", radioFavoriteNeighbor(stations, stations[1].mediaId, 1)?.uuid)
        assertEquals("one", radioFavoriteNeighbor(stations, stations[2].mediaId, -1)?.uuid)
    }

    @Test
    fun navigationStopsAtOrderEdges() {
        assertNull(radioFavoriteNeighbor(stations, stations.first().mediaId, -1))
        assertNull(radioFavoriteNeighbor(stations, stations.last().mediaId, 1))
    }

    @Test
    fun unknownOrInvalidDirectionDoesNothing() {
        assertNull(radioFavoriteNeighbor(stations, "radio:missing", 1))
        assertNull(radioFavoriteNeighbor(stations, stations[1].mediaId, 0))
    }
}
''',
    encoding="utf-8",
)

print("Applied single-stream WebRadio favorite navigation")
