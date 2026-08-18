/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens.playlist

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ContainedLoadingIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.boundsInRoot
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.fastAny
import androidx.compose.ui.util.fastForEachReversed
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavController
import coil3.compose.AsyncImage
import coil3.request.ImageRequest
import com.metrolist.innertube.models.PlaylistItem
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.LocalDatabase
import com.metrolist.music.LocalListenTogetherManager
import com.metrolist.music.LocalNavController
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.LocalSyncUtils
import com.metrolist.music.R
import com.metrolist.music.constants.HideExplicitKey
import com.metrolist.music.db.entities.Playlist
import com.metrolist.music.playback.queues.YouTubePlaylistQueue
import com.metrolist.music.ui.component.ExpandableText
import com.metrolist.music.ui.component.IconButton
import com.metrolist.music.ui.component.LocalMenuState
import com.metrolist.music.ui.component.LocalRightPaneScrollBridge
import com.metrolist.music.ui.component.YouTubeListItem
import com.metrolist.music.ui.menu.YouTubePlaylistMenu
import com.metrolist.music.ui.menu.YouTubeSelectionSongMenu
import com.metrolist.music.ui.menu.YouTubeSongMenu
import com.metrolist.music.ui.utils.backToMain
import com.metrolist.music.utils.rememberPreference
import com.metrolist.music.viewmodels.OnlinePlaylistViewModel
import kotlinx.coroutines.CoroutineScope
import timber.log.Timber

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun OnlinePlaylistScreen(navController: NavController, viewModel: OnlinePlaylistViewModel = hiltViewModel()) {
    val menuState = LocalMenuState.current
    val haptic = LocalHapticFeedback.current
    val playerConnection = LocalPlayerConnection.current ?: return
    val isPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()
    val playlist by viewModel.playlist.collectAsStateWithLifecycle()
    val songs by viewModel.playlistSongs.collectAsStateWithLifecycle()
    val dbPlaylist by viewModel.dbPlaylist.collectAsStateWithLifecycle()
    val isLoading by viewModel.isLoading.collectAsStateWithLifecycle()
    val isLoadingMore by viewModel.isLoadingMore.collectAsStateWithLifecycle()
    val error by viewModel.error.collectAsStateWithLifecycle()
    val isPodcastPlaylist = viewModel.isPodcastPlaylist
    val hideExplicit by rememberPreference(key = HideExplicitKey, defaultValue = false)
    val lazyListState = rememberLazyListState()
    val snackbarHostState = remember { SnackbarHostState() }
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneSongTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
    val coroutineScope = rememberCoroutineScope()
    var isSearching by rememberSaveable { mutableStateOf(false) }
    var query by rememberSaveable(stateSaver = TextFieldValue.Saver) { mutableStateOf(TextFieldValue()) }
    val filteredSongs = remember(songs, query) {
        if (query.text.isEmpty()) songs.mapIndexed { i, s -> i to s }
        else songs.mapIndexed { i, s -> i to s }.filter { it.second.title.contains(query.text, true) || it.second.artists.fastAny { a -> a.name.contains(query.text, true) } }
    }
    var inSelectMode by remember { mutableStateOf(false) }
    val selection = remember { mutableStateListOf<String>() }
    var selectionAnchorSongId by remember { mutableStateOf<String?>(null) }
    val onExitSelectionMode = { inSelectMode = false; selection.clear(); selectionAnchorSongId = null }
    val focusRequester = remember { FocusRequester() }
    LaunchedEffect(isSearching) { if (isSearching) focusRequester.requestFocus() }
    LaunchedEffect(filteredSongs) {
        selection.fastForEachReversed { songId -> if (filteredSongs.find { it.second.id == songId } == null) selection.remove(songId) }
        if (selectionAnchorSongId != null && filteredSongs.none { it.second.id == selectionAnchorSongId }) selectionAnchorSongId = filteredSongs.firstOrNull { it.second.id in selection }?.second?.id
    }
    DisposableEffect(rightPaneScrollBridge, lazyListState) {
        if (rightPaneScrollBridge != null) rightPaneScrollBridge.register(
            owner = rightPaneScrollOwner,
            handler = { delta -> lazyListState.dispatchRawDelta(delta) },
            tapHandler = { positionInRoot ->
                val target = rightPaneSongTapTargets.values.lastOrNull { (bounds, _) -> bounds.contains(positionInRoot) }
                if (target != null) { Timber.tag("Dudu7PlaylistTap").i("Bridged OnlinePlaylistScreen row tap x=%.1f y=%.1f", positionInRoot.x, positionInRoot.y); target.second.invoke(); true } else false
            },
        )
        onDispose { rightPaneScrollBridge?.unregister(rightPaneScrollOwner); rightPaneSongTapTargets.clear() }
    }
    if (isSearching) BackHandler { isSearching = false; query = TextFieldValue() } else if (inSelectMode) BackHandler(onBack = onExitSelectionMode)

    Box(Modifier.fillMaxSize()) {
        LazyColumn(state = lazyListState, contentPadding = LocalPlayerAwareWindowInsets.current.union(WindowInsets.ime).asPaddingValues(), userScrollEnabled = rightPaneScrollBridge == null) {
            if (playlist == null || songs.isEmpty()) {
                if (isLoading) item(key = "loading_placeholder") { Box(Modifier.fillParentMaxSize().padding(32.dp), contentAlignment = Alignment.Center) { ContainedLoadingIndicator() } }
                else if (error != null) item(key = "error_placeholder") { Column(Modifier.fillParentMaxSize().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { Text(error ?: stringResource(R.string.error_unknown), style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center); Spacer(Modifier.height(16.dp)); androidx.compose.material3.TextButton(onClick = { viewModel.retry() }) { Text(stringResource(R.string.retry)) } } }
                else if (!isLoading && songs.isEmpty()) item(key = "empty_placeholder") { Box(Modifier.fillParentMaxSize().padding(32.dp), contentAlignment = Alignment.Center) { Text(stringResource(R.string.playlist_is_empty), style = MaterialTheme.typography.bodyLarge) } }
            } else playlist?.let { playlist ->
                if (!isSearching) item(key = "playlist_header") { OnlinePlaylistHeader(playlist, songs, dbPlaylist, coroutineScope, viewModel.continuation, isPodcastPlaylist, Modifier.animateItem()) }
                itemsIndexed(filteredSongs) { index, (_, songItem) ->
                    val onCheckedChange: (Boolean) -> Unit = { if (it) selection.add(songItem.id) else selection.remove(songItem.id) }
                    val onSongClick: () -> Unit = {
                        if (inSelectMode) onCheckedChange(songItem.id !in selection)
                        else if (songItem.id == mediaMetadata?.id) playerConnection.togglePlayPause()
                        else {
                            Timber.tag("Dudu7PlaylistPlayback").i("play row id=%s index=%d playlist=%s", songItem.id, index, playlist.id)
                            playerConnection.playQueue(YouTubePlaylistQueue(playlistId = playlist.id, playlistTitle = playlist.title, initialSongs = filteredSongs.map { it.second }, initialContinuation = viewModel.continuation, startIndex = index))
                        }
                    }
                    val onSongLongClick: () -> Unit = {
                        if (!inSelectMode) { haptic.performHapticFeedback(HapticFeedbackType.LongPress); inSelectMode = true; onCheckedChange(true); selectionAnchorSongId = songItem.id }
                        else {
                            val anchorIndex = selectionAnchorSongId?.let { id -> filteredSongs.indexOfFirst { it.second.id == id } } ?: -1
                            if (anchorIndex == -1) { onCheckedChange(true); selectionAnchorSongId = songItem.id }
                            else { val range = if (anchorIndex <= index) anchorIndex..index else index..anchorIndex; for (rangeIndex in range) { val id = filteredSongs[rangeIndex].second.id; if (id !in selection) selection.add(id) } }
                        }
                    }
                    val tapKey = "online_playlist_song_${songItem.id}"
                    DisposableEffect(tapKey, rightPaneScrollBridge) { onDispose { rightPaneSongTapTargets.remove(tapKey) } }
                    val interactionModifier = if (rightPaneScrollBridge != null) Modifier else Modifier.combinedClickable(enabled = !hideExplicit || !songItem.explicit, onClick = onSongClick, onLongClick = onSongLongClick)
                    YouTubeListItem(
                        item = songItem, isActive = mediaMetadata?.id == songItem.id, isPlaying = isPlaying, isSelected = inSelectMode && songItem.id in selection,
                        modifier = Modifier.onGloballyPositioned { coordinates -> if (rightPaneScrollBridge != null && (!hideExplicit || !songItem.explicit)) rightPaneSongTapTargets[tapKey] = coordinates.boundsInRoot() to onSongClick else rightPaneSongTapTargets.remove(tapKey) }.then(interactionModifier).animateItem(),
                        trailingContent = { if (inSelectMode) Checkbox(checked = songItem.id in selection, onCheckedChange = onCheckedChange) else IconButton(onClick = { menuState.show { YouTubeSongMenu(songItem, menuState::dismiss) } }) { Icon(painterResource(R.drawable.more_vert), null) } },
                    )
                }
                if (isLoadingMore) item(key = "loading_more") { Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) { ContainedLoadingIndicator() } }
            }
        }
        TopAppBar(
            title = {
                if (inSelectMode) Text(if (isPodcastPlaylist) pluralStringResource(R.plurals.n_episode, selection.size, selection.size) else pluralStringResource(R.plurals.n_song, selection.size, selection.size), style = MaterialTheme.typography.titleLarge)
                else if (isSearching) TextField(value = query, onValueChange = { query = it }, placeholder = { Text(stringResource(R.string.search), style = MaterialTheme.typography.titleLarge) }, singleLine = true, textStyle = MaterialTheme.typography.titleLarge, keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search), colors = TextFieldDefaults.colors(focusedContainerColor = Color.Transparent, unfocusedContainerColor = Color.Transparent, focusedIndicatorColor = Color.Transparent, unfocusedIndicatorColor = Color.Transparent, disabledIndicatorColor = Color.Transparent), modifier = Modifier.fillMaxWidth().focusRequester(focusRequester))
                else if (lazyListState.firstVisibleItemIndex > 0) Text(playlist?.title ?: "")
            },
            navigationIcon = { IconButton(onClick = { if (isSearching) { isSearching = false; query = TextFieldValue() } else if (inSelectMode) onExitSelectionMode() else navController.navigateUp() }, onLongClick = { if (!isSearching && !inSelectMode) navController.backToMain() }) { Icon(painterResource(if (inSelectMode) R.drawable.close else R.drawable.arrow_back), null) } },
            actions = {
                if (inSelectMode) {
                    Checkbox(checked = selection.size == filteredSongs.size && selection.isNotEmpty(), onCheckedChange = { if (selection.size == filteredSongs.size) selection.clear() else { selection.clear(); selection.addAll(filteredSongs.map { it.second.id }) } })
                    IconButton(enabled = selection.isNotEmpty(), onClick = { menuState.show { YouTubeSelectionSongMenu(songSelection = filteredSongs.filter { it.second.id in selection }.map { it.second }, onDismiss = menuState::dismiss, clearAction = onExitSelectionMode) } }) { Icon(painterResource(R.drawable.more_vert), null) }
                } else if (!isSearching) IconButton(onClick = { isSearching = true }) { Icon(painterResource(R.drawable.search), null) }
            },
        )
        SnackbarHost(hostState = snackbarHostState, modifier = Modifier.align(Alignment.BottomCenter))
    }
}

@Composable
private fun OnlinePlaylistHeader(playlist: PlaylistItem, songs: List<SongItem>, dbPlaylist: Playlist?, coroutineScope: CoroutineScope, continuation: String?, isPodcastPlaylist: Boolean = false, modifier: Modifier = Modifier) {
    val playerConnection = LocalPlayerConnection.current ?: return
    val menuState = LocalMenuState.current
    Column(modifier = modifier.fillMaxWidth().padding(top = 8.dp, bottom = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Surface(modifier = Modifier.size(240.dp).shadow(8.dp, RoundedCornerShape(12.dp)).clip(RoundedCornerShape(12.dp)), color = MaterialTheme.colorScheme.surfaceContainer) {
            AsyncImage(model = ImageRequest.Builder(LocalContext.current).data(playlist.thumbnail).build(), contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        }
        Spacer(Modifier.height(16.dp))
        Text(playlist.title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, textAlign = TextAlign.Center)
        playlist.author?.name?.let { Text(it, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.secondary) }
        playlist.description?.takeIf { it.isNotBlank() }?.let { ExpandableText(text = it, modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp)) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(enabled = songs.isNotEmpty(), onClick = { playerConnection.playQueue(YouTubePlaylistQueue(playlistId = playlist.id, playlistTitle = playlist.title, initialSongs = songs, initialContinuation = continuation)) }) { Icon(painterResource(R.drawable.play), null) }
            IconButton(onClick = { menuState.show { YouTubePlaylistMenu(playlist = playlist, songs = songs, coroutineScope = coroutineScope, onDismiss = menuState::dismiss) } }) { Icon(painterResource(R.drawable.more_vert), null) }
        }
    }
}
