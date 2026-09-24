#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[1]
view_model = root / "app/src/main/kotlin/com/metrolist/music/viewmodels/ArtistItemsViewModel.kt"

replace_once(
    view_model,
    '    val title = MutableStateFlow("")\n'
    '    val itemsPage = MutableStateFlow<ItemsPage?>(null)\n\n'
    '    init {\n'
    '        viewModelScope.launch {\n'
    '            if (browseId.isBlank() || browseId == "__artist_songs__") {\n'
    '                loadArtistSongFallback()\n'
    '            } else {\n'
    '                loadEndpoint(\n'
    '                    endpoint =\n'
    '                        BrowseEndpoint(\n'
    '                            browseId = browseId,\n'
    '                            params = params,\n'
    '                        ),\n'
    '                )\n'
    '            }\n'
    '        }\n'
    '    }\n',
    '''    val title = MutableStateFlow("")
    val itemsPage = MutableStateFlow<ItemsPage?>(null)
    val isLoading = MutableStateFlow(false)
    val errorMessage = MutableStateFlow<String?>(null)

    init {
        loadInitial()
    }

    private fun loadInitial() {
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                if (browseId.isBlank() || browseId == "__artist_songs__") {
                    loadArtistSongFallback()
                } else {
                    loadEndpoint(
                        endpoint =
                            BrowseEndpoint(
                                browseId = browseId,
                                params = params,
                            ),
                    )
                }
            } finally {
                isLoading.value = false
            }
        }
    }

    fun retry() {
        itemsPage.value = null
        loadInitial()
    }
''',
)
replace_once(
    view_model,
    '''        if (artistItemsPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            return false
        }

        title.value = artistItemsPage.title.ifBlank { fallbackTitle }
''',
    '''        if (artistItemsPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            errorMessage.value = result.exceptionOrNull()?.message ?: "Künstler-Inhalte konnten nicht geladen werden"
            return false
        }

        errorMessage.value = null
        title.value = artistItemsPage.title.ifBlank { fallbackTitle }
''',
)
replace_once(
    view_model,
    '''        if (artistPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            return
        }

        val songSection =
            artistPage.sections.firstOrNull { section ->
                section.items.firstOrNull() is SongItem
            } ?: return
''',
    '''        if (artistPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            errorMessage.value = result.exceptionOrNull()?.message ?: "Künstler konnte nicht geladen werden"
            return
        }

        val songSection =
            artistPage.sections.firstOrNull { section ->
                section.items.any { it is SongItem }
            }
        if (songSection == null) {
            errorMessage.value = "Für diesen Künstler wurden keine Titel gefunden"
            return
        }
''',
)
replace_once(
    view_model,
    '''        title.value = songSection.title.ifBlank { artistPage.artist.title }
        itemsPage.value =
''',
    '''        errorMessage.value = null
        title.value = songSection.title.ifBlank { artistPage.artist.title }
        itemsPage.value =
''',
)
replace_once(
    view_model,
    '''    fun loadMore() {
        viewModelScope.launch {
            val oldItemsPage = itemsPage.value ?: return@launch
            val continuation = oldItemsPage.continuation ?: return@launch
            YouTube
                .artistItemsContinuation(continuation)
                .onSuccess { artistItemsContinuationPage ->
''',
    '''    fun loadMore() {
        viewModelScope.launch {
            val oldItemsPage = itemsPage.value ?: return@launch
            val continuation = oldItemsPage.continuation ?: return@launch
            isLoading.value = true
            errorMessage.value = null
            YouTube
                .artistItemsContinuation(continuation)
                .onSuccess { artistItemsContinuationPage ->
''',
)
replace_once(
    view_model,
    '''                }.onFailure {
                    reportException(it)
                }
        }
    }
''',
    '''                }.onFailure {
                    reportException(it)
                    errorMessage.value = it.message ?: "Weitere Inhalte konnten nicht geladen werden"
                }
            isLoading.value = false
        }
    }
''',
)

embedded = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/EmbeddedArtistItemsScreen.kt"
embedded.write_text(
    '''package com.metrolist.music.ui.screens.artist

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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import com.metrolist.innertube.models.YTItem
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.extensions.toMediaItem
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.ui.utils.resize
import com.metrolist.music.viewmodels.ArtistItemsViewModel
import kotlinx.coroutines.launch

/** Flat Dudu7-safe detail page for Top Songs and other artist sections. */
@Composable
fun EmbeddedArtistItemsScreen(
    navController: NavController,
    viewModel: ArtistItemsViewModel = hiltViewModel(),
) {
    val playerConnection = LocalPlayerConnection.current ?: return
    val title by viewModel.title.collectAsStateWithLifecycle()
    val itemsPage by viewModel.itemsPage.collectAsStateWithLifecycle()
    val isLoading by viewModel.isLoading.collectAsStateWithLifecycle()
    val errorMessage by viewModel.errorMessage.collectAsStateWithLifecycle()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()
    val isPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()

    fun playFrom(selected: YTItem) {
        scope.launch {
            val allItems = viewModel.loadAllItems()
            val playableItems =
                allItems.mapNotNull { item ->
                    when (item) {
                        is SongItem -> item.toMediaItem()
                        is EpisodeItem -> item.asSongItem().toMediaItem()
                        else -> null
                    }
                }
            val selectedIndex =
                allItems
                    .filter { it is SongItem || it is EpisodeItem }
                    .indexOfFirst { it.id == selected.id }
                    .coerceAtLeast(0)
            if (playableItems.isNotEmpty()) {
                playerConnection.notifyUserSongSelection()
                playerConnection.playQueue(
                    ListQueue(
                        title = title.ifBlank { "Künstler" },
                        items = playableItems,
                        startIndex = selectedIndex,
                    ),
                    notifyUserSelection = false,
                )
            }
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            modifier = Modifier.fillMaxWidth().height(58.dp).padding(horizontal = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier.size(44.dp).clip(RoundedCornerShape(22.dp)).clickable { navController.navigateUp() },
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    painter = painterResource(R.drawable.arrow_back),
                    contentDescription = "Zurück",
                    modifier = Modifier.size(24.dp),
                )
            }
            Spacer(Modifier.width(8.dp))
            Text(
                text = title.ifBlank { "Künstler-Inhalte" },
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }

        when {
            itemsPage == null && isLoading -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(Modifier.height(10.dp))
                        Text("Titel werden geladen …")
                    }
                }
            }

            itemsPage == null && errorMessage != null -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier = Modifier.padding(24.dp),
                    ) {
                        Text(
                            text = errorMessage.orEmpty(),
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Button(onClick = viewModel::retry) { Text("Erneut laden") }
                    }
                }
            }

            itemsPage?.items.isNullOrEmpty() -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Keine Inhalte gefunden")
                        errorMessage?.let {
                            Spacer(Modifier.height(8.dp))
                            Text(it, color = MaterialTheme.colorScheme.error)
                        }
                        Spacer(Modifier.height(8.dp))
                        TextButton(onClick = viewModel::retry) { Text("Erneut laden") }
                    }
                }
            }

            else -> {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(bottom = 28.dp),
                ) {
                    itemsIndexed(
                        items = itemsPage?.items.orEmpty().distinctBy { it.id },
                        key = { index, item -> "embedded_artist_items_${item.id}_$index" },
                    ) { _, item ->
                        EmbeddedArtistDetailRow(
                            item = item,
                            active = mediaMetadata?.id == item.id,
                            playing = isPlaying,
                            onClick = {
                                when (item) {
                                    is SongItem, is EpisodeItem -> playFrom(item)
                                    is AlbumItem -> navController.navigate("album/${item.browseId}")
                                    is ArtistItem -> navController.navigate("artist/${item.id}")
                                    is PlaylistItem -> navController.navigate("online_playlist/${item.id}")
                                    is PodcastItem -> navController.navigate("online_podcast/${item.id}")
                                }
                            },
                        )
                    }
                    if (itemsPage?.continuation != null) {
                        item(key = "embedded_artist_items_more") {
                            Box(
                                modifier = Modifier.fillMaxWidth().padding(16.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                if (isLoading) {
                                    CircularProgressIndicator(modifier = Modifier.size(28.dp), strokeWidth = 2.dp)
                                } else {
                                    Button(onClick = viewModel::loadMore) { Text("Weitere laden") }
                                }
                            }
                        }
                    }
                    if (errorMessage != null && itemsPage != null) {
                        item(key = "embedded_artist_items_error") {
                            Text(
                                text = errorMessage.orEmpty(),
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.padding(18.dp),
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun EmbeddedArtistDetailRow(
    item: YTItem,
    active: Boolean,
    playing: Boolean,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick).padding(horizontal = 18.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        item.thumbnail?.let { thumbnail ->
            AsyncImage(
                model = thumbnail.resize(256, 256),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(58.dp).clip(RoundedCornerShape(8.dp)),
            )
            Spacer(Modifier.width(12.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(
                text = item.title,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            embeddedDetailSubtitle(item)?.takeIf { it.isNotBlank() }?.let { subtitle ->
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

private fun embeddedDetailSubtitle(item: YTItem): String? =
    when (item) {
        is SongItem -> item.artists.joinToString { it.name }
        is AlbumItem -> listOfNotNull(item.artists?.joinToString { it.name }, item.year?.toString()).joinToString(" • ")
        is ArtistItem -> "Künstler"
        is PlaylistItem -> item.author?.name ?: item.songCountText
        is PodcastItem -> item.author?.name ?: item.episodeCountText
        is EpisodeItem -> item.author?.name ?: item.publishDateText
    }
''',
    encoding="utf-8",
)

navigation = root / "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt"
replace_once(
    navigation,
    'import com.metrolist.music.ui.screens.artist.ArtistItemsScreen\n'
    'import com.metrolist.music.ui.screens.artist.ArtistScreen\n'
    'import com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n'
    'import com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n'
    'import com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n',
    'import com.metrolist.music.ui.screens.artist.ArtistItemsScreen\n'
    'import com.metrolist.music.ui.screens.artist.ArtistScreen\n'
    'import com.metrolist.music.ui.screens.artist.EmbeddedArtistItemsScreen\n'
    'import com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n',
)
replace_once(
    navigation,
    '''    ) {
        ArtistItemsScreen(navController)
    }

    composable(
        route = "online_playlist/{playlistId}",
''',
    '''    ) {
        if (embeddedInPlayer) {
            EmbeddedArtistItemsScreen(navController)
        } else {
            ArtistItemsScreen(navController)
        }
    }

    composable(
        route = "online_playlist/{playlistId}",
''',
)

print("Applied Dudu7 embedded artist-items round 3 patches")
