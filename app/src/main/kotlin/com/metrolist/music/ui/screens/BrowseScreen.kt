/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens

import android.view.KeyEvent as AndroidKeyEvent
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
import androidx.compose.ui.input.key.nativeKeyEvent
import androidx.compose.ui.input.key.onKeyEvent
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.innertube.models.ArtistItem
import com.metrolist.innertube.models.PlaylistItem
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.constants.AutoRadioQueueKey
import com.metrolist.music.constants.GridItemSize
import com.metrolist.music.constants.GridItemsSizeKey
import com.metrolist.music.constants.GridThumbnailHeight
import com.metrolist.music.ui.component.IconButton
import com.metrolist.music.ui.component.LocalMenuState
import com.metrolist.music.ui.component.LocalRightPaneScrollBridge
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
import timber.log.Timber

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
    val lazyGridState = rememberLazyGridState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }

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

    // The fixed Dudu7 right pane owns vertical gestures and can route taps by the
    // real card bounds. Playlist cards deliberately do not attach a pointer-click
    // modifier while embedded: on the FYT/Dudu7 target combinedClickable consumes
    // the touch but can fail to execute its click callback. The parent then sees a
    // consumed event and cannot use its bridge fallback. Keyboard/D-pad activation
    // is preserved explicitly below; standard MetroList keeps combinedClickable.
    DisposableEffect(rightPaneScrollBridge, lazyGridState) {
        if (rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = { delta -> lazyGridState.dispatchRawDelta(delta) },
                tapHandler = { positionInRoot ->
                    val target =
                        rightPaneTapTargets.values.lastOrNull { (bounds, _) ->
                            bounds.contains(positionInRoot)
                        }
                    if (target != null) {
                        Timber.tag("Dudu7BrowseTap").i(
                            "Bridged BrowseScreen tap x=%.1f y=%.1f browseId=%s",
                            positionInRoot.x,
                            positionInRoot.y,
                            browseId,
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
        columns = GridCells.Adaptive(minSize = GridThumbnailHeight + if (gridItemSize == GridItemSize.BIG) 24.dp else (-24).dp),
        state = lazyGridState,
        contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
        userScrollEnabled = rightPaneScrollBridge == null,
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
                            Timber.tag("Dudu7BrowseNavigate").i(
                                "completed type=playlist id=%s currentRoute=%s title=%s",
                                item.id,
                                navController.currentDestination?.route,
                                item.title,
                            )
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

                val rightPaneTapKey = "browse_item_${item.id}"
                val bridgeSupportsItem =
                    item is SongItem || item is AlbumItem || item is PlaylistItem || item is ArtistItem
                val parentOwnsPlaylistPointer = rightPaneScrollBridge != null && item is PlaylistItem

                DisposableEffect(rightPaneTapKey, rightPaneScrollBridge) {
                    onDispose {
                        rightPaneTapTargets.remove(rightPaneTapKey)
                    }
                }

                val interactionModifier =
                    if (parentOwnsPlaylistPointer) {
                        Modifier
                            .focusable()
                            .onKeyEvent { event ->
                                val native = event.nativeKeyEvent
                                val activate =
                                    native.action == AndroidKeyEvent.ACTION_UP &&
                                        native.keyCode in
                                        setOf(
                                            AndroidKeyEvent.KEYCODE_DPAD_CENTER,
                                            AndroidKeyEvent.KEYCODE_ENTER,
                                            AndroidKeyEvent.KEYCODE_NUMPAD_ENTER,
                                            AndroidKeyEvent.KEYCODE_SPACE,
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
                    isPlaying = isPlaying,
                    fillMaxWidth = true,
                    coroutineScope = coroutineScope,
                    onPlayClick =
                        (item as? SongItem)?.let { songItem ->
                            { playBrowseSong(songItem) }
                        },
                    modifier =
                        Modifier
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
                                            browseId,
                                        )
                                    }
                                } else {
                                    rightPaneTapTargets.remove(rightPaneTapKey)
                                }
                            }
                            .then(interactionModifier),
                )
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