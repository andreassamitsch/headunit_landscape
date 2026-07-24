#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

# The normal/full-screen Metrolist artist page keeps its original LazyColumn.
# Only the embedded Dudu7 pane gets a regular Column + ScrollState, avoiding the
# LazyColumn draw-tree failure that left semantics visible but rendered white.
for line in (
    "import androidx.compose.foundation.gestures.Orientation\n",
    "import androidx.compose.foundation.gestures.scrollable\n",
):
    artist = artist.replace(line, "")
if "import androidx.compose.foundation.rememberScrollState\n" not in artist:
    artist = artist.replace(
        "import androidx.compose.foundation.combinedClickable\n",
        "import androidx.compose.foundation.combinedClickable\n"
        "import androidx.compose.foundation.rememberScrollState\n"
        "import androidx.compose.foundation.verticalScroll\n",
        1,
    )
if "import androidx.compose.material3.FloatingActionButton\n" not in artist:
    artist = artist.replace(
        "import androidx.compose.material3.ExperimentalMaterial3Api\n",
        "import androidx.compose.material3.ExperimentalMaterial3Api\n"
        "import androidx.compose.material3.FloatingActionButton\n"
        "import androidx.compose.material3.SmallFloatingActionButton\n",
        1,
    )

artist = replace_once(
    artist,
    '''    val lazyListState = rememberLazyListState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
''',
    '''    val lazyListState = rememberLazyListState()
    val embeddedScrollState = rememberScrollState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
''',
    "embedded ScrollState declaration",
)

old_registration = '''
    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = null,
                tapHandler = null,
                scrollEndHandler = null,
                scrollableState = lazyListState,
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
        }
    }
'''
new_registration = '''
    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, embeddedScrollState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = { delta ->
                    embeddedScrollState.dispatchRawDelta(delta.coerceIn(-160f, 160f))
                },
                tapHandler = { positionInRoot ->
                    val target =
                        rightPaneTapTargets.values.lastOrNull { (bounds, _) ->
                            bounds.contains(positionInRoot)
                        }
                    if (target != null) {
                        target.second.invoke()
                        true
                    } else {
                        false
                    }
                },
                scrollEndHandler = null,
                scrollableState = null,
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
            rightPaneTapTargets.clear()
        }
    }
'''
artist = replace_once(artist, old_registration, new_registration, "embedded bridge registration")

insert_marker = '''    LaunchedEffect(artistPage?.artist?.id) {
        rightPaneTapTargets.clear()
    }

    BoxWithConstraints(
'''

embedded_branch = r'''    LaunchedEffect(artistPage?.artist?.id) {
        rightPaneTapTargets.clear()
    }

    if (embeddedInPlayer) {
        BoxWithConstraints(
            modifier = Modifier.fillMaxSize(),
        ) {
            val embeddedPaneWidth = maxWidth
            val thumbnail = artistPage?.artist?.thumbnail ?: libraryArtist?.artist?.thumbnailUrl
            val artistName = artistPage?.artist?.title ?: libraryArtist?.artist?.name ?: "Unknown"
            val showLocalFab = librarySongs.isNotEmpty() && libraryArtist?.artist?.isLocal != true
            val canPlayAll =
                !isGuest && (
                    (showLocal && librarySongs.isNotEmpty()) ||
                        (
                            !showLocal && artistPage?.sections?.any {
                                (it.items.firstOrNull() as? SongItem)?.album != null
                            } == true
                        )
                )

            fun tapTargetModifier(
                key: String,
                action: () -> Unit,
            ): Modifier =
                Modifier.onGloballyPositioned { coordinates ->
                    rightPaneTapTargets[key] = coordinates.boundsInRoot() to action
                }

            val onPlayAllClick: () -> Unit = {
                timber.log.Timber.tag("Dudu7ArtistAction").i(
                    "Play all clicked embedded=true local=%s",
                    showLocal,
                )
                if (!isGuest) {
                    playerConnection.notifyUserSongSelection()
                    if (showLocal) {
                        if (librarySongs.isNotEmpty()) {
                            playerConnection.playQueue(
                                ListQueue(
                                    title = libraryArtist?.artist?.name ?: artistName,
                                    items = librarySongs.map { it.toMediaItem() },
                                ),
                            )
                        }
                    } else if (artistPage != null) {
                        val songSection =
                            artistPage.sections.find { section ->
                                (section.items.firstOrNull() as? SongItem)?.album != null
                            }
                        val moreEndpoint = songSection?.moreEndpoint
                        if (moreEndpoint != null) {
                            coroutineScope.launch(kotlinx.coroutines.Dispatchers.IO) {
                                val result = YouTube.artistItems(moreEndpoint).getOrNull()
                                withContext(kotlinx.coroutines.Dispatchers.Main) {
                                    val songs =
                                        result
                                            ?.items
                                            ?.filterIsInstance<SongItem>()
                                            ?.map { it.toMediaItem() }
                                            .orEmpty()
                                            .ifEmpty {
                                                songSection.items
                                                    .filterIsInstance<SongItem>()
                                                    .map { it.toMediaItem() }
                                            }
                                    if (songs.isNotEmpty()) {
                                        playerConnection.playQueue(
                                            ListQueue(
                                                title = artistPage.artist.title,
                                                items = songs,
                                            ),
                                        )
                                    }
                                }
                            }
                        } else {
                            val songs =
                                songSection
                                    ?.items
                                    ?.filterIsInstance<SongItem>()
                                    ?.map { it.toMediaItem() }
                                    .orEmpty()
                            if (songs.isNotEmpty()) {
                                playerConnection.playQueue(
                                    ListQueue(
                                        title = artistPage.artist.title,
                                        items = songs,
                                    ),
                                )
                            } else {
                                artistPage.artist.shuffleEndpoint?.let { endpoint ->
                                    playerConnection.playQueue(YouTubeQueue(endpoint))
                                }
                            }
                        }
                    }
                }
            }

            Box(modifier = Modifier.fillMaxSize()) {
                Column(
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .verticalScroll(embeddedScrollState)
                            .padding(top = AppBarHeight, bottom = 104.dp),
                ) {
                    if (artistPage == null && !showLocal) {
                        ShimmerHost {
                            Box(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .aspectRatio(1.45f)
                                        .shimmer()
                                        .background(MaterialTheme.colorScheme.onSurface),
                            )
                            Column(
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                            ) {
                                TextPlaceholder(
                                    height = 36.dp,
                                    modifier = Modifier.fillMaxWidth(0.7f),
                                )
                                repeat(6) { ListItemPlaceHolder() }
                            }
                        }
                    } else {
                        if (thumbnail != null) {
                            AsyncImage(
                                model = thumbnail.resize(1200, 1200),
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier =
                                    Modifier
                                        .fillMaxWidth()
                                        .aspectRatio(1.45f)
                                        .fadingEdge(bottom = 120.dp),
                            )
                        }

                        Column(
                            modifier =
                                Modifier
                                    .fillMaxWidth()
                                    .padding(horizontal = 16.dp, vertical = 12.dp),
                        ) {
                            Text(
                                text = artistName,
                                style = MaterialTheme.typography.headlineLarge,
                                fontWeight = FontWeight.Bold,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                fontSize = 32.sp,
                            )
                            Spacer(modifier = Modifier.height(12.dp))
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                val toggleSubscription: () -> Unit = viewModel::toggleChannelSubscription
                                OutlinedButton(
                                    onClick = toggleSubscription,
                                    modifier = tapTargetModifier("artist_subscribe", toggleSubscription),
                                    colors =
                                        ButtonDefaults.outlinedButtonColors(
                                            containerColor =
                                                if (isChannelSubscribed) {
                                                    MaterialTheme.colorScheme.surface
                                                } else {
                                                    Color.Transparent
                                                },
                                        ),
                                    shape = RoundedCornerShape(50),
                                ) {
                                    Text(
                                        text = stringResource(if (isChannelSubscribed) R.string.subscribed else R.string.subscribe),
                                        color = if (!isChannelSubscribed) MaterialTheme.colorScheme.error else LocalContentColor.current,
                                    )
                                }
                                Spacer(modifier = Modifier.weight(1f))
                                artistPage?.artist?.radioEndpoint?.let { endpoint ->
                                    val playRadio: () -> Unit = {
                                        playerConnection.notifyUserSongSelection()
                                        playerConnection.playQueue(YouTubeQueue(endpoint))
                                    }
                                    OutlinedButton(
                                        onClick = playRadio,
                                        modifier = tapTargetModifier("artist_radio", playRadio),
                                        shape = RoundedCornerShape(50),
                                    ) {
                                        Icon(
                                            painter = painterResource(R.drawable.radio),
                                            contentDescription = null,
                                            modifier = Modifier.size(20.dp),
                                        )
                                        Spacer(modifier = Modifier.width(8.dp))
                                        Text(stringResource(R.string.radio))
                                    }
                                }
                                Spacer(modifier = Modifier.width(10.dp))
                                artistPage?.artist?.shuffleEndpoint?.let { endpoint ->
                                    val playShuffle: () -> Unit = {
                                        playerConnection.notifyUserSongSelection()
                                        playerConnection.playQueue(YouTubeQueue(endpoint))
                                    }
                                    androidx.compose.material3.IconButton(
                                        onClick = playShuffle,
                                        modifier =
                                            Modifier
                                                .size(48.dp)
                                                .background(
                                                    MaterialTheme.colorScheme.primary,
                                                    RoundedCornerShape(24.dp),
                                                ).then(tapTargetModifier("artist_shuffle", playShuffle)),
                                    ) {
                                        Icon(
                                            painter = painterResource(R.drawable.shuffle),
                                            contentDescription = "Shuffle",
                                            tint = MaterialTheme.colorScheme.onPrimary,
                                        )
                                    }
                                }
                            }
                        }

                        if (!showLocal && (showArtistDescription || showArtistSubscriberCount || showMonthlyListeners)) {
                            val description = artistPage?.description
                            val descriptionRuns = artistPage?.descriptionRuns
                            val subscriberCount = artistPage?.subscriberCountText
                            val monthlyListeners = artistPage?.monthlyListenerCount
                            if (
                                (showArtistDescription && (!description.isNullOrEmpty() || !descriptionRuns.isNullOrEmpty())) ||
                                (showArtistSubscriberCount && !subscriberCount.isNullOrEmpty()) ||
                                (showMonthlyListeners && !monthlyListeners.isNullOrEmpty())
                            ) {
                                Column(
                                    modifier =
                                        Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 16.dp, vertical = 8.dp),
                                ) {
                                    if (showArtistDescription && (!description.isNullOrEmpty() || !descriptionRuns.isNullOrEmpty())) {
                                        Text(
                                            text = stringResource(R.string.about_artist),
                                            style = MaterialTheme.typography.titleMedium,
                                            fontWeight = FontWeight.Bold,
                                        )
                                    }
                                    if (showArtistSubscriberCount && !subscriberCount.isNullOrEmpty()) {
                                        Text(
                                            text = subscriberCount,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    if (showMonthlyListeners && !monthlyListeners.isNullOrEmpty()) {
                                        Text(
                                            text = monthlyListeners,
                                            style = MaterialTheme.typography.bodyMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                    if (showArtistDescription && (!description.isNullOrEmpty() || !descriptionRuns.isNullOrEmpty())) {
                                        ExpandableText(
                                            text = description.orEmpty(),
                                            runs =
                                                descriptionRuns?.map {
                                                    LinkSegment(
                                                        text = it.text,
                                                        url = it.navigationEndpoint?.urlEndpoint?.url,
                                                    )
                                                },
                                            collapsedMaxLines = 3,
                                        )
                                    }
                                }
                            }
                        }

                        if (showLocal) {
                            if (librarySongs.isNotEmpty()) {
                                val openLocalSongs: () -> Unit = {
                                    navController.navigate("artist/${viewModel.artistId}/songs")
                                }
                                NavigationTitle(
                                    title = stringResource(R.string.songs),
                                    modifier = tapTargetModifier("local_songs", openLocalSongs),
                                    onClick = openLocalSongs,
                                )
                                val filteredSongs =
                                    if (hideExplicit) librarySongs.filter { !it.song.explicit } else librarySongs
                                filteredSongs.take(20).forEachIndexed { index, song ->
                                    SongListItem(
                                        song = song,
                                        showInLibraryIcon = true,
                                        isActive = song.id == mediaMetadata?.id,
                                        isPlaying = isPlaying,
                                        trailingContent = null,
                                        modifier =
                                            Modifier
                                                .fillMaxWidth()
                                                .combinedClickable(
                                                    onClick = {
                                                        if (!isGuest) {
                                                            playerConnection.notifyUserSongSelection()
                                                            playerConnection.playQueue(
                                                                ListQueue(
                                                                    title = libraryArtist?.artist?.name ?: artistName,
                                                                    items = filteredSongs.map { it.toMediaItem() },
                                                                    startIndex = index,
                                                                ),
                                                            )
                                                        }
                                                    },
                                                    onLongClick = {},
                                                ),
                                    )
                                }
                            }
                            if (libraryAlbums.isNotEmpty()) {
                                val openLocalAlbums: () -> Unit = {
                                    navController.navigate("artist/${viewModel.artistId}/albums")
                                }
                                NavigationTitle(
                                    title = stringResource(R.string.albums),
                                    modifier = tapTargetModifier("local_albums", openLocalAlbums),
                                    onClick = openLocalAlbums,
                                )
                                LazyRow {
                                    items(libraryAlbums, key = { it.id }) { album ->
                                        AlbumGridItem(
                                            album = album,
                                            isActive = mediaMetadata?.album?.id == album.id,
                                            isPlaying = isPlaying,
                                            coroutineScope = coroutineScope,
                                            modifier =
                                                Modifier.combinedClickable(
                                                    onClick = { navController.navigate("album/${album.id}") },
                                                    onLongClick = {},
                                                ),
                                        )
                                    }
                                }
                            }
                        } else {
                            artistPage?.sections?.forEachIndexed { index, section ->
                                val sectionItems = distinctItemsBySection.getOrNull(index) ?: section.items
                                val isSongSection = (section.items.firstOrNull() as? SongItem)?.album != null
                                val moreEndpoint = section.moreEndpoint
                                val openSection: (() -> Unit)? =
                                    when {
                                        moreEndpoint != null -> {
                                            {
                                                timber.log.Timber.tag("Dudu7ArtistNavigation").d(
                                                    "Opening artist section title=%s browseId=%s fallback=false",
                                                    section.title,
                                                    moreEndpoint.browseId,
                                                )
                                                navController.navigate(
                                                    "artist/${viewModel.artistId}/items?browseId=${android.net.Uri.encode(moreEndpoint.browseId)}&params=${android.net.Uri.encode(moreEndpoint.params.orEmpty())}",
                                                )
                                            }
                                        }
                                        isSongSection -> {
                                            {
                                                timber.log.Timber.tag("Dudu7ArtistNavigation").d(
                                                    "Opening artist section title=%s browseId=artist_songs_fallback fallback=true",
                                                    section.title,
                                                )
                                                navController.navigate(
                                                    "artist/${viewModel.artistId}/items?browseId=__artist_songs__&params=",
                                                )
                                            }
                                        }
                                        else -> null
                                    }
                                if (section.items.isNotEmpty()) {
                                    val sectionKey = "embedded_${index}_${section.title}"
                                    NavigationTitle(
                                        title = section.title,
                                        modifier =
                                            if (openSection != null) {
                                                tapTargetModifier(sectionKey, openSection)
                                            } else {
                                                Modifier
                                            },
                                        onClick = openSection,
                                    )
                                }
                                if (isSongSection) {
                                    sectionItems.filterIsInstance<SongItem>().take(10).forEach { song ->
                                        YouTubeListItem(
                                            item = song,
                                            isActive = mediaMetadata?.id == song.id,
                                            isPlaying = isPlaying,
                                            trailingContent = null,
                                            modifier =
                                                Modifier.combinedClickable(
                                                    onClick = {
                                                        if (!isGuest) {
                                                            playerConnection.notifyUserSongSelection()
                                                            playerConnection.playQueue(
                                                                YouTubeQueue(
                                                                    WatchEndpoint(videoId = song.id),
                                                                    song.toMediaMetadata(),
                                                                ),
                                                            )
                                                        }
                                                    },
                                                    onLongClick = {},
                                                ),
                                        )
                                    }
                                } else if (sectionItems.isNotEmpty()) {
                                    LazyRow {
                                        items(sectionItems, key = { "embedded_${section.title}_${it.id}" }) { item ->
                                            YouTubeGridItem(
                                                item = item,
                                                isActive =
                                                    when (item) {
                                                        is SongItem -> mediaMetadata?.id == item.id
                                                        is AlbumItem -> mediaMetadata?.album?.id == item.id
                                                        else -> false
                                                    },
                                                isPlaying = isPlaying,
                                                coroutineScope = coroutineScope,
                                                thumbnailRatio = 1f,
                                                modifier =
                                                    Modifier.combinedClickable(
                                                        onClick = {
                                                            when (item) {
                                                                is SongItem -> {
                                                                    if (!isGuest) {
                                                                        playerConnection.notifyUserSongSelection()
                                                                        playerConnection.playQueue(
                                                                            YouTubeQueue(
                                                                                WatchEndpoint(videoId = item.id),
                                                                                item.toMediaMetadata(),
                                                                            ),
                                                                        )
                                                                    }
                                                                }
                                                                is AlbumItem -> navController.navigate("album/${item.id}")
                                                                is ArtistItem -> navController.navigate("artist/${item.id}")
                                                                is PlaylistItem -> navController.navigate("online_playlist/${item.id}")
                                                                is PodcastItem -> navController.navigate("online_podcast/${item.id}")
                                                                is EpisodeItem -> {
                                                                    if (!isGuest) {
                                                                        playerConnection.notifyUserSongSelection()
                                                                        playerConnection.playQueue(
                                                                            YouTubeQueue(
                                                                                WatchEndpoint(videoId = item.id),
                                                                                item.toMediaMetadata(),
                                                                            ),
                                                                        )
                                                                    }
                                                                }
                                                            }
                                                        },
                                                        onLongClick = {},
                                                    ),
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                if (showLocalFab) {
                    val toggleLocal: () -> Unit = {
                        showLocal = !showLocal
                        if (!showLocal && artistPage == null) viewModel.fetchArtistsFromYTM()
                    }
                    SmallFloatingActionButton(
                        onClick = toggleLocal,
                        modifier =
                            Modifier
                                .align(Alignment.BottomEnd)
                                .padding(end = 20.dp, bottom = 84.dp)
                                .then(tapTargetModifier("artist_local_toggle", toggleLocal)),
                    ) {
                        Icon(
                            painter = painterResource(if (showLocal) R.drawable.language else R.drawable.library_music),
                            contentDescription = null,
                        )
                    }
                }

                if (canPlayAll) {
                    FloatingActionButton(
                        onClick = onPlayAllClick,
                        modifier =
                            Modifier
                                .align(Alignment.BottomEnd)
                                .padding(16.dp)
                                .then(tapTargetModifier("artist_play_all", onPlayAllClick)),
                    ) {
                        Icon(
                            painter = painterResource(R.drawable.play),
                            contentDescription = "Play All",
                            modifier = Modifier.size(32.dp),
                        )
                    }
                }

                TopAppBar(
                    title = {
                        if (embeddedScrollState.value > 80) {
                            Text(artistName)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = navController::navigateUp) {
                            Icon(
                                painter = painterResource(R.drawable.arrow_back),
                                contentDescription = null,
                            )
                        }
                    },
                    colors =
                        if (embeddedScrollState.value <= 80) {
                            TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent)
                        } else {
                            TopAppBarDefaults.topAppBarColors()
                        },
                )

                SnackbarHost(
                    hostState = snackbarHostState,
                    modifier = Modifier.align(Alignment.BottomCenter),
                )
            }
        }
        return
    }

    BoxWithConstraints(
'''

artist = replace_once(artist, insert_marker, embedded_branch, "embedded non-lazy artist branch")

# Normal/full-screen path no longer needs the embedded flag checks after the early return.
artist = artist.replace("userScrollEnabled = !embeddedInPlayer,", "userScrollEnabled = true,", 1)

if "if (embeddedInPlayer) {\n        BoxWithConstraints" not in artist:
    raise SystemExit("Embedded non-lazy artist branch missing")
if ".verticalScroll(embeddedScrollState)" not in artist:
    raise SystemExit("Embedded ScrollState renderer missing")
if "embeddedScrollState.dispatchRawDelta" not in artist:
    raise SystemExit("Embedded parent scroll handler missing")
artist_path.write_text(artist, encoding="utf-8")


# Restore the fixed right pane's existing custom pointer handling for artist routes.
# This is separate from, and does not change, the Player's original nested scroll.
layout_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
layout = layout_path.read_text(encoding="utf-8")
layout = layout.replace("import androidx.compose.foundation.gestures.Orientation\n", "")
layout = layout.replace("import androidx.compose.foundation.gestures.scrollable\n", "")
old_branch = '''                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        rightPaneScrollBridge.scrollableState?.let { artistScrollState ->
                                            Modifier.scrollable(
                                                state = artistScrollState,
                                                orientation = Orientation.Vertical,
                                            )
                                        } ?: Modifier
                                    } else {
'''
new_branch = '''                                    if (
                                        currentPaneRoute?.startsWith("artist/") == true &&
                                        rightPaneScrollBridge.handler == null
                                    ) {
                                        Modifier
                                    } else {
'''
layout = replace_once(layout, old_branch, new_branch, "artist custom pointer restoration")
if ".nestedScroll(state.preUpPostDownNestedScrollConnection)" not in layout:
    raise SystemExit("Original Player nested-scroll connection was lost")
layout_path.write_text(layout, encoding="utf-8")

print("Added a non-lazy embedded ArtistScreen with ScrollState and preserved the original Player nested scroll")
