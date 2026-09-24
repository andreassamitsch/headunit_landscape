package com.metrolist.music.ui.screens

import com.metrolist.innertube.models.SongItem
import com.metrolist.innertube.models.WatchEndpoint
import com.metrolist.music.extensions.toMediaItem
import com.metrolist.music.models.toMediaMetadata
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.playback.queues.Queue
import com.metrolist.music.playback.queues.YouTubeQueue

/**
 * Builds the exact same queue shape used by normal online search when a user explicitly
 * chooses a song. Keeping this small helper shared by BrowseScreen makes Home/genre playback
 * testable without duplicating Dudu7-specific queue logic.
 */
internal fun createBrowseSongQueue(
    item: SongItem,
    autoRadioQueue: Boolean,
): Queue =
    if (autoRadioQueue) {
        YouTubeQueue(
            WatchEndpoint(videoId = item.id),
            item.toMediaMetadata(),
        )
    } else {
        ListQueue(
            title = item.title,
            items = listOf(item.toMediaItem()),
        )
    }
