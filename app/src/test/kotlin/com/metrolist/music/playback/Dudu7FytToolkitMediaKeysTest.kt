package com.metrolist.music.playback

import android.view.KeyEvent
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class Dudu7FytToolkitMediaKeysTest {
    @Test
    fun `media key is recognized directly from FYT update code`() {
        assertEquals(
            KeyEvent.KEYCODE_MEDIA_NEXT,
            extractMediaKeyCode(KeyEvent.KEYCODE_MEDIA_NEXT, null, null),
        )
        assertEquals(
            KeyEvent.KEYCODE_MEDIA_PREVIOUS,
            extractMediaKeyCode(KeyEvent.KEYCODE_MEDIA_PREVIOUS, intArrayOf(1, 2), null),
        )
    }

    @Test
    fun `media key is recognized from FYT integer payload`() {
        assertEquals(
            KeyEvent.KEYCODE_MEDIA_FAST_FORWARD,
            extractMediaKeyCode(12, intArrayOf(4, KeyEvent.KEYCODE_MEDIA_FAST_FORWARD, 0), null),
        )
        assertEquals(
            KeyEvent.KEYCODE_MEDIA_REWIND,
            extractMediaKeyCode(12, intArrayOf(KeyEvent.KEYCODE_MEDIA_REWIND), null),
        )
    }

    @Test
    fun `media key is recognized from diagnostic string payload`() {
        assertEquals(
            KeyEvent.KEYCODE_MEDIA_PREVIOUS,
            extractMediaKeyCode(7, null, arrayOf("keyCode=88 action=down")),
        )
    }

    @Test
    fun `unrelated FYT module values are ignored`() {
        assertNull(extractMediaKeyCode(23, intArrayOf(8750, 1, 0), arrayOf("frequency=87.5")))
        assertNull(extractMediaKeyCode(119, intArrayOf(42), arrayOf("station")))
    }

    @Test
    fun `restored queue UI state retains every item and safe index`() {
        val snapshot =
            Dudu7QueueSnapshot(
                title = "YT queue",
                items =
                    listOf(
                        MediaItem.Builder().setMediaId("song-1").build(),
                        MediaItem.Builder().setMediaId("song-2").build(),
                        MediaItem.Builder().setMediaId("song-3").build(),
                    ),
                currentIndex = 9,
                currentPositionMs = 12_000L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_ALL,
                shuffleModeEnabled = false,
            )

        assertEquals(
            Dudu7QueueUiState(
                title = "YT queue",
                mediaIds = listOf("song-1", "song-2", "song-3"),
                currentIndex = 2,
            ),
            snapshot.queueUiState(),
        )
    }
}
