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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.extensions.move
import com.metrolist.music.radio.fyt.FmPresetOrderStore
import com.metrolist.music.radio.fyt.FmStationArtwork
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import kotlinx.coroutines.delay
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState

private enum class PhysicalRadioSection {
    FAVOURITES,
    SEARCH,
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun PhysicalRadioScreen() {
    val context = LocalContext.current
    val haptic = LocalHapticFeedback.current
    val playerConnection = LocalPlayerConnection.current
    val radio = remember(context) { FytPhysicalRadio.get(context) }
    val state by radio.state.collectAsStateWithLifecycle()

    var section by remember { mutableStateOf(PhysicalRadioSection.FAVOURITES) }
    var frequencyInput by remember { mutableStateOf(FytPhysicalRadio.formatFrequency(state.frequency)) }

    val orderedPresets = remember { mutableStateListOf<FytPhysicalRadio.Preset>() }
    val listState = rememberLazyListState()
    val reorderState =
        rememberReorderableLazyListState(listState) { from, to ->
            if (from.index in orderedPresets.indices && to.index in orderedPresets.indices) {
                orderedPresets.move(from.index, to.index)
            }
        }
    val isDragging = reorderState.isAnyItemDragging
    var wasDragging by remember { mutableStateOf(false) }

    LaunchedEffect(state.frequency) {
        frequencyInput = FytPhysicalRadio.formatFrequency(state.frequency)
    }

    LaunchedEffect(state.presets, isDragging) {
        if (!isDragging && !wasDragging) {
            val ordered = FmPresetOrderStore.ordered(context, state.presets)
            if (orderedPresets.map { it.frequency } != ordered.map { it.frequency }) {
                orderedPresets.clear()
                orderedPresets.addAll(ordered)
            }
        }
    }

    LaunchedEffect(isDragging) {
        if (wasDragging && !isDragging) {
            FmPresetOrderStore.persist(context, orderedPresets)
        }
        wasDragging = isDragging
    }

    Column(Modifier.fillMaxSize()) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            FilterChip(
                selected = section == PhysicalRadioSection.FAVOURITES,
                onClick = { section = PhysicalRadioSection.FAVOURITES },
                label = { Text("Favoriten") },
                leadingIcon = { Icon(painterResource(R.drawable.favorite), contentDescription = null) },
            )
            FilterChip(
                selected = section == PhysicalRadioSection.SEARCH,
                onClick = { section = PhysicalRadioSection.SEARCH },
                label = { Text("Sendersuche") },
                leadingIcon = { Icon(painterResource(R.drawable.search), contentDescription = null) },
            )
            Spacer(Modifier.weight(1f))
            if (state.isBusy) CircularProgressIndicator(Modifier.size(28.dp))
        }

        when (section) {
            PhysicalRadioSection.FAVOURITES -> {
                if (orderedPresets.isEmpty()) {
                    EmptyFmFavourites(onOpenSearch = { section = PhysicalRadioSection.SEARCH })
                } else {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(5.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        itemsIndexed(
                            items = orderedPresets,
                            key = { _, preset -> "fm-${(preset.frequency * 10).toInt()}" },
                        ) { _, preset ->
                            ReorderableItem(reorderState, key = "fm-${(preset.frequency * 10).toInt()}") {
                                val isActive =
                                    state.isActive &&
                                        FmPresetOrderStore.sameFrequency(state.frequency, preset.frequency)
                                FmFavouriteRow(
                                    preset = preset,
                                    isActive = isActive,
                                    isMuted = isActive && state.isMuted,
                                    onPlay = {
                                        if (isActive) {
                                            radio.toggleMute()
                                        } else {
                                            playerConnection?.pause()
                                            radio.tune(preset.frequency)
                                        }
                                    },
                                    onDelete = {
                                        val remaining = orderedPresets.filterNot {
                                            FmPresetOrderStore.sameFrequency(it.frequency, preset.frequency)
                                        }
                                        orderedPresets.clear()
                                        orderedPresets.addAll(remaining)
                                        FmPresetOrderStore.persist(context, remaining)
                                        radio.removePreset(preset.frequency)
                                    },
                                    dragHandle = {
                                        IconButton(
                                            onClick = {},
                                            modifier =
                                                Modifier
                                                    .draggableHandle(
                                                        onDragStarted = {
                                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                        },
                                                    ).size(44.dp),
                                        ) {
                                            Icon(
                                                painter = painterResource(R.drawable.drag_handle),
                                                contentDescription = "Sender verschieben",
                                            )
                                        }
                                    },
                                )
                            }
                        }
                    }
                }
            }

            PhysicalRadioSection.SEARCH -> {
                PhysicalRadioSearchPanel(
                    radio = radio,
                    frequencyInput = frequencyInput,
                    onFrequencyInputChange = { frequencyInput = it.replace(',', '.') },
                    onTune = {
                        frequencyInput.toFloatOrNull()?.let { frequency ->
                            playerConnection?.pause()
                            radio.tune(frequency)
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun EmptyFmFavourites(onOpenSearch: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(52.dp),
            )
            Spacer(Modifier.height(8.dp))
            Text("Noch keine FM-Sender gespeichert", style = MaterialTheme.typography.titleMedium)
            TextButton(onClick = onOpenSearch) { Text("Sender suchen") }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun FmFavouriteRow(
    preset: FytPhysicalRadio.Preset,
    isActive: Boolean,
    isMuted: Boolean,
    onPlay: () -> Unit,
    onDelete: () -> Unit,
    dragHandle: @Composable () -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(
                    if (isActive) {
                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
                    } else {
                        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)
                    },
                ).combinedClickable(onClick = onPlay, onLongClick = onPlay)
                .padding(horizontal = 10.dp, vertical = 8.dp),
    ) {
        FmStationArtwork(
            stationName = preset.name,
            frequency = preset.frequency,
            size = 56.dp,
        )
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(
                text = preset.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = "${FytPhysicalRadio.formatFrequency(preset.frequency)} MHz",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (isActive) {
            Text(
                text = if (isMuted) "STUMM" else "● LÄUFT",
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(end = 4.dp),
            )
        }
        IconButton(onClick = onDelete) {
            Icon(painterResource(R.drawable.delete), contentDescription = "Favorit löschen")
        }
        dragHandle()
    }
}

@Composable
private fun PhysicalRadioSearchPanel(
    radio: FytPhysicalRadio,
    frequencyInput: String,
    onFrequencyInputChange: (String) -> Unit,
    onTune: () -> Unit,
) {
    val context = LocalContext.current
    val playerConnection = LocalPlayerConnection.current
    val state by radio.state.collectAsStateWithLifecycle()
    val isFavourite =
        state.presets.any { FmPresetOrderStore.sameFrequency(it.frequency, state.frequency) }

    LazyColumn(
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(9.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        item {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                FmStationArtwork(
                    stationName = state.displayStation,
                    frequency = state.frequency,
                    size = 82.dp,
                )
                Column(Modifier.weight(1f)) {
                    Text(
                        text = state.displayStation,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = state.rt.ifBlank { "Physischer Antennenempfang" },
                        style = MaterialTheme.typography.bodyLarge,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }

        item {
            Text(
                text =
                    buildString {
                        append("${FytPhysicalRadio.formatFrequency(state.frequency)} MHz")
                        append("  •  RSSI ${state.rssi}")
                        append(if (state.stereo) "  •  Stereo" else "  •  Mono")
                        if (state.pi != 0) append("  •  PI ${state.pi.toString(16).uppercase()}")
                        if (state.pty != 0) append("  •  PTY ${state.pty}")
                        if (state.tp) append("  •  TP")
                        if (state.ta) append("  •  TA")
                    },
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        state.error?.let { error ->
            item {
                Text(
                    text = error,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }

        item {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedTextField(
                    value = frequencyInput,
                    onValueChange = onFrequencyInputChange,
                    label = { Text("Frequenz") },
                    suffix = { Text("MHz") },
                    singleLine = true,
                    keyboardOptions =
                        KeyboardOptions(
                            keyboardType = KeyboardType.Decimal,
                            imeAction = ImeAction.Done,
                        ),
                    keyboardActions = KeyboardActions(onDone = { onTune() }),
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = onTune, enabled = !state.isBusy) {
                    Text("EINSTELLEN")
                }
            }
        }

        item {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Button(
                    onClick = {
                        if (state.isActive) {
                            radio.powerOff()
                        } else {
                            playerConnection?.pause()
                            radio.powerOn()
                        }
                    },
                    enabled = !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(
                        painter = painterResource(if (state.isActive) R.drawable.stop else R.drawable.play),
                        contentDescription = null,
                    )
                    Text(if (state.isActive) "AUS" else "RADIO EIN", modifier = Modifier.padding(start = 6.dp))
                }
                OutlinedButton(
                    onClick = radio::toggleMute,
                    enabled = state.isActive && !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(
                        painter = painterResource(if (state.isMuted) R.drawable.volume_off else R.drawable.volume_up),
                        contentDescription = null,
                    )
                    Text(if (state.isMuted) "STUMM" else "TON", modifier = Modifier.padding(start = 6.dp))
                }
                OutlinedButton(
                    onClick = {
                        if (isFavourite) {
                            val remaining = state.presets.filterNot {
                                FmPresetOrderStore.sameFrequency(it.frequency, state.frequency)
                            }
                            radio.removePreset(state.frequency)
                            FmPresetOrderStore.persist(context, remaining)
                        } else {
                            radio.saveCurrentPreset()
                        }
                    },
                    enabled = state.isActive,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(
                        painter = painterResource(if (isFavourite) R.drawable.favorite else R.drawable.favorite_border),
                        contentDescription = null,
                    )
                    Text(if (isFavourite) "ENTFERNEN" else "MERKEN", modifier = Modifier.padding(start = 6.dp))
                }
            }
        }

        item {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedButton(
                    onClick = { radio.seek(false) },
                    enabled = state.isActive && !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) { Text("SEEK ◀") }
                OutlinedButton(
                    onClick = { radio.step(false) },
                    enabled = !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) { Text("− 0,1") }
                OutlinedButton(
                    onClick = { radio.step(true) },
                    enabled = !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) { Text("+ 0,1") }
                OutlinedButton(
                    onClick = { radio.seek(true) },
                    enabled = state.isActive && !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) { Text("SEEK ▶") }
                OutlinedButton(
                    onClick = radio::enableRds,
                    enabled = state.isActive,
                    modifier = Modifier.weight(1f),
                ) { Text("RDS") }
            }
        }

        item { HorizontalDivider() }
        item {
            Text(
                text =
                    "FYT ${state.platform.ifBlank { "Dudu7" }} • " +
                        "radio_type=${state.radioType.ifBlank { "?" }} • " +
                        "libfmjni=${if (state.libraryLoaded) "bereit" else "fehlt"}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            Spacer(Modifier.height(2.dp))
            LaunchedEffect(state.frequency, state.ps) {
                if (state.ps.isNotBlank()) delay(250)
            }
        }
    }
}
