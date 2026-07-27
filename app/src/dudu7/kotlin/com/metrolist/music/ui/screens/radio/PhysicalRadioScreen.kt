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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
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
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState
import kotlin.math.roundToInt

private enum class PhysicalRadioSection {
    FAVOURITES,
    SCAN,
    MANUAL,
    SETTINGS,
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
    var editingPreset by remember { mutableStateOf<FytPhysicalRadio.Preset?>(null) }

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
            if (orderedPresets != ordered) {
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
        LazyRow(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            item {
                FilterChip(
                    selected = section == PhysicalRadioSection.FAVOURITES,
                    onClick = { section = PhysicalRadioSection.FAVOURITES },
                    label = { Text("Favoriten") },
                    leadingIcon = { Icon(painterResource(R.drawable.favorite), contentDescription = null) },
                )
            }
            item {
                FilterChip(
                    selected = section == PhysicalRadioSection.SCAN,
                    onClick = { section = PhysicalRadioSection.SCAN },
                    label = { Text("Sendersuchlauf") },
                    leadingIcon = { Icon(painterResource(R.drawable.search), contentDescription = null) },
                )
            }
            item {
                FilterChip(
                    selected = section == PhysicalRadioSection.MANUAL,
                    onClick = { section = PhysicalRadioSection.MANUAL },
                    label = { Text("Manuell") },
                )
            }
            item {
                FilterChip(
                    selected = section == PhysicalRadioSection.SETTINGS,
                    onClick = { section = PhysicalRadioSection.SETTINGS },
                    label = { Text("Radiofunktionen") },
                )
            }
            if (state.isBusy && !state.isScanning) {
                item { CircularProgressIndicator(Modifier.size(28.dp)) }
            }
        }

        when (section) {
            PhysicalRadioSection.FAVOURITES -> {
                if (orderedPresets.isEmpty()) {
                    EmptyFmFavourites(onOpenSearch = { section = PhysicalRadioSection.SCAN })
                } else {
                    LazyColumn(
                        state = listState,
                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),
                        verticalArrangement = Arrangement.spacedBy(5.dp),
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        itemsIndexed(
                            items = orderedPresets,
                            key = { _, preset -> FytPhysicalRadio.stablePresetKey(preset) },
                        ) { _, preset ->
                            ReorderableItem(reorderState, key = FytPhysicalRadio.stablePresetKey(preset)) {
                                val isActive =
                                    state.isActive &&
                                        FytPhysicalRadio.presetMatches(preset, state.frequency, state.pi)
                                FmFavouriteRow(
                                    preset = preset,
                                    pi = if (isActive && state.pi > 0) state.pi else preset.pi,
                                    isActive = isActive,
                                    onPlay = {
                                        if (!isActive) {
                                            playerConnection?.pause()
                                            radio.tunePreset(preset)
                                        }
                                    },
                                    onEdit = { editingPreset = preset },
                                    onDelete = {
                                        val remaining = orderedPresets.filterNot { it == preset }
                                        orderedPresets.clear()
                                        orderedPresets.addAll(remaining)
                                        FmPresetOrderStore.persist(context, remaining)
                                        radio.removePreset(preset)
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

            PhysicalRadioSection.SCAN -> {
                FmAutoScanPanel(
                    radio = radio,
                    onSaved = { section = PhysicalRadioSection.FAVOURITES },
                )
            }

            PhysicalRadioSection.MANUAL -> {
                PhysicalRadioManualPanel(
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

            PhysicalRadioSection.SETTINGS -> {
                PhysicalRadioSettingsPanel(radio)
            }
        }
    }

    editingPreset?.let { preset ->
        FmPresetEditorDialog(
            preset = preset,
            onDismiss = { editingPreset = null },
            onSave = { name, frequencies ->
                if (radio.updatePreset(preset, name, frequencies)) {
                    editingPreset = null
                }
            },
        )
    }
}


@Composable
private fun FmPresetEditorDialog(
    preset: FytPhysicalRadio.Preset,
    onDismiss: () -> Unit,
    onSave: (String, List<Float>) -> Unit,
) {
    var name by remember(preset) { mutableStateOf(preset.name) }
    var frequencies by
        remember(preset) {
            mutableStateOf(
                FytPhysicalRadio
                    .presetFrequencies(preset)
                    .joinToString("; ") { FytPhysicalRadio.formatFrequency(it) },
            )
        }
    var error by remember(preset) { mutableStateOf<String?>(null) }

    fun submit() {
        val tokens =
            frequencies
                .split(';', ',')
                .map(String::trim)
                .filter(String::isNotBlank)
        val parsed = tokens.mapNotNull { value -> value.replace(',', '.').toFloatOrNull() }
        when {
            name.isBlank() -> error = "Sendername fehlt"
            parsed.size != tokens.size -> error = "Mindestens eine Frequenz ist ungültig"
            parsed.isEmpty() -> error = "Mindestens eine Frequenz angeben"
            parsed.any { it !in 87.5f..108.0f } -> error = "Frequenzen müssen zwischen 87,5 und 108,0 MHz liegen"
            else -> onSave(name.trim(), parsed)
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("FM-Favorit bearbeiten") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Sendername") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = frequencies,
                    onValueChange = { frequencies = it },
                    label = { Text("Frequenzen, durch Semikolon getrennt") },
                    supportingText = { Text("Beispiel: 99,4; 103,2") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { Button(onClick = ::submit) { Text("Speichern") } },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
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
            TextButton(onClick = onOpenSearch) { Text("Automatischen Suchlauf starten") }
        }
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun FmFavouriteRow(
    preset: FytPhysicalRadio.Preset,
    pi: Int,
    isActive: Boolean,
    onPlay: () -> Unit,
    onEdit: () -> Unit,
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
                ).combinedClickable(onClick = onPlay, onLongClick = onEdit)
                .padding(horizontal = 10.dp, vertical = 8.dp),
    ) {
        FmStationArtwork(
            stationName = preset.name,
            frequency = preset.frequency,
            pi = pi,
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
                text = FytPhysicalRadio.formatFrequencies(FytPhysicalRadio.presetFrequencies(preset)),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (isActive) {
            Text(
                text = "● LÄUFT",
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
private fun FmAutoScanPanel(
    radio: FytPhysicalRadio,
    onSaved: () -> Unit,
) {
    val playerConnection = LocalPlayerConnection.current
    val state by radio.state.collectAsStateWithLifecycle()
    val selected = remember { mutableStateMapOf<Int, Boolean>() }

    LaunchedEffect(state.scanResults) {
        state.scanResults.forEach { result ->
            selected.putIfAbsent((result.frequency * 10).roundToInt(), true)
        }
        val validKeys = state.scanResults.map { (it.frequency * 10).roundToInt() }.toSet()
        selected.keys.toList().filterNot { it in validKeys }.forEach(selected::remove)
    }

    val selectedResults =
        state.scanResults.filter {
            selected[(it.frequency * 10).roundToInt()] == true
        }

    LazyColumn(
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        item {
            Text(
                "Automatischer FM-Sendersuchlauf",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                "Das gesamte UKW-Band wird geprüft. Gefundene Sender werden erst nach deiner Auswahl als Favoriten gespeichert.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            if (state.isScanning) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    LinearProgressIndicator(
                        progress = { state.scanProgress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        "${(state.scanProgress * 100).roundToInt()} %  •  " +
                            "${FytPhysicalRadio.formatFrequency(state.frequency)} MHz  •  " +
                            "${state.scanResults.size} Sender",
                        style = MaterialTheme.typography.labelLarge,
                    )
                    OutlinedButton(
                        onClick = radio::stopAutoScan,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("SUCHLAUF ABBRECHEN")
                    }
                }
            } else {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Button(
                        onClick = {
                            playerConnection?.pause()
                            radio.startAutoScan()
                        },
                        enabled = state.libraryLoaded,
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(painterResource(R.drawable.search), contentDescription = null)
                        Text(
                            if (state.scanResults.isEmpty()) "SUCHLAUF STARTEN" else "NEU SUCHEN",
                            modifier = Modifier.padding(start = 6.dp),
                        )
                    }
                    if (state.scanResults.isNotEmpty()) {
                        OutlinedButton(onClick = radio::clearScanResults) {
                            Text("LEEREN")
                        }
                    }
                }
            }
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

        if (!state.isScanning && state.scanResults.isEmpty()) {
            item {
                Box(
                    modifier = Modifier.fillMaxWidth().height(180.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        "Noch keine Suchergebnisse",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        if (state.scanResults.isNotEmpty()) {
            item {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        "${state.scanResults.size} Sender gefunden",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(
                        onClick = {
                            state.scanResults.forEach {
                                selected[(it.frequency * 10).roundToInt()] = true
                            }
                        },
                    ) { Text("Alle") }
                    TextButton(onClick = { selected.keys.forEach { selected[it] = false } }) {
                        Text("Keine")
                    }
                }
            }

            items(
                items = state.scanResults,
                key = { "scan-${(it.frequency * 10).roundToInt()}" },
            ) { result ->
                val key = (result.frequency * 10).roundToInt()
                FmScanResultRow(
                    result = result,
                    checked = selected[key] == true,
                    onCheckedChange = { selected[key] = it },
                    onPreview = {
                        playerConnection?.pause()
                        radio.tune(result.frequency)
                    },
                )
            }

            item {
                Button(
                    onClick = {
                        radio.saveScanResults(selectedResults)
                        onSaved()
                    },
                    enabled = selectedResults.isNotEmpty() && !state.isScanning,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("${selectedResults.size} AUSGEWÄHLTE SENDER HINZUFÜGEN")
                }
            }
        }
    }
}

@Composable
private fun FmScanResultRow(
    result: FytPhysicalRadio.ScanResult,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    onPreview: () -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f))
                .combinedClickable(onClick = onPreview, onLongClick = { onCheckedChange(!checked) })
                .padding(horizontal = 8.dp, vertical = 8.dp),
    ) {
        Checkbox(checked = checked, onCheckedChange = onCheckedChange)
        FmStationArtwork(
            stationName = result.name,
            frequency = result.frequency,
            size = 54.dp,
        )
        Column(Modifier.weight(1f).padding(horizontal = 10.dp)) {
            Text(
                result.name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                buildString {
                    append(FytPhysicalRadio.formatFrequencies(FytPhysicalRadio.scanFrequencies(result)))
                    append("  •  RSSI ${result.rssi}")
                    result.stereo?.let { append(if (it) "  •  Stereo" else "  •  Mono") }
                    val pty = FytPhysicalRadio.ptyLabel(result.pty)
                    if (pty.isNotBlank()) append("  •  $pty")
                    if (result.tp) append("  •  TP")
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        TextButton(onClick = onPreview) { Text("HÖREN") }
    }
}

@Composable
private fun PhysicalRadioManualPanel(
    radio: FytPhysicalRadio,
    frequencyInput: String,
    onFrequencyInputChange: (String) -> Unit,
    onTune: () -> Unit,
) {
    val context = LocalContext.current
    val playerConnection = LocalPlayerConnection.current
    val state by radio.state.collectAsStateWithLifecycle()
    val currentPreset =
        state.presets.firstOrNull {
            FytPhysicalRadio.presetMatches(it, state.frequency, state.pi)
        }
    val isFavourite = currentPreset != null

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

        item { RadioStatusLine(state) }

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
                    onClick = {
                        if (isFavourite) {
                            val preset = currentPreset ?: return@OutlinedButton
                            val remaining = state.presets.filterNot { it == preset }
                            radio.removePreset(preset)
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
            }
        }
    }
}

@Composable
private fun PhysicalRadioSettingsPanel(radio: FytPhysicalRadio) {
    val state by radio.state.collectAsStateWithLifecycle()

    LazyColumn(
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize(),
    ) {
        item {
            Text(
                "Radiofunktionen",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                "Die Einstellungen werden dauerhaft gespeichert. Funktionen greifen nur, wenn sie vom FYT-Tuner unterstützt werden.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            RadioSettingRow(
                title = "AF – Alternative Frequenzen",
                description = "Bei schwachem Empfang nach einer stärkeren Frequenz desselben Senders suchen.",
                checked = state.afEnabled,
                onCheckedChange = radio::setAfEnabled,
            )
        }
        item {
            RadioSettingRow(
                title = "TA – Verkehrsmeldungen",
                description = "TA-Ereignisse des aktuell laufenden FM-Senders hervorheben.",
                checked = state.taEnabled,
                onCheckedChange = radio::setTaEnabled,
            )
        }
        item {
            RadioSettingRow(
                title = "REG – Regionalprogramm",
                description = "Alternative Frequenzen auf dieselbe Regionalvariante beschränken, sofern die Firmware dies unterstützt.",
                checked = state.regEnabled,
                onCheckedChange = radio::setRegEnabled,
            )
        }
        item {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedButton(
                    onClick = radio::requestAlternativeFrequency,
                    enabled = state.isActive && state.afEnabled && !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("AF JETZT PRÜFEN")
                }
                OutlinedButton(
                    onClick = radio::enableRds,
                    enabled = state.isActive,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("RDS NEU LESEN")
                }
            }
        }
        item { HorizontalDivider() }
        item { RadioStatusLine(state) }
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
    }
}

@Composable
private fun RadioSettingRow(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(12.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f))
                .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(
                description,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun RadioStatusLine(state: FytPhysicalRadio.State) {
    Text(
        text =
            buildString {
                append("${FytPhysicalRadio.formatFrequency(state.frequency)} MHz")
                append("  •  RSSI ${state.rssi}")
                state.stereo?.let { append(if (it) "  •  Stereo" else "  •  Mono") }
                if (state.pi != 0) append("  •  PI ${state.pi.toString(16).uppercase()}")
                val pty = FytPhysicalRadio.ptyLabel(state.pty)
                if (pty.isNotBlank()) append("  •  $pty")
                if (state.afEnabled) append("  •  AF")
                if (state.tp) append("  •  TP")
                if (state.ta && state.taEnabled) append("  •  TA AKTIV")
            },
        style = MaterialTheme.typography.labelLarge,
        color =
            if (state.ta && state.taEnabled) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
    )
}
