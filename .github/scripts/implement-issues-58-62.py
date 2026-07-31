from pathlib import Path


def replace_exact(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, got {count}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_exact(
    "app/build.gradle.kts",
    '        versionCode = 1370043\n        versionName = "13.7.34"',
    '        versionCode = 1370044\n        versionName = "13.7.35"',
)

Path("app/src/main/kotlin/com/metrolist/music/radio/WebRadioFavouriteQueue.kt").write_text(
    '''package com.metrolist.music.radio

fun orderWebRadioFavourites(
    selected: RadioStation,
    savedStations: List<RadioStation>,
): List<RadioStation> {
    val ordered = savedStations.distinctBy { it.uuid }.toMutableList()
    val selectedIndex = ordered.indexOfFirst { it.uuid == selected.uuid }
    if (selectedIndex >= 0) {
        ordered[selectedIndex] = selected
    } else {
        ordered += selected
    }
    return ordered
}

fun webRadioFavouriteStartIndex(
    selected: RadioStation,
    orderedStations: List<RadioStation>,
): Int = orderedStations.indexOfFirst { it.uuid == selected.uuid }.coerceAtLeast(0)
''',
    encoding="utf-8",
)

replace_exact(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    '''                    ListQueue(
                        title = "WebRadio",
                        items = queueStations.map { it.toMediaItem() },
                        startIndex = 0,
                    ),''',
    '''                    ListQueue(
                        title = "WebRadio",
                        items = queueStations.map { it.toMediaItem() },
                        startIndex = webRadioFavouriteStartIndex(playable, queueStations),
                    ),''',
)
replace_exact(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "import com.metrolist.music.radio.orderWebRadioFavourites\n",
    "import com.metrolist.music.radio.orderWebRadioFavourites\nimport com.metrolist.music.radio.webRadioFavouriteStartIndex\n",
)

replace_exact(
    "app/src/main/kotlin/com/metrolist/music/playback/MediaLibrarySessionCallback.kt",
    '''        if (!PhysicalFmSessionBridge.owns(session.player) &&
            PhysicalFmMediaKeyBridge.handleMediaButton(intent)
        ) {
            MediaKeyDiagnostics.record(context, "SESSION_ROUTE", "fallback -> direct FM favourite; consumed=true")
            return true
        }''',
    '''        if (PhysicalFmSessionBridge.owns(session.player) &&
            PhysicalFmMediaKeyBridge.handleMediaButton(intent)
        ) {
            MediaKeyDiagnostics.record(context, "SESSION_ROUTE", "hardware -> direct FM favourite; consumed=true")
            return true
        }''',
)

replace_exact(
    "app/src/main/kotlin/com/metrolist/music/playback/MediaLibrarySessionCallback.kt",
    '''        val direction =
            when (playerCommand) {
                Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM -> true
                Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM -> false
                else -> null
            }
        if (direction != null &&
            !PhysicalFmSessionBridge.owns(session.player) &&
            PhysicalFmMediaKeyBridge.handleDirection(direction)
        ) {
            MediaKeyDiagnostics.record(context, "PLAYER_COMMAND_ROUTE", "fallback -> direct FM favourite")
            return SessionResult.RESULT_SUCCESS
        }
        return super.onPlayerCommandRequest(session, controllerInfo, playerCommand)''',
    '''        return super.onPlayerCommandRequest(session, controllerInfo, playerCommand)''',
)

Path("app/src/test/kotlin/com/metrolist/music/radio/WebRadioFavouriteQueueTest.kt").write_text(
    '''package com.metrolist.music.radio

import org.junit.Assert.assertEquals
import org.junit.Test

class WebRadioFavouriteQueueTest {
    private fun station(id: String, url: String = "https://example.invalid/$id") =
        RadioStation(uuid = id, name = id, streamUrl = url)

    @Test
    fun `selected station keeps its saved position`() {
        val one = station("one")
        val two = station("two")
        val three = station("three")
        val result = orderWebRadioFavourites(two, listOf(one, two, three))

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals(1, webRadioFavouriteStartIndex(two, result))
    }

    @Test
    fun `refreshed selected station replaces stale object at the same position`() {
        val stale = station("two", "https://old.invalid")
        val refreshed = station("two", "https://new.invalid")
        val result = orderWebRadioFavourites(
            refreshed,
            listOf(station("one"), stale, stale, station("three")),
        )

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals("https://new.invalid", result[1].streamUrl)
        assertEquals(1, webRadioFavouriteStartIndex(refreshed, result))
    }

    @Test
    fun `unsaved selected station is appended deterministically`() {
        val selected = station("three")
        val result = orderWebRadioFavourites(selected, listOf(station("one"), station("two")))

        assertEquals(listOf("one", "two", "three"), result.map { it.uuid })
        assertEquals(2, webRadioFavouriteStartIndex(selected, result))
    }
}
''',
    encoding="utf-8",
)
