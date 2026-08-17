package com.metrolist.music.ui.screens

import com.metrolist.innertube.models.Artist
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.playback.queues.YouTubeQueue
import org.junit.Assert.assertTrue
import org.junit.Test

class BrowsePlaybackTest {
    private val song =
        SongItem(
            id = "genre-song-id",
            title = "Genre Song",
            artists = listOf(Artist(name = "Artist", id = "artist-id")),
            thumbnail = "https://example.invalid/cover.jpg",
        )

    @Test
    fun `browse song uses YouTube radio queue when auto radio is enabled`() {
        assertTrue(createBrowseSongQueue(song, autoRadioQueue = true) is YouTubeQueue)
    }

    @Test
    fun `browse song uses single item queue when auto radio is disabled`() {
        assertTrue(createBrowseSongQueue(song, autoRadioQueue = false) is ListQueue)
    }
}
