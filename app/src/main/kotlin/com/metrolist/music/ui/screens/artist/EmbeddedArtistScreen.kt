package com.metrolist.music.ui.screens.artist

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import coil3.compose.AsyncImage
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.innertube.models.ArtistItem
import com.metrolist.innertube.models.EpisodeItem
import com.metrolist.innertube.models.PlaylistItem
import com.metrolist.innertube.models.PodcastItem
import com.metrolist.innertube.models.SongItem
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.YTItem
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.extensions.toMediaItem
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.playback.queues.YouTubeQueue
import com.metrolist.music.viewmodels.ArtistViewModel
import kotlinx.coroutines.launch

/**
 * Touch-safe artist page for the vehicle player's embedded right pane.
 *
 * The normal ArtistScreen has several overlapping, animated layers which are
 * useful in the phone UI but can intercept taps when it is hosted inside the
 * player's nested NavHost. This deliberately flat layout keeps every visible
 * control in the same input hierarchy while retaining the important YouTube
 * Music actions and navigation.
 */
@Composable
fun EmbeddedArtistScreen(
    navController: NavController,
    viewModel: ArtistViewModel = hiltViewModel(),
) {
    val playerConnection = LocalPlayerConnection.current ?: return
    val coroutineScope = rememberCoroutineScope()
    val page = viewModel.artistPage
    val mediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()
    val isPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()

    Column(modifier = Modifier.fillMaxSize()) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(64.dp)
                    .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier =
                    Modifier
                        .size(44.dp)
                        .clip(RoundedCornerShape(22.dp))
                        .clickable { navController.navigateUp() },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painter = painterResource(R.drawable.arrow_back),
                    contentDescription = "Zurück",
                    modifier = Modifier.size(24.dp),
                )
            }
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = page?.artist?.title.orEmpty(),
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        if (page == null) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                Text(text = "Künstler wird geladen …")
            }
            return@Column
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 28.dp),
        ) {
            item(key = "embedded_artist_header") {
                page.artist.thumbnail?.let { thumbnail ->
                    AsyncImage(
                        model = thumbnail,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .height(220.dp),
                    )
                }

                Column(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 18.dp, vertical = 14.dp),
                ) {
                    Text(
                        text = page.artist.title,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )

                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        page.artist.radioEndpoint?.let { endpoint ->
                            EmbeddedArtistAction(
                                icon = R.drawable.radio,
                                label = "Radio",
                                onClick = {
                                    playerConnection.notifyUserSongSelection()
                                    playerConnection.playQueue(
                                        YouTubeQueue(endpoint),
                                        notifyUserSelection = false,
                                    )
                                },
                            )
                        }
                        page.artist.shuffleEndpoint?.let { endpoint ->
                            EmbeddedArtistAction(
                                icon = R.drawable.shuffle,
                                label = "Shuffle",
                                onClick = {
                                    playerConnection.notifyUserSongSelection()
                                    playerConnection.playQueue(
                                        YouTubeQueue(endpoint),
                                        notifyUserSelection = false,
                                    )
                                },
                            )
                        }
                    }

                    page.subscriberCountText?.takeIf { it.isNotBlank() }?.let {
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    page.description?.takeIf { it.isNotBlank() }?.let {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 4,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }

            page.sections.forEachIndexed { sectionIndex, section ->
                item(key = "embedded_section_${sectionIndex}_title") {
                    Text(
                        text = section.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .then(
                                    section.moreEndpoint?.let { endpoint ->
                                        Modifier.clickable {
                                            navController.navigate(
                                                "artist/${viewModel.artistId}/items?browseId=${endpoint.browseId}?params=${endpoint.params}",
                                            )
                                        }
                                    } ?: Modifier,
                                )
                                .padding(start = 18.dp, top = 18.dp, end = 18.dp, bottom = 8.dp),
                    )
                }

                val songs = section.items.filterIsInstance<SongItem>()
                itemsIndexed(section.items) { _, item ->
                    EmbeddedArtistItemRow(
                        item = item,
                        active = mediaMetadata?.id == item.id,
                        playing = isPlaying,
                        onClick = {
                            when (item) {
                                is SongItem -> {
                                    coroutineScope.launch {
                                        val complete = section.moreEndpoint?.let { endpoint ->
                                            val first = YouTube.artistItems(endpoint).getOrNull()
                                            if (first == null) emptyList() else {
                                                val all = first.items.toMutableList()
                                                var continuation = first.continuation
                                                while (continuation != null) {
                                                    val next = YouTube.artistItemsContinuation(continuation).getOrNull() ?: break
                                                    all += next.items
                                                    continuation = next.continuation
                                                }
                                                all.filterIsInstance<SongItem>().distinctBy { it.id }
                                            }
                                        }.orEmpty().ifEmpty { songs }
                                        val startIndex = complete.indexOfFirst { it.id == item.id }.coerceAtLeast(0)
                                        playerConnection.notifyUserSongSelection()
                                        playerConnection.playQueue(
                                            ListQueue(
                                                title = section.title.ifBlank { page.artist.title },
                                                items = complete.map { it.toMediaItem() },
                                                startIndex = startIndex,
                                            ),
                                            notifyUserSelection = false,
                                        )
                                    }
                                }

                                is EpisodeItem -> {
                                    playerConnection.notifyUserSongSelection()
                                    playerConnection.playQueue(
                                        ListQueue(
                                            title = section.title.ifBlank { page.artist.title },
                                            items = listOf(item.asSongItem().toMediaItem()),
                                        ),
                                        notifyUserSelection = false,
                                    )
                                }

                                is AlbumItem -> navController.navigate("album/${item.browseId}")
                                is ArtistItem -> navController.navigate("artist/${item.id}")
                                is PlaylistItem -> navController.navigate("online_playlist/${item.id}")
                                is PodcastItem -> navController.navigate("online_podcast/${item.id}")
                            }
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun EmbeddedArtistAction(
    icon: Int,
    label: String,
    onClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .clip(RoundedCornerShape(22.dp))
                .background(MaterialTheme.colorScheme.secondaryContainer)
                .clickable(onClick = onClick)
                .padding(horizontal = 16.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = null,
            modifier = Modifier.size(20.dp),
        )
        Spacer(modifier = Modifier.width(8.dp))
        Text(text = label, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun EmbeddedArtistItemRow(
    item: YTItem,
    active: Boolean,
    playing: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier =
            Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .padding(horizontal = 18.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        item.thumbnail?.let { thumbnail ->
            AsyncImage(
                model = thumbnail,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier =
                    Modifier
                        .size(58.dp)
                        .clip(RoundedCornerShape(8.dp)),
            )
            Spacer(modifier = Modifier.width(12.dp))
        }

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = item.title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            item.embeddedSubtitle()?.takeIf { it.isNotBlank() }?.let { subtitle ->
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        if (active) {
            Text(
                text = if (playing) "▶" else "Ⅱ",
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(start = 10.dp),
            )
        }
    }
}

private fun YTItem.embeddedSubtitle(): String? =
    when (this) {
        is SongItem -> artists.joinToString { it.name }
        is AlbumItem -> listOfNotNull(artists?.joinToString { it.name }, year?.toString()).joinToString(" • ")
        is ArtistItem -> "Künstler"
        is PlaylistItem -> author?.name ?: songCountText
        is PodcastItem -> author?.name ?: episodeCountText
        is EpisodeItem -> author?.name ?: publishDateText
    }
