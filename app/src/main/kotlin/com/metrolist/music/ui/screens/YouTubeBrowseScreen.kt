/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.focusable
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.KeyEventType
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.input.key.type
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.innertube.models.ArtistItem
import com.metrolist.innertube.models.EpisodeItem
import com.metrolist.innertube.models.PlaylistItem
import com.metrolist.innertube.models.PodcastItem
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.constants.GridItemSize
import com.metrolist.music.constants.GridItemsSizeKey
import com.metrolist.music.constants.GridThumbnailHeight
import com.metrolist.music.models.toMediaMetadata
import com.metrolist.music.playback.queues.YouTubeQueue
import com.metrolist.music.ui.component.IconButton
import com.metrolist.music.ui.component.LocalMenuState
import com.metrolist.music.ui.component.LocalRightPaneScrollBridge
import com.metrolist.music.ui.component.YouTubeGridItem
import com.metrolist.music.ui.component.shimmer.GridItemPlaceHolder
import com.metrolist.music.ui.component.shimmer.ShimmerHost
import com.metrolist.music.ui.menu.YouTubeAlbumMenu
import com.metrolist.music.ui.menu.YouTubeArtistMenu
import com.metrolist.music.ui.menu.YouTubePlaylistMenu
import com.metrolist.music.ui.menu.YouTubeSongMenu
import com.metrolist.music.ui.utils.backToMain
import com.metrolist.music.utils.rememberEnumPreference
import com.metrolist.music.viewmodels.YouTubeBrowseViewModel
import timber.log.Timber

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun YouTubeBrowseScreen(
    navController: NavController,
    viewModel: YouTubeBrowseViewModel = hiltViewModel(),
) {
    val menuState = LocalMenuState.current
    val haptic = LocalHapticFeedback.current
    val playerConnection = LocalPlayerConnection.current ?: return
    val isPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()
    val browseResult by viewModel.result.collectAsStateWithLifecycle()
    val coroutineScope = rememberCoroutineScope()
    val gridItemSize by rememberEnumPreference(GridItemsSizeKey, GridItemSize.BIG)
    val allItems = browseResult?.items?.flatMap { it.items } ?: emptyList()

    val lazyGridState = rememberLazyGridState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }

    DisposableEffect(rightPaneScrollBridge, lazyGridState) {
        if (rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = { delta -> lazyGridState.dispatchRawDelta(delta) },
                tapHandler = { positionInRoot ->
                    val target = rightPaneTapTargets.values.lastOrNull { (bounds, _) -> bounds.contains(positionInRoot) }
                    if (target != null) {
                        Timber.tag("Dudu7BrowseTap").i(
                            "Bridged BrowseScreen tap x=%.1f y=%.1f browseId=%s",
                            positionInRoot.x,
                            positionInRoot.y,
                            "youtube_browse",
                        )
                        target.second.invoke()
                        true
                    } else {
                        false
                    }
                },
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
            rightPaneTapTargets.clear()
        }
    }

    LazyVerticalGrid(
        columns = GridCells.Adaptive(
            minSize = GridThumbnailHeight + if (gridItemSize == GridItemSize.BIG) 24.dp else (-24).dp,
        ),
        state = lazyGridState,
        contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
        userScrollEnabled = rightPaneScrollBridge == null,
    ) {
        if (browseResult == null) {
            items(8) {
                ShimmerHost { GridItemPlaceHolder(fillMaxWidth = true) }
            }
        }

        items(
            items = allItems.distinctBy { it.id },
            key = { "yt_browse_${it.id}" },
        ) { item ->
            val onItemClick: () -> Unit = {
                when (item) {
                    is SongItem -> {
                        if (item.id == mediaMetadata?.id) {
                            playerConnection.togglePlayPause()
                        } else {
                            playerConnection.playQueue(YouTubeQueue.radio(item.toMediaMetadata()))
                        }
                    }

                    is AlbumItem -> navController.navigate("album/${item.id}")
                    is ArtistItem -> navController.navigate("artist/${item.id}")
                    is PlaylistItem -> {
                        navController.navigate("online_playlist/${item.id}")
                        Timber.tag("Dudu7BrowseNavigate").i(
                            "completed type=playlist id=%s currentRoute=%s title=%s",
                            item.id,
                            navController.currentDestination?.route,
                            item.title,
                        )
                    }

                    is PodcastItem -> navController.navigate("online_podcast/${item.id}")
                    is EpisodeItem -> {
                        if (item.id == mediaMetadata?.id) {
                            playerConnection.togglePlayPause()
                        } else {
                            playerConnection.playQueue(YouTubeQueue.radio(item.toMediaMetadata()))
                        }
                    }
                }
            }

            val onItemLongClick: () -> Unit = {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                menuState.show {
                    when (item) {
                        is SongItem -> YouTubeSongMenu(song = item, onDismiss = menuState::dismiss)
                        is AlbumItem -> YouTubeAlbumMenu(albumItem = item, onDismiss = menuState::dismiss)
                        is ArtistItem -> YouTubeArtistMenu(artist = item, onDismiss = menuState::dismiss)
                        is PlaylistItem -> YouTubePlaylistMenu(
                            playlist = item,
                            coroutineScope = coroutineScope,
                            onDismiss = menuState::dismiss,
                        )
                        is PodcastItem -> YouTubePlaylistMenu(
                            playlist = item.asPlaylistItem(),
                            coroutineScope = coroutineScope,
                            onDismiss = menuState::dismiss,
                        )
                        is EpisodeItem -> YouTubeSongMenu(song = item.asSongItem(), onDismiss = menuState::dismiss)
                    }
                }
            }

            val rightPaneTapKey = "youtube_browse_item_${item.id}"
            val bridgeSupportsItem =
                item is SongItem || item is AlbumItem || item is ArtistItem || item is PlaylistItem ||
                    item is PodcastItem || item is EpisodeItem
            val parentOwnsPlaylistPointer = rightPaneScrollBridge != null && item is PlaylistItem

            DisposableEffect(rightPaneTapKey, rightPaneScrollBridge) {
                onDispose { rightPaneTapTargets.remove(rightPaneTapKey) }
            }

            val interactionModifier =
                if (parentOwnsPlaylistPointer) {
                    Modifier
                        .focusable()
                        .onKeyEvent { event ->
                            val activate =
                                event.type == KeyEventType.KeyUp &&
                                    event.key in setOf(
                                        Key.DirectionCenter,
                                        Key.Enter,
                                        Key.NumPadEnter,
                                        Key.Spacebar,
                                    )
                            if (activate) {
                                onItemClick()
                                true
                            } else {
                                false
                            }
                        }
                        .semantics {
                            onClick {
                                onItemClick()
                                true
                            }
                        }
                } else {
                    Modifier.combinedClickable(
                        onClick = onItemClick,
                        onLongClick = onItemLongClick,
                    )
                }

            YouTubeGridItem(
                item = item,
                isActive = when (item) {
                    is SongItem -> mediaMetadata?.id == item.id
                    is AlbumItem -> mediaMetadata?.album?.id == item.id
                    else -> false
                },
                isPlaying = isPlaying,
                fillMaxWidth = true,
                coroutineScope = coroutineScope,
                modifier = Modifier
                    .onGloballyPositioned { coordinates ->
                        if (rightPaneScrollBridge != null && bridgeSupportsItem) {
                            val bounds = coordinates.boundsInRoot()
                            val previousBounds = rightPaneTapTargets[rightPaneTapKey]?.first
                            rightPaneTapTargets[rightPaneTapKey] = bounds to onItemClick
                            if (item is PlaylistItem && previousBounds != bounds) {
                                Timber.tag("Dudu7BrowseTarget").i(
                                    "type=PlaylistItem id=%s bounds=[%.1f,%.1f,%.1f,%.1f] title=%s browseId=%s",
                                    item.id,
                                    bounds.left,
                                    bounds.top,
                                    bounds.right,
                                    bounds.bottom,
                                    item.title,
                                    item.id,
                                )
                            }
                        } else {
                            rightPaneTapTargets.remove(rightPaneTapKey)
                        }
                    }
                    .then(interactionModifier)
                    .animateItem(),
            )
        }
    }

    TopAppBar(
        title = { Text(browseResult?.title.orEmpty()) },
        navigationIcon = {
            IconButton(
                onClick = navController::navigateUp,
                onLongClick = navController::backToMain,
            ) {
                Icon(painterResource(R.drawable.arrow_back), contentDescription = null)
            }
        },
    )
}
