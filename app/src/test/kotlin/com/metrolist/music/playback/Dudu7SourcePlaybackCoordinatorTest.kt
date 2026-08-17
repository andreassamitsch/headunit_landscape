package com.metrolist.music.playback

import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7SourcePlaybackCoordinatorTest {
    private fun item(mediaId: String): MediaItem =
        MediaItem.Builder()
            .setMediaId(mediaId)
            .build()

    @Test
    fun `YT and WebRadio queues are retained independently`() {
        val memory = Dudu7SourcePlaybackMemory()
        val yt =
            Dudu7QueueSnapshot(
                title = "YT queue",
                items = listOf(item("song-1"), item("song-2"), item("song-3")),
                currentIndex = 1,
                currentPositionMs = 42_500L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_ALL,
                shuffleModeEnabled = true,
            )
        val web =
            Dudu7QueueSnapshot(
                title = "WebRadio",
                items = listOf(item("radio:a"), item("radio:b"), item("radio:c")),
                currentIndex = 2,
                currentPositionMs = 0L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_OFF,
                shuffleModeEnabled = false,
            )

        assertTrue(memory.save(Dudu7PlaybackSource.YT_MUSIC, yt))
        assertTrue(memory.save(Dudu7PlaybackSource.WEBRADIO, web))

        assertEquals(listOf("song-1", "song-2", "song-3"), memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.items?.map { it.mediaId })
        assertEquals(1, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.safeIndex)
        assertEquals(42_500L, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.currentPositionMs)
        assertEquals(Player.REPEAT_MODE_ALL, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.repeatMode)
        assertEquals(true, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.shuffleModeEnabled)

        assertEquals(listOf("radio:a", "radio:b", "radio:c"), memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.items?.map { it.mediaId })
        assertEquals(2, memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.safeIndex)
        assertEquals("radio:c", memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.currentMediaId)
    }

    @Test
    fun `queue snapshot cannot overwrite a different source`() {
        val memory = Dudu7SourcePlaybackMemory()
        val web =
            Dudu7QueueSnapshot(
                title = "WebRadio",
                items = listOf(item("radio:a")),
                currentIndex = 0,
                currentPositionMs = 0L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_OFF,
                shuffleModeEnabled = false,
            )

        assertFalse(memory.save(Dudu7PlaybackSource.YT_MUSIC, web))
        assertNull(memory.snapshot(Dudu7PlaybackSource.YT_MUSIC))
        assertTrue(memory.save(Dudu7PlaybackSource.WEBRADIO, web))
    }

    @Test
    fun `out of range queue index is safely clamped`() {
        val snapshot =
            Dudu7QueueSnapshot(
                title = null,
                items = listOf(item("song-1"), item("song-2")),
                currentIndex = 99,
                currentPositionMs = 1_000L,
                playWhenReady = false,
                repeatMode = Player.REPEAT_MODE_ONE,
                shuffleModeEnabled = false,
            )

        assertEquals(1, snapshot.safeIndex)
        assertEquals("song-2", snapshot.currentMediaId)
    }

    @Test
    fun `explicit YT selection is consumed exactly once`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection(requiresRestoreBypass = true)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertTrue(memory.consumeUserYtSelection())
        assertFalse(memory.consumeUserYtSelection())
    }

    @Test
    fun `explicit YT selection while YT is already active bypasses stale queue restore once`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection(requiresRestoreBypass = true)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertTrue(memory.consumeUserYtSelection())
        assertFalse(memory.consumeUserYtSelection())
    }
}
