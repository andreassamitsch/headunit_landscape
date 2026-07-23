/**
 * Web radio UI inspired by Transistor (MIT License)
 * https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.ui.screens.radio

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.itemsIndexed
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImage
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.constants.LibraryViewType
import com.metrolist.music.constants.WebRadioViewTypeKey
import com.metrolist.music.extensions.move
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.radio.RadioBrowserClient
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationLogoResolver
import com.metrolist.music.radio.RadioStationStore
import com.metrolist.music.utils.rememberEnumPreference
import kotlinx.coroutines.launch
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.longPressDraggableHandle
import sh.calvin.reorderable.rememberReorderableLazyGridState
import sh.calvin.reorderable.rememberReorderableLazyListState
import java.util.UUID

enum class WebRadioSection {
    SAVED,
    SEARCH,
}

private enum class RadioFilterKind(val label: String) {
    COUNTRY("Land"),
    GENRE("Genre"),
    LANGUAGE("Sprache"),
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun WebRadioScreen() {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val playerConnection = LocalPlayerConnection.current ?: return
    val store = remember(context) { RadioStationStore.get(context) }
    val savedStations by store.stations.collectAsStateWithLifecycle()
    val currentMediaMetadata by playerConnection.mediaMetadata.collectAsStateWithLifecycle()
    val radioIsPlaying by playerConnection.isEffectivelyPlaying.collectAsStateWithLifecycle()
    val currentRadioMediaId = currentMediaMetadata?.id?.takeIf { it.startsWith("radio:") }
    val scope = rememberCoroutineScope()

    var section by remember { mutableStateOf(WebRadioSection.SAVED) }
    var viewType by rememberEnumPreference(WebRadioViewTypeKey, LibraryViewType.LIST)
    var query by remember { mutableStateOf("") }
    var countryFilter by remember { mutableStateOf("") }
    var genreFilter by remember { mutableStateOf("") }
    var languageFilter by remember { mutableStateOf("") }
    var editingFilter by remember { mutableStateOf<RadioFilterKind?>(null) }
    var results by remember { mutableStateOf<List<RadioStation>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var editingStation by remember { mutableStateOf<RadioStation?>(null) }
    var actionStation by remember { mutableStateOf<RadioStation?>(null) }
    var deletingStation by remember { mutableStateOf<RadioStation?>(null) }
    var showAddDialog by remember { mutableStateOf(false) }

    val orderedSavedStations = remember { mutableStateListOf<RadioStation>() }
    val savedListState = rememberLazyListState()
    val savedGridState = rememberLazyGridState()
    val listReorderState =
        rememberReorderableLazyListState(savedListState) { from, to ->
            if (from.index in orderedSavedStations.indices && to.index in orderedSavedStations.indices) {
                orderedSavedStations.move(from.index, to.index)
            }
        }
    val gridReorderState =
        rememberReorderableLazyGridState(savedGridState) { from, to ->
            if (from.index in orderedSavedStations.indices && to.index in orderedSavedStations.indices) {
                orderedSavedStations.move(from.index, to.index)
            }
        }
    val isDragging = listReorderState.isAnyItemDragging || gridReorderState.isAnyItemDragging
    var wasDragging by remember { mutableStateOf(false) }

    LaunchedEffect(savedStations, isDragging) {
        if (!isDragging && !wasDragging && orderedSavedStations.map { it.uuid } != savedStations.map { it.uuid }) {
            orderedSavedStations.clear()
            orderedSavedStations.addAll(savedStations)
        }
    }
    LaunchedEffect(isDragging) {
        if (wasDragging && !isDragging) {
            store.reorder(orderedSavedStations.map { it.uuid })
        }
        wasDragging = isDragging
    }

    fun playSaved(station: RadioStation) {
        val stations = savedStations.ifEmpty { listOf(station) }
        val effectiveStations = if (stations.any { it.uuid == station.uuid }) stations else stations + station
        val startIndex = effectiveStations.indexOfFirst { it.uuid == station.uuid }.coerceAtLeast(0)
        playerConnection.playQueue(
            queue =
                ListQueue(
                    title = "WebRadio",
                    items = effectiveStations.map { it.toMediaItem() },
                    startIndex = startIndex,
                ),
            notifyUserSelection = false,
        )
    }

    fun performSearch() {
        val filters =
            RadioBrowserClient.SearchFilters(
                country = countryFilter,
                genre = genreFilter,
                language = languageFilter,
            )
        if (query.isBlank() && filters.isEmpty) return
        scope.launch {
            isLoading = true
            errorMessage = null
            RadioBrowserClient.search(query, filters)
                .onSuccess { results = it }
                .onFailure { errorMessage = it.message ?: "Sendersuche fehlgeschlagen" }
            isLoading = false
        }
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            FilterChip(
                selected = section == WebRadioSection.SAVED,
                onClick = { section = WebRadioSection.SAVED },
                label = { Text("Gespeichert") },
                leadingIcon = { Icon(painterResource(R.drawable.favorite), contentDescription = null) },
            )
            FilterChip(
                selected = section == WebRadioSection.SEARCH,
                onClick = { section = WebRadioSection.SEARCH },
                label = { Text("Sender suchen") },
                leadingIcon = { Icon(painterResource(R.drawable.search), contentDescription = null) },
            )
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { viewType = viewType.toggle() }) {
                Icon(
                    painter = painterResource(if (viewType == LibraryViewType.LIST) R.drawable.grid_view else R.drawable.list),
                    contentDescription = if (viewType == LibraryViewType.LIST) "Kachelansicht" else "Listenansicht",
                )
            }
            IconButton(onClick = { showAddDialog = true }) {
                Icon(painterResource(R.drawable.add), contentDescription = "Sender per URL hinzufügen")
            }
        }

        when (section) {
            WebRadioSection.SAVED -> {
                if (orderedSavedStations.isEmpty()) {
                    EmptySavedStations(onSearch = { section = WebRadioSection.SEARCH })
                } else if (viewType == LibraryViewType.LIST) {
                    LazyColumn(
                        state = savedListState,
                        contentPadding = PaddingValues(bottom = 12.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        itemsIndexed(orderedSavedStations, key = { _, station -> station.uuid }) { _, station ->
                            ReorderableItem(listReorderState, key = station.uuid) {
                                val isActive = currentRadioMediaId == station.mediaId
                                RadioStationRow(
                                    station = station,
                                    isSaved = true,
                                    isActive = isActive,
                                    isPlaying = isActive && radioIsPlaying,
                                    onPlay = { if (isActive) playerConnection.togglePlayPause() else playSaved(station) },
                                    onSave = {},
                                    onLongClick = { actionStation = station },
                                    dragHandleModifier =
                                        Modifier.longPressDraggableHandle(
                                            onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                        ),
                                    onLogoResolved = store::addOrUpdate,
                                )
                            }
                        }
                    }
                } else {
                    LazyVerticalGrid(
                        state = savedGridState,
                        columns = GridCells.Adaptive(142.dp),
                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        itemsIndexed(orderedSavedStations, key = { _, station -> station.uuid }) { _, station ->
                            ReorderableItem(gridReorderState, key = station.uuid) {
                                val isActive = currentRadioMediaId == station.mediaId
                                RadioStationCard(
                                    station = station,
                                    isSaved = true,
                                    isActive = isActive,
                                    isPlaying = isActive && radioIsPlaying,
                                    onPlay = { if (isActive) playerConnection.togglePlayPause() else playSaved(station) },
                                    onSave = {},
                                    onLongClick = { actionStation = station },
                                    dragHandleModifier =
                                        Modifier.longPressDraggableHandle(
                                            onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                        ),
                                    onLogoResolved = store::addOrUpdate,
                                )
                            }
                        }
                    }
                }
            }

            WebRadioSection.SEARCH -> {
                Column(Modifier.fillMaxSize()) {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        singleLine = true,
                        label = { Text("Sender oder freier Suchbegriff") },
                        leadingIcon = { Icon(painterResource(R.drawable.search), contentDescription = null) },
                        trailingIcon = {
                            IconButton(onClick = ::performSearch) {
                                Icon(painterResource(R.drawable.arrow_forward), contentDescription = "Suchen")
                            }
                        },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { performSearch() }),
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    )
                    LazyRow(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 4.dp),
                    ) {
                        item {
                            FilterChip(
                                selected = countryFilter.isNotBlank(),
                                onClick = { editingFilter = RadioFilterKind.COUNTRY },
                                label = { Text(countryFilter.ifBlank { "Land" }, maxLines = 1) },
                            )
                        }
                        item {
                            FilterChip(
                                selected = genreFilter.isNotBlank(),
                                onClick = { editingFilter = RadioFilterKind.GENRE },
                                label = { Text(genreFilter.ifBlank { "Genre" }, maxLines = 1) },
                            )
                        }
                        item {
                            FilterChip(
                                selected = languageFilter.isNotBlank(),
                                onClick = { editingFilter = RadioFilterKind.LANGUAGE },
                                label = { Text(languageFilter.ifBlank { "Sprache" }, maxLines = 1) },
                            )
                        }
                        if (countryFilter.isNotBlank() || genreFilter.isNotBlank() || languageFilter.isNotBlank()) {
                            item {
                                TextButton(
                                    onClick = {
                                        countryFilter = ""
                                        genreFilter = ""
                                        languageFilter = ""
                                    },
                                ) { Text("Filter löschen") }
                            }
                        }
                    }

                    when {
                        isLoading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                        errorMessage != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(errorMessage.orEmpty(), color = MaterialTheme.colorScheme.error)
                        }
                        results.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text("Nach Radiosendern suchen")
                        }
                        viewType == LibraryViewType.LIST -> LazyColumn(Modifier.fillMaxSize()) {
                            items(results, key = { it.uuid }) { station ->
                                val isActive = currentRadioMediaId == station.mediaId
                                RadioStationRow(
                                    station = station,
                                    isSaved = savedStations.any { it.uuid == station.uuid },
                                    isActive = isActive,
                                    isPlaying = isActive && radioIsPlaying,
                                    onPlay = {
                                        if (isActive) playerConnection.togglePlayPause() else {
                                            playerConnection.playQueue(
                                                queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                                notifyUserSelection = false,
                                            )
                                        }
                                    },
                                    onSave = { store.addOrUpdate(station) },
                                    onLongClick = {},
                                    onLogoResolved = { enriched ->
                                        results = results.map { if (it.uuid == enriched.uuid) enriched else it }
                                        if (savedStations.any { it.uuid == enriched.uuid }) store.addOrUpdate(enriched)
                                    },
                                )
                            }
                        }
                        else -> LazyVerticalGrid(
                            columns = GridCells.Adaptive(142.dp),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxSize(),
                        ) {
                            items(results, key = { it.uuid }) { station ->
                                val isActive = currentRadioMediaId == station.mediaId
                                RadioStationCard(
                                    station = station,
                                    isSaved = savedStations.any { it.uuid == station.uuid },
                                    isActive = isActive,
                                    isPlaying = isActive && radioIsPlaying,
                                    onPlay = {
                                        if (isActive) playerConnection.togglePlayPause() else {
                                            playerConnection.playQueue(
                                                queue = ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                                notifyUserSelection = false,
                                            )
                                        }
                                    },
                                    onSave = { store.addOrUpdate(station) },
                                    onLongClick = {},
                                    onLogoResolved = { enriched ->
                                        results = results.map { if (it.uuid == enriched.uuid) enriched else it }
                                        if (savedStations.any { it.uuid == enriched.uuid }) store.addOrUpdate(enriched)
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    editingFilter?.let { kind ->
        val current = when (kind) {
            RadioFilterKind.COUNTRY -> countryFilter
            RadioFilterKind.GENRE -> genreFilter
            RadioFilterKind.LANGUAGE -> languageFilter
        }
        RadioSearchFilterDialog(
            kind = kind,
            initial = current,
            onDismiss = { editingFilter = null },
            onApply = { value ->
                when (kind) {
                    RadioFilterKind.COUNTRY -> countryFilter = value
                    RadioFilterKind.GENRE -> genreFilter = value
                    RadioFilterKind.LANGUAGE -> languageFilter = value
                }
                editingFilter = null
            },
        )
    }

    actionStation?.let { station ->
        AlertDialog(
            onDismissRequest = { actionStation = null },
            title = { Text(station.name) },
            text = { Text("Aktion für diesen Radiosender auswählen") },
            confirmButton = {
                Button(
                    onClick = {
                        actionStation = null
                        editingStation = station
                    },
                ) { Text("Bearbeiten") }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        actionStation = null
                        deletingStation = station
                    },
                ) { Text("Löschen", color = MaterialTheme.colorScheme.error) }
            },
        )
    }

    deletingStation?.let { station ->
        AlertDialog(
            onDismissRequest = { deletingStation = null },
            title = { Text("Radiosender löschen?") },
            text = { Text("${station.name} wird aus den Favoriten entfernt.") },
            confirmButton = {
                Button(
                    onClick = {
                        store.remove(station.uuid)
                        deletingStation = null
                    },
                ) { Text("Löschen") }
            },
            dismissButton = { OutlinedButton(onClick = { deletingStation = null }) { Text("Abbrechen") } },
        )
    }

    if (showAddDialog || editingStation != null) {
        RadioStationEditorDialog(
            initial = editingStation,
            onDismiss = {
                showAddDialog = false
                editingStation = null
            },
            onSave = { draft ->
                scope.launch {
                    isLoading = true
                    RadioBrowserClient.resolveStreamUrl(draft.streamUrl)
                        .onSuccess { resolved ->
                            val station = draft.copy(streamUrl = resolved)
                            store.addOrUpdate(station)
                            showAddDialog = false
                            editingStation = null
                            section = WebRadioSection.SAVED
                            playSaved(station)
                        }
                        .onFailure { errorMessage = it.message ?: "Stream konnte nicht geöffnet werden" }
                    isLoading = false
                }
            },
        )
    }
}

@Composable
private fun EmptySavedStations(onSearch: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(painter = painterResource(R.drawable.radio), contentDescription = null, modifier = Modifier.size(48.dp))
            Spacer(Modifier.height(8.dp))
            Text("Noch keine Radiosender gespeichert", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = onSearch) { Text("Sender suchen") }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun RadioStationRow(
    station: RadioStation,
    isSaved: Boolean,
    isActive: Boolean,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onSave: () -> Unit,
    onLongClick: () -> Unit,
    dragHandleModifier: Modifier = Modifier,
    onLogoResolved: (RadioStation) -> Unit = {},
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(horizontal = 6.dp, vertical = 2.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.48f) else MaterialTheme.colorScheme.surface)
                .combinedClickable(onClick = onPlay, onLongClick = onLongClick)
                .padding(horizontal = 10.dp, vertical = 8.dp),
    ) {
        RadioStationArtwork(station, 54, dragHandleModifier, onLogoResolved)
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            StationTitle(station, isActive, isPlaying)
            StationDetails(station)
        }
        if (!isSaved) {
            IconButton(onClick = onSave) {
                Icon(painterResource(R.drawable.add_circle), contentDescription = "Speichern")
            }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun RadioStationCard(
    station: RadioStation,
    isSaved: Boolean,
    isActive: Boolean,
    isPlaying: Boolean,
    onPlay: () -> Unit,
    onSave: () -> Unit,
    onLongClick: () -> Unit,
    dragHandleModifier: Modifier = Modifier,
    onLogoResolved: (RadioStation) -> Unit = {},
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier =
            Modifier
                .fillMaxWidth()
                .aspectRatio(0.86f)
                .clip(RoundedCornerShape(14.dp))
                .background(if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f))
                .combinedClickable(onClick = onPlay, onLongClick = onLongClick)
                .padding(10.dp),
    ) {
        Box(contentAlignment = Alignment.TopEnd) {
            RadioStationArtwork(station, 88, dragHandleModifier, onLogoResolved)
            if (!isSaved) {
                IconButton(onClick = onSave, modifier = Modifier.align(Alignment.TopEnd).size(34.dp)) {
                    Icon(painterResource(R.drawable.add_circle), contentDescription = "Speichern")
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            station.name,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        if (isActive) {
            Text(
                if (isPlaying) "● LÄUFT" else "PAUSIERT",
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
        } else {
            StationDetails(station, compact = true)
        }
    }
}

@Composable
private fun RadioStationArtwork(
    station: RadioStation,
    size: Int,
    modifier: Modifier,
    onLogoResolved: (RadioStation) -> Unit,
) {
    var artworkUrl by remember(station.uuid, station.favicon) { mutableStateOf(station.favicon) }
    LaunchedEffect(station.uuid, station.homepage) {
        RadioStationLogoResolver.resolve(station)?.let { resolved ->
            artworkUrl = resolved
            if (resolved != station.favicon) onLogoResolved(station.copy(favicon = resolved))
        }
    }
    if (artworkUrl.isNotBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo ${station.name}; lange drücken und ziehen zum Sortieren",
            contentScale = ContentScale.Crop,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier = modifier.size(size.dp).clip(RoundedCornerShape(10.dp)),
        )
    } else {
        val initials = remember(station.name) {
            station.name.trim().split(' ').filter { it.isNotBlank() }.take(2)
                .joinToString("") { it.first().uppercaseChar().toString() }.ifBlank { "R" }
        }
        Box(
            modifier.size(size.dp).clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surfaceVariant),
            contentAlignment = Alignment.Center,
        ) {
            Text(initials, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun StationTitle(station: RadioStation, isActive: Boolean, isPlaying: Boolean) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            station.name,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        if (isActive) {
            Text(
                if (isPlaying) "● LÄUFT" else "PAUSIERT",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = if (isPlaying) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun StationDetails(station: RadioStation, compact: Boolean = false) {
    val details =
        listOfNotNull(
            station.country.takeIf { it.isNotBlank() },
            station.tags.split(',').firstOrNull()?.trim()?.takeIf { it.isNotBlank() },
            if (!compact) station.codec.takeIf { it.isNotBlank() }?.let { if (station.bitrate > 0) "$it · ${station.bitrate} kbps" else it } else null,
        ).joinToString(" · ")
    if (details.isNotBlank()) {
        Text(
            details,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun RadioSearchFilterDialog(
    kind: RadioFilterKind,
    initial: String,
    onDismiss: () -> Unit,
    onApply: (String) -> Unit,
) {
    var value by remember(kind, initial) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("${kind.label} filtern") },
        text = {
            OutlinedTextField(
                value = value,
                onValueChange = { value = it },
                label = { Text(kind.label) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onApply(value.trim()) }),
                modifier = Modifier.fillMaxWidth(),
            )
        },
        confirmButton = { Button(onClick = { onApply(value.trim()) }) { Text("Übernehmen") } },
        dismissButton = {
            Row {
                TextButton(onClick = { onApply("") }) { Text("Löschen") }
                TextButton(onClick = onDismiss) { Text("Abbrechen") }
            }
        },
    )
}

@Composable
private fun RadioStationEditorDialog(
    initial: RadioStation?,
    onDismiss: () -> Unit,
    onSave: (RadioStation) -> Unit,
) {
    var name by remember(initial) { mutableStateOf(initial?.name.orEmpty()) }
    var streamUrl by remember(initial) { mutableStateOf(initial?.streamUrl.orEmpty()) }
    var favicon by remember(initial) { mutableStateOf(initial?.favicon.orEmpty()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "Radiosender hinzufügen" else "Radiosender bearbeiten") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Sendername") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = streamUrl, onValueChange = { streamUrl = it }, label = { Text("Stream-, M3U- oder PLS-Adresse") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = favicon, onValueChange = { favicon = it }, label = { Text("Senderbild (optional)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            Button(
                enabled = name.isNotBlank() && streamUrl.isNotBlank(),
                onClick = {
                    onSave(
                        (initial ?: RadioStation(UUID.randomUUID().toString(), name.trim(), streamUrl.trim()))
                            .copy(name = name.trim(), streamUrl = streamUrl.trim(), favicon = favicon.trim()),
                    )
                },
            ) { Text("Speichern") }
        },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
