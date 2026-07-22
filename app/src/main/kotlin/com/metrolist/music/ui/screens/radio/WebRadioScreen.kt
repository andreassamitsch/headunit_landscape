/**
 * Web radio UI inspired by Transistor (MIT License)
 * https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.ui.screens.radio

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImage
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.radio.RadioBrowserClient
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationStore
import kotlinx.coroutines.launch
import java.util.UUID

enum class WebRadioSection {
    SAVED,
    SEARCH,
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WebRadioScreen() {
    val context = LocalContext.current
    val playerConnection = LocalPlayerConnection.current ?: return
    val store = remember(context) { RadioStationStore.get(context) }
    val savedStations by store.stations.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()

    var section by remember { mutableStateOf(WebRadioSection.SAVED) }
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<RadioStation>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var editingStation by remember { mutableStateOf<RadioStation?>(null) }
    var showAddDialog by remember { mutableStateOf(false) }

    fun playSaved(station: RadioStation) {
        val stations = savedStations.ifEmpty { listOf(station) }
        val startIndex = stations.indexOfFirst { it.uuid == station.uuid }.coerceAtLeast(0)
        playerConnection.playQueue(
            ListQueue(
                title = "WebRadio",
                items = stations.map { it.toMediaItem() },
                startIndex = startIndex,
            ),
        )
    }

    fun performSearch() {
        val cleaned = query.trim()
        if (cleaned.isBlank()) return
        scope.launch {
            isLoading = true
            errorMessage = null
            RadioBrowserClient.search(cleaned)
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
                leadingIcon = {
                    Icon(painterResource(R.drawable.favorite), contentDescription = null)
                },
            )
            FilterChip(
                selected = section == WebRadioSection.SEARCH,
                onClick = { section = WebRadioSection.SEARCH },
                label = { Text("Sender suchen") },
                leadingIcon = {
                    Icon(painterResource(R.drawable.search), contentDescription = null)
                },
            )
            Spacer(Modifier.weight(1f))
            IconButton(onClick = { showAddDialog = true }) {
                Icon(painterResource(R.drawable.add), contentDescription = "Sender per URL hinzufügen")
            }
        }

        when (section) {
            WebRadioSection.SAVED -> {
                if (savedStations.isEmpty()) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                painter = painterResource(R.drawable.radio),
                                contentDescription = null,
                                modifier = Modifier.size(48.dp),
                            )
                            Spacer(Modifier.height(8.dp))
                            Text("Noch keine Radiosender gespeichert", style = MaterialTheme.typography.titleMedium)
                            TextButton(onClick = { section = WebRadioSection.SEARCH }) {
                                Text("Sender suchen")
                            }
                        }
                    }
                } else {
                    LazyColumn(Modifier.fillMaxSize()) {
                        items(savedStations, key = { it.uuid }) { station ->
                            RadioStationRow(
                                station = station,
                                isSaved = true,
                                onPlay = { playSaved(station) },
                                onSave = {},
                                onEdit = { editingStation = station },
                                onDelete = { store.remove(station.uuid) },
                                onMoveUp = { store.move(station.uuid, -1) },
                                onMoveDown = { store.move(station.uuid, 1) },
                            )
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
                        label = { Text("Sender, Land oder Genre") },
                        leadingIcon = {
                            Icon(painterResource(R.drawable.search), contentDescription = null)
                        },
                        trailingIcon = {
                            IconButton(onClick = ::performSearch) {
                                Icon(painterResource(R.drawable.arrow_forward), contentDescription = "Suchen")
                            }
                        },
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        keyboardActions = KeyboardActions(onSearch = { performSearch() }),
                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    )

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
                        else -> LazyColumn(Modifier.fillMaxSize()) {
                            items(results, key = { it.uuid }) { station ->
                                RadioStationRow(
                                    station = station,
                                    isSaved = savedStations.any { it.uuid == station.uuid },
                                    onPlay = {
                                        playerConnection.playQueue(
                                            ListQueue(title = station.name, items = listOf(station.toMediaItem())),
                                        )
                                    },
                                    onSave = {
                                        store.addOrUpdate(station)
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
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

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
private fun RadioStationRow(
    station: RadioStation,
    isSaved: Boolean,
    onPlay: () -> Unit,
    onSave: () -> Unit,
    onEdit: (() -> Unit)? = null,
    onDelete: (() -> Unit)? = null,
    onMoveUp: (() -> Unit)? = null,
    onMoveDown: (() -> Unit)? = null,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier =
            Modifier
                .fillMaxWidth()
                .combinedClickable(onClick = onPlay, onLongClick = { onEdit?.invoke() })
                .padding(horizontal = 12.dp, vertical = 8.dp),
    ) {
        if (station.favicon.isNotBlank()) {
            AsyncImage(
                model = station.favicon,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.size(54.dp).clip(RoundedCornerShape(10.dp)),
            )
        } else {
            Box(
                Modifier.size(54.dp).clip(RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(painterResource(R.drawable.radio), contentDescription = null)
            }
        }

        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(
                station.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            val details =
                listOfNotNull(
                    station.country.takeIf { it.isNotBlank() },
                    station.tags.split(',').firstOrNull()?.trim()?.takeIf { it.isNotBlank() },
                    station.codec.takeIf { it.isNotBlank() }?.let { codec ->
                        if (station.bitrate > 0) "$codec · ${station.bitrate} kbps" else codec
                    },
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

        if (!isSaved) {
            IconButton(onClick = onSave) {
                Icon(painterResource(R.drawable.add_circle), contentDescription = "Speichern")
            }
        }
        onMoveUp?.let {
            IconButton(onClick = it) {
                Icon(painterResource(R.drawable.arrow_upward), contentDescription = "Nach oben")
            }
        }
        onMoveDown?.let {
            IconButton(onClick = it) {
                Icon(painterResource(R.drawable.arrow_downward), contentDescription = "Nach unten")
            }
        }
        onEdit?.let {
            IconButton(onClick = it) {
                Icon(painterResource(R.drawable.edit), contentDescription = "Bearbeiten")
            }
        }
        onDelete?.let {
            IconButton(onClick = it) {
                Icon(painterResource(R.drawable.delete), contentDescription = "Löschen")
            }
        }
    }
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
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Sendername") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = streamUrl,
                    onValueChange = { streamUrl = it },
                    label = { Text("Stream-, M3U- oder PLS-Adresse") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = favicon,
                    onValueChange = { favicon = it },
                    label = { Text("Senderbild (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
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
            ) {
                Text("Speichern")
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss) { Text("Abbrechen") }
        },
    )
}
