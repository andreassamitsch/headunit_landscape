/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.matchParentSize
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.navigation.NavController
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.innertube.models.ArtistItem
import com.metrolist.innertube.models.PlaylistItem
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.BuildConfig
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.constants.AutoRadioQueueKey
import com.metrolist.music.constants.GridItemSize
import com.metrolist.music.constants.GridItemsSizeKey
import com.metrolist.music.constants.GridThumbnailHeight
import com.metrolist.music.ui.component.IconButton
import com.metrolist.music.ui.component.LocalMenuState
import com.metrolist.music.ui.component.YouTubeGridItem
import com.metrolist.music.ui.component.shimmer.GridItemPlaceHolder
import com.metrolist.music.ui.component.shimmer.ShimmerHost
import com.metrolist.music.ui.menu.YouTubeAlbumMenu
import com.metrolist.music.ui.menu.YouTubeArtistMenu
import com.metrolist.music.ui.menu.YouTubePlaylistMenu
import com.metrolist.music.ui.utils.backToMain
import com.metrolist.music.utils.rememberEnumPreference
import com.metrolist.music.utils.rememberPreference
import com.metrolist.music.viewmodels.BrowseViewModel

@OptIn(ExperimentalFoundationApi::class, ExperimentalMaterial3Api::class)
@Composable
fun BrowseScreen(
    navController: NavController,
    browseId: String?,
    viewModel: BrowseViewModel = hiltViewModel(),
) {
    val menuState = LocalMenuState.current
    val playerConnection = LocalPlayerConnection.current ?: return
    val isPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()

    val title by viewModel.title.collectAsStateWithLifecycle()
    val items by viewModel.items.collectAsStateWithLifecycle()

    val coroutineScope = rememberCoroutineScope()
    val gridItemSize by rememberEnumPreference(GridItemsSizeKey, GridItemSize.BIG)
    val autoRadioQueue by rememberPreference(AutoRadioQueueKey, defaultValue = true)

    val playBrowseSong: (SongItem) -> Unit = { songItem ->
        if (songItem.id == mediaMetadata?.id) {
            playerConnection.togglePlayPause()
        } else {
            playerConnection.playQueue(
                createBrowseSongQueue(
                    item = songItem,
                    autoRadioQueue = autoRadioQueue,
                ),
            )
        }
    }

    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = GridThumbnailHeight + if (gridItemSize == GridItemSize.BIG) 24.dp else (-24).dp),
        contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
    ) {
        items?.let { items ->
            items(
                items = items.distinctBy { it.id },
                key = { "browse_${it.id}" },
            ) { item ->
                val onItemClick: () -> Unit = {
                    when (item) {
                        is SongItem -> playBrowseSong(item)

                        is AlbumItem -> {
                            navController.navigate("album/${item.id}")
                        }

                        is PlaylistItem -> {
                            navController.navigate("online_playlist/${item.id}")
                        }

                        is ArtistItem -> {
                            navController.navigate("artist/${item.id}")
                        }

                        else -> {
                            // Do nothing for unsupported browse item types.
                        }
                    }
                }

                val onItemLongClick: () -> Unit = {
                    menuState.show {
                        when (item) {
                            is AlbumItem -> {
                                YouTubeAlbumMenu(
                                    albumItem = item,
                                    onDismiss = menuState::dismiss,
                                )
                            }

                            is PlaylistItem -> {
                                YouTubePlaylistMenu(
                                    playlist = item,
                                    coroutineScope = coroutineScope,
                                    onDismiss = menuState::dismiss,
                                )
                            }

                            is ArtistItem -> {
                                YouTubeArtistMenu(
                                    artist = item,
                                    onDismiss = menuState::dismiss,
                                )
                            }

                            else -> {
                                // Do nothing
                            }
                        }
                    }
                }

                Box {
                    YouTubeGridItem(
                        item = item,
                        isPlaying = isPlaying,
                        fillMaxWidth = true,
                        coroutineScope = coroutineScope,
                        onPlayClick =
                            (item as? SongItem)?.let { songItem ->
                                { playBrowseSong(songItem) }
                            },
                        modifier =
                            Modifier
                                .combinedClickable(
                                    onClick = onItemClick,
                                    onLongClick = onItemLongClick,
                                ),
                    )

                    // On the Dudu7 embedded player pane PlaylistItem activation works via
                    // keyboard/D-pad semantics, while the regular GridItem pointer path can
                    // lose taps. Keep the original combinedClickable for semantics/focus and
                    // add only a pointer-layer for playlists so touch invokes exactly the same
                    // navigation/menu actions. Standard MetroList never receives this layer.
                    if (BuildConfig.IS_DUDU7 && item is PlaylistItem) {
                        Box(
                            modifier =
                                Modifier
                                    .matchParentSize()
                                    .pointerInput(item.id) {
                                        detectTapGestures(
                                            onTap = { onItemClick() },
                                            onLongPress = { onItemLongClick() },
                                        )
                                    },
                        ) {}
                    }
                }
            }

            if (items.isEmpty()) {
                items(8) {
                    ShimmerHost {
                        GridItemPlaceHolder(fillMaxWidth = true)
                    }
                }
            }
        }
    }

    TopAppBar(
        title = { Text(title ?: "") },
        navigationIcon = {
            IconButton(
                onClick = navController::navigateUp,
                onLongClick = navController::backToMain,
            ) {
                Icon(
                    painterResource(R.drawable.arrow_back),
                    contentDescription = null,
                )
            }
        },
    )
}
