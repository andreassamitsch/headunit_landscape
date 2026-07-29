from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "app/build.gradle.kts"
RADIO = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
SCREEN = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
RTR = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"


def replace_exact(path: Path, old: str, new: str, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrence(s), found {count}: {old[:180]!r}")
    path.write_text(text.replace(old, new, expected), encoding="utf-8")


def replace_regex(path: Path, pattern: str, replacement: str, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, flags=re.S)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} regex occurrence(s), found {count}: {pattern[:180]!r}")
    path.write_text(updated, encoding="utf-8")


replace_exact(
    BUILD,
    '        versionCode = 1370033\n        versionName = "13.7.24"',
    '        versionCode = 1370034\n        versionName = "13.7.25"',
)

replace_exact(
    RADIO,
    '    private const val KEY_PRESETS = "presets"',
    '    private const val KEY_PRESETS = "presets_v3"\n    private const val LEGACY_KEY_PRESETS = "presets"',
)

replace_exact(
    RADIO,
    '''        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
    )''',
    '''        // Kept only for binary/source compatibility. V3 favourites never persist AF lists.
        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
        val id: String = "",
    )''',
)

replace_exact(
    RADIO,
    '''            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val frequency = normalizeFrequency(prefs.getFloat(KEY_FREQUENCY, 99.7f))
            native = FmNative.getInstance()''',
    '''            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val frequency = normalizeFrequency(prefs.getFloat(KEY_FREQUENCY, 99.7f))
            val presetPayload = prefs.getString(KEY_PRESETS, null)
            val legacyPresetPayload = if (presetPayload == null) prefs.getString(LEGACY_KEY_PRESETS, null) else null
            val loadedPresets = readPresets(presetPayload ?: legacyPresetPayload)
            native = FmNative.getInstance()''',
)

replace_exact(
    RADIO,
    '                    presets = readPresets(prefs.getString(KEY_PRESETS, null)),',
    '                    presets = loadedPresets,',
)

replace_exact(
    RADIO,
    '''                    error = if (FmNative.isLibraryLoaded()) null else "FYT-Firmwarebibliothek libfmjni.so konnte nicht geladen werden",
                )
        }
        startRtrServices(applicationContext)''',
    '''                    error = if (FmNative.isLibraryLoaded()) null else "FYT-Firmwarebibliothek libfmjni.so konnte nicht geladen werden",
                )
            if (presetPayload == null && legacyPresetPayload != null) persistPresets(loadedPresets)
        }
        startRtrServices(applicationContext)''',
)

replace_regex(
    RADIO,
    r'''    fun saveScanResults\(results: Collection<ScanResult>\) \{.*?\n    \}\n\n    fun toggleMute\(\)''',
    '''    fun saveScanResults(results: Collection<ScanResult>) {
        if (results.isEmpty()) return
        var updated = _state.value.presets
        results.sortedByDescending(ScanResult::rssi).forEach { result ->
            val refs = updated.map(::presetRef)
            val existingIndex = FmFavouriteModel.existingIndexForUpsert(refs, result.frequency, result.stationId)
            if (existingIndex >= 0) {
                val existing = updated[existingIndex]
                updated = updated.toMutableList().apply {
                    this[existingIndex] = existing.copy(
                        frequency = normalizeFrequency(result.frequency),
                        name = if (existing.stationId.isNotBlank()) existing.name else result.name,
                        pi = result.pi.takeIf { result.rdsConfirmed } ?: existing.pi,
                        ecc = result.ecc.takeIf { result.rdsConfirmed }.orEmpty().ifBlank { existing.ecc },
                        alternativeFrequencies = emptyList(),
                        stationId = result.stationId.ifBlank { existing.stationId },
                    )
                }
            } else {
                updated = updated + Preset(
                    frequency = normalizeFrequency(result.frequency),
                    name = result.name,
                    pi = result.pi.takeIf { result.rdsConfirmed } ?: 0,
                    ecc = result.ecc.takeIf { result.rdsConfirmed }.orEmpty(),
                    alternativeFrequencies = emptyList(),
                    stationId = result.stationId,
                    id = FmFavouriteModel.newId(),
                )
            }
        }
        updated = normalizePresets(updated)
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    fun toggleMute()''',
)

replace_regex(
    RADIO,
    r'''                val preset = before\.currentPreset.*?                val currentRssi = before\.rssi\.takeIf \{ it > 0 \} \?: runCatching \{ fm\.rssi \}\.getOrDefault\(0\)''',
    '''                val preset = before.currentPreset
                val expectedPi = before.pi.takeIf { before.rdsConfirmed && it > 0 } ?: preset?.pi.orZero()
                val currentRtrMatch = before.rtrStableId.isNotBlank() &&
                    kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f &&
                    before.rtrMatchConfidence >= 60 &&
                    preset?.stationId == before.rtrStableId
                val liveAfFrequencies = if (before.rdsConfirmed) before.alternativeFrequencies else emptyList()
                val nativeFrequencies = if (before.rdsConfirmed) {
                    runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList())
                } else {
                    emptyList()
                }
                val rtrPredictions = before.rtrAfPredictions.takeIf { currentRtrMatch }.orEmpty()
                val rtrFrequencies = rtrPredictions.map(RtrAfPrediction::frequency)
                val knownFrequencies = normalizeFrequencyList(
                    liveAfFrequencies + nativeFrequencies + rtrFrequencies + before.frequency,
                )
                val databaseTrusted = currentRtrMatch && before.rtrMatchConfidence >= 75
                val trustedFrequencies = normalizeFrequencyList(
                    rtrPredictions.filter { databaseTrusted && it.coverageStrength > 0 }
                        .map(RtrAfPrediction::frequency),
                )
                val candidates =
                    (rtrPredictions.map {
                        FmAfCandidate(
                            frequency = it.frequency,
                            trustedPresetFrequency = databaseTrusted && it.coverageStrength > 0,
                            predictedCoverage = it.coverageStrength,
                            source = it.source,
                        )
                    } + (liveAfFrequencies + nativeFrequencies).map {
                        FmAfCandidate(it, false, source = "bestätigtes FYT/RDS-AF")
                    })
                        .filter { abs(it.frequency - before.frequency) >= 0.05f }
                        .distinctBy { frequencyKey(it.frequency) }
                        .sortedWith(compareByDescending<FmAfCandidate> { it.trustedPresetFrequency }
                            .thenByDescending { it.predictedCoverage })
                        .take(8)
                val currentRssi = before.rssi.takeIf { it > 0 } ?: runCatching { fm.rssi }.getOrDefault(0)''',
)

replace_exact(
    RADIO,
    '''        requestRtrResolution(force = true)
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)''',
    '''        updatePresetLastFrequency(before.currentPreset?.id, target)
        requestRtrResolution(force = true)
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)''',
)

replace_regex(
    RADIO,
    r'''        val candidates =\n            normalizeFrequencyList\(\n                presetFrequencies\(preset\) \+ if \(current\.rdsConfirmed\) current\.alternativeFrequencies else emptyList\(\),\n            \)''',
    '''        val candidates =
            normalizeFrequencyList(
                listOf(current.frequency) +
                    current.rtrAfPredictions.takeIf { rtrIdentityTrusted }.orEmpty().map(RtrAfPrediction::frequency) +
                    if (current.rdsConfirmed) current.alternativeFrequencies else emptyList(),
            )''',
)

replace_exact(
    RADIO,
    '''            updateCurrentPresetIdentity()
            triggerRdsRead()
            Timber.tag(TAG).i(
                "Manual AF cycle %.1f -> %.1f PI=%04X RSSI=%d",''',
    '''            updatePresetLastFrequency(preset.id, target)
            requestRtrResolution(force = true)
            updateCurrentPresetIdentity()
            triggerRdsRead()
            Timber.tag(TAG).i(
                "Manual AF cycle %.1f -> %.1f PI=%04X RSSI=%d",''',
)

replace_regex(
    RADIO,
    r'''    fun saveCurrentPreset\(\) \{.*?\n    \}\n\n    fun tunePreset\(preset: Preset\)''',
    '''    fun saveCurrentPreset() {
        val snapshot = _state.value
        val currentRtrMatch = snapshot.rtrStableId.isNotBlank() &&
            kotlin.math.abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f &&
            snapshot.rtrMatchConfidence >= 60
        val stationId = snapshot.rtrStableId.takeIf { currentRtrMatch }.orEmpty()
        val refs = snapshot.presets.map(::presetRef)
        val existingIndex = FmFavouriteModel.existingIndexForUpsert(refs, snapshot.frequency, stationId)
        val updated = snapshot.presets.toMutableList()
        if (existingIndex >= 0) {
            val existing = updated[existingIndex]
            updated[existingIndex] = existing.copy(
                frequency = normalizeFrequency(snapshot.frequency),
                name = if (existing.stationId.isNotBlank()) existing.name else snapshot.displayStation,
                pi = snapshot.pi.takeIf { snapshot.rdsConfirmed } ?: existing.pi,
                ecc = snapshot.ecc.takeIf { snapshot.rdsConfirmed }.orEmpty().ifBlank { existing.ecc },
                alternativeFrequencies = emptyList(),
                stationId = stationId.ifBlank { existing.stationId },
            )
        } else {
            updated += Preset(
                frequency = normalizeFrequency(snapshot.frequency),
                name = snapshot.displayStation,
                pi = snapshot.pi.takeIf { snapshot.rdsConfirmed } ?: 0,
                ecc = snapshot.ecc.takeIf { snapshot.rdsConfirmed }.orEmpty(),
                alternativeFrequencies = emptyList(),
                stationId = stationId,
                id = FmFavouriteModel.newId(),
            )
        }
        val normalized = normalizePresets(updated)
        persistPresets(normalized)
        _state.update { it.copy(presets = normalized) }
    }

    fun tunePreset(preset: Preset)''',
)

replace_regex(
    RADIO,
    r'''    fun updatePreset\(\n        original: Preset,\n        name: String,\n        frequencies: List<Float>,\n    \): Boolean \{.*?\n    \}\n\n    fun removePreset\(preset: Preset\)''',
    '''    fun updatePreset(
        original: Preset,
        name: String,
        frequency: Float,
    ): Boolean {
        if (!frequency.isFinite() || frequency !in FM_MIN..FM_MAX) return false
        val index = _state.value.presets.indexOfFirst { it.id == original.id }
        if (index < 0) return false
        val updated = _state.value.presets.toMutableList().apply {
            this[index] = original.copy(
                frequency = normalizeFrequency(frequency),
                name = name.trim().ifBlank { original.name },
                alternativeFrequencies = emptyList(),
            )
        }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
        return true
    }

    fun removePreset(preset: Preset)''',
)

replace_exact(
    RADIO,
    '''    fun removePreset(preset: Preset) {
        val updated = _state.value.presets.filterNot { samePresetRecord(it, preset) }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }''',
    '''    fun removePreset(preset: Preset) {
        val updated = _state.value.presets.filterNot { it.id == preset.id }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }''',
)

replace_exact(
    RADIO,
    '''                        (snapshot.pi > 0 || snapshot.currentPreset?.let { presetFrequencies(it).size > 1 } == true) &&''',
    '''                        (snapshot.pi > 0 || snapshot.currentPreset?.stationId?.isNotBlank() == true) &&''',
)

replace_regex(
    RADIO,
    r'''    private fun updateCurrentPresetIdentity\(\) \{.*?\n    \}\n\n    private fun persistPresets''',
    '''    private fun updateCurrentPresetIdentity() {
        val snapshot = _state.value
        val currentRtrMatch = snapshot.rtrStableId.isNotBlank() &&
            kotlin.math.abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f &&
            snapshot.rtrMatchConfidence >= 60
        val index = findCurrentPresetIndex(
            presets = snapshot.presets,
            frequency = snapshot.frequency,
            pi = snapshot.pi,
            rdsConfirmed = snapshot.rdsConfirmed,
            stationId = snapshot.rtrStableId.takeIf { currentRtrMatch }.orEmpty(),
        )
        if (index < 0) return
        val current = snapshot.presets[index]
        if (currentRtrMatch && current.stationId.isNotBlank() && current.stationId != snapshot.rtrStableId) return
        val freshRds = snapshot.rdsConfirmed && abs(snapshot.rdsFreshFrequency - snapshot.frequency) < 0.05f
        val rdsCompatible = freshRds && (current.pi <= 0 || snapshot.pi <= 0 || samePi(current.pi, snapshot.pi))
        val rtrCompatible = currentRtrMatch && (current.stationId.isBlank() || current.stationId == snapshot.rtrStableId)
        val updatedPreset = current.copy(
            frequency = normalizeFrequency(snapshot.frequency),
            name = when {
                rtrCompatible && current.stationId == snapshot.rtrStableId && current.name.isNotBlank() -> current.name
                rtrCompatible -> snapshot.rtrCanonicalName
                rdsCompatible -> snapshot.displayStation
                else -> current.name
            },
            pi = if (rdsCompatible && snapshot.pi > 0) snapshot.pi else current.pi,
            ecc = if (rdsCompatible && snapshot.ecc.isNotBlank()) snapshot.ecc else current.ecc,
            alternativeFrequencies = emptyList(),
            stationId = if (rtrCompatible) snapshot.rtrStableId else current.stationId,
        )
        if (updatedPreset == current) return
        val updated = snapshot.presets.toMutableList().apply { this[index] = updatedPreset }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    private fun updatePresetLastFrequency(presetId: String?, frequency: Float) {
        if (presetId.isNullOrBlank()) return
        val snapshot = _state.value
        val index = snapshot.presets.indexOfFirst { it.id == presetId }
        if (index < 0) return
        val updated = snapshot.presets.toMutableList().apply {
            this[index] = this[index].copy(
                frequency = normalizeFrequency(frequency),
                alternativeFrequencies = emptyList(),
            )
        }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    private fun persistPresets''',
)

replace_regex(
    RADIO,
    r'''    private fun persistPresets\(presets: List<Preset>\) \{.*?\n    private fun usefulStationIdentity''',
    '''    private fun persistPresets(presets: List<Preset>) {
        val normalized = normalizePresets(presets)
        val encoded = normalized.joinToString("\\n") { preset ->
            listOf(
                "v3",
                preset.id,
                preset.frequency.toString(),
                preset.name.replace('\\n', ' ').replace('\\t', ' '),
                preset.pi.toString(),
                preset.ecc.replace('\\n', ' ').replace('\\t', ' '),
                preset.stationId.replace('\\n', ' ').replace('\\t', ' '),
            ).joinToString("\\t")
        }
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putString(KEY_PRESETS, encoded)
            ?.remove(LEGACY_KEY_PRESETS)
            ?.apply()
    }

    private fun readPresets(value: String?): List<Preset> {
        val parsed = value.orEmpty().lineSequence().mapIndexedNotNull { index, line ->
            if (line.isBlank()) return@mapIndexedNotNull null
            val parts = line.split('\\t')
            if (parts.firstOrNull() == "v3") {
                val frequency = parts.getOrNull(2)?.toFloatOrNull() ?: return@mapIndexedNotNull null
                Preset(
                    frequency = normalizeFrequency(frequency),
                    name = parts.getOrNull(3).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" },
                    pi = parts.getOrNull(4)?.toIntOrNull() ?: 0,
                    ecc = parts.getOrNull(5).orEmpty(),
                    alternativeFrequencies = emptyList(),
                    stationId = parts.getOrNull(6).orEmpty(),
                    id = parts.getOrNull(1).orEmpty().ifBlank {
                        FmFavouriteModel.legacyId(index, frequency, parts.getOrNull(3).orEmpty(), parts.getOrNull(6).orEmpty())
                    },
                )
            } else {
                val legacy = line.split('\\t', limit = 6)
                val frequency = legacy.firstOrNull()?.toFloatOrNull() ?: return@mapIndexedNotNull null
                val name = legacy.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" }
                val stationId = legacy.getOrNull(5).orEmpty()
                Preset(
                    frequency = normalizeFrequency(frequency),
                    name = name,
                    pi = legacy.getOrNull(2)?.toIntOrNull() ?: 0,
                    ecc = legacy.getOrNull(3).orEmpty(),
                    alternativeFrequencies = emptyList(),
                    stationId = stationId,
                    id = FmFavouriteModel.legacyId(index, frequency, name, stationId),
                )
            }
        }.toList()
        return normalizePresets(parsed)
    }

    private fun normalizePresets(presets: Collection<Preset>): List<Preset> =
        presets.mapIndexed { index, preset ->
            preset.copy(
                id = preset.id.ifBlank {
                    FmFavouriteModel.legacyId(index, preset.frequency, preset.name, preset.stationId)
                },
                frequency = normalizeFrequency(preset.frequency),
                alternativeFrequencies = emptyList(),
            )
        }.distinctBy(Preset::id)

    private fun presetRef(preset: Preset): FmFavouriteRef =
        FmFavouriteRef(preset.id, preset.stationId, preset.frequency)

    fun presetFrequencies(preset: Preset): List<Float> = listOf(normalizeFrequency(preset.frequency))

    fun scanFrequencies(result: ScanResult): List<Float> =
        normalizeFrequencyList(listOf(result.frequency) + result.alternativeFrequencies)

    fun presetContainsFrequency(
        preset: Preset,
        frequency: Float,
    ): Boolean = abs(preset.frequency - frequency) < 0.05f

    fun presetMatches(
        preset: Preset,
        frequency: Float,
        pi: Int,
    ): Boolean = presetContainsFrequency(preset, frequency)

    private fun findCurrentPresetIndex(
        presets: List<Preset>,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Int = FmFavouriteModel.selectCurrentIndex(presets.map(::presetRef), frequency, stationId)

    private fun findCurrentPreset(
        presets: List<Preset>,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Preset? = findCurrentPresetIndex(presets, frequency, pi, rdsConfirmed, stationId)
        .takeIf { it >= 0 }
        ?.let(presets::get)

    fun stablePresetKey(preset: Preset): String = preset.id

    fun presetOrderKeys(preset: Preset): Set<String> = buildSet {
        add(preset.id)
        preset.stationId.takeIf(String::isNotBlank)?.let(::add)
        addAll(FmStationIdentity.orderKeys(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = listOf(preset.frequency),
            pi = preset.pi,
            ecc = preset.ecc,
        ))
    }

    fun formatFrequencies(values: List<Float>): String =
        normalizeFrequencyList(values).joinToString(" / ") { "${formatFrequency(it)} MHz" }

    private fun groupScanResults(results: Collection<ScanResult>): List<ScanResult> {
        val groups = mutableListOf<MutableList<ScanResult>>()
        results.forEach { result ->
            val group = groups.firstOrNull { existing ->
                FmFavouriteModel.shouldGroupScan(existing.first().stationId, result.stationId)
            }
            if (group == null) groups += mutableListOf(result) else group += result
        }
        return groups.map { group ->
            val strongest = group.maxByOrNull(ScanResult::rssi) ?: group.first()
            val frequencies = normalizeFrequencyList(group.map(ScanResult::frequency))
            strongest.copy(
                name = group.firstOrNull { it.stationId.isNotBlank() }?.name ?: strongest.name,
                pi = group.firstOrNull { it.rdsConfirmed && it.pi > 0 }?.pi ?: strongest.pi,
                ecc = group.firstOrNull { it.rdsConfirmed && it.ecc.isNotBlank() }?.ecc ?: strongest.ecc,
                stationId = group.firstOrNull { it.stationId.isNotBlank() }?.stationId.orEmpty(),
                rdsConfirmed = group.any(ScanResult::rdsConfirmed),
                alternativeFrequencies = frequencies.filterNot { abs(it - strongest.frequency) < 0.05f },
                stereo = when {
                    group.any { it.stereo == true } -> true
                    group.any { it.stereo == false } -> false
                    else -> null
                },
            )
        }
    }

    private fun samePresetRecord(first: Preset, second: Preset): Boolean = first.id == second.id

    private fun usefulStationIdentity''',
)

replace_exact(
    RTR,
    'setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.22")',
    'setRequestProperty("User-Agent", "Metrolist-dudu7/13.7.25")',
)

replace_exact(
    SCREEN,
    '''                                val isActive =
                                    state.isActive &&
                                        FytPhysicalRadio.presetMatches(preset, state.frequency, state.pi)''',
    '''                                val isActive = state.isActive && state.currentPreset?.id == preset.id''',
)

replace_exact(
    SCREEN,
    '''                                    activeEcc = state.ecc,
                                    activeAlternativeFrequencies = state.alternativeFrequencies,
                                    isActive = isActive,''',
    '''                                    activeEcc = state.ecc,
                                    isActive = isActive,''',
)

replace_exact(
    SCREEN,
    '''            onSave = { name, frequencies ->
                if (radio.updatePreset(preset, name, frequencies)) {''',
    '''            onSave = { name, frequency ->
                if (radio.updatePreset(preset, name, frequency)) {''',
)

replace_regex(
    SCREEN,
    r'''@Composable\nprivate fun FmPresetEditorDialog\(.*?\n\}\n\n@Composable\nprivate fun EmptyFmFavourites''',
    '''@Composable
private fun FmPresetEditorDialog(
    preset: FytPhysicalRadio.Preset,
    onDismiss: () -> Unit,
    onSave: (String, Float) -> Unit,
    onChooseLogo: () -> Unit,
) {
    var name by remember(preset) { mutableStateOf(preset.name) }
    var frequency by remember(preset) { mutableStateOf(FytPhysicalRadio.formatFrequency(preset.frequency)) }
    var error by remember(preset) { mutableStateOf<String?>(null) }
    val isRtrFavourite = preset.stationId.isNotBlank()

    fun submit() {
        val parsed = frequency.replace(',', '.').toFloatOrNull()
        when {
            name.isBlank() -> error = "Sendername fehlt"
            parsed == null -> error = "Frequenz ist ungültig"
            parsed !in 87.5f..108.0f -> error = "Frequenz muss zwischen 87,5 und 108,0 MHz liegen"
            else -> onSave(name.trim(), if (isRtrFavourite) preset.frequency else parsed)
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
                if (isRtrFavourite) {
                    OutlinedTextField(
                        value = "${FytPhysicalRadio.formatFrequency(preset.frequency)} MHz",
                        onValueChange = {},
                        readOnly = true,
                        label = { Text("Zuletzt verwendete Frequenz") },
                        supportingText = { Text("Alternative Frequenzen werden automatisch über RTR gewählt und nicht im Favoriten gespeichert.") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    OutlinedTextField(
                        value = frequency,
                        onValueChange = { frequency = it },
                        label = { Text("Feste Frequenz") },
                        supportingText = { Text("Dieser manuelle Favorit verwendet genau eine Frequenz.") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                FmStationArtwork(
                    stationName = preset.name,
                    frequency = preset.frequency,
                    pi = preset.pi,
                    ecc = preset.ecc,
                    size = 72.dp,
                    allFrequencies = listOf(preset.frequency),
                )
                OutlinedButton(onClick = onChooseLogo, modifier = Modifier.fillMaxWidth()) {
                    Text("SENDERLOGO AUSWÄHLEN")
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { Button(onClick = ::submit) { Text("Speichern") } },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

@Composable
private fun EmptyFmFavourites''',
)

replace_exact(
    SCREEN,
    '''    activeEcc: String,
    activeAlternativeFrequencies: List<Float>,
    isActive: Boolean,''',
    '''    activeEcc: String,
    isActive: Boolean,''',
)

replace_exact(
    SCREEN,
    '''            allFrequencies =
                FytPhysicalRadio.presetFrequencies(preset) +
                    if (isActive) activeAlternativeFrequencies else emptyList(),''',
    '''            allFrequencies = listOf(if (isActive) activeFrequency else preset.frequency),''',
)

replace_exact(
    SCREEN,
    '''            Text(
                text = FytPhysicalRadio.formatFrequencies(FytPhysicalRadio.presetFrequencies(preset)),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )''',
    '''            Text(
                text = if (preset.stationId.isNotBlank()) {
                    "${FytPhysicalRadio.formatFrequency(if (isActive) activeFrequency else preset.frequency)} MHz • AF automatisch über RTR"
                } else {
                    "${FytPhysicalRadio.formatFrequency(preset.frequency)} MHz • Fester Frequenzfavorit"
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )''',
)

print("Applied Dudu7 13.7.25 FM favourite model v3")
