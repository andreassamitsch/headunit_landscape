from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "app/build.gradle.kts"
RADIO = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
SCREEN = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one occurrence, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    BUILD,
    '        versionCode = 1370031\n        versionName = "13.7.22"',
    '        versionCode = 1370032\n        versionName = "13.7.23"',
)

replace_once(
    RADIO,
    '''    fun removePreset(frequency: Float) {
        val matching = _state.value.presets.firstOrNull { presetContainsFrequency(it, frequency) }
        if (matching != null) {
            removePreset(matching)
        }
    }
''',
    '''    fun clearPresets() {
        pendingPresetIdentity = null
        persistPresets(emptyList())
        _state.update {
            it.copy(
                presets = emptyList(),
                alternativeFrequencies = emptyList(),
                rtrAfPredictions = emptyList(),
            )
        }
    }

    fun removePreset(frequency: Float) {
        val matching = _state.value.presets.firstOrNull { presetContainsFrequency(it, frequency) }
        if (matching != null) {
            removePreset(matching)
        }
    }
''',
)

replace_once(
    SCREEN,
    '''    val playerConnection = LocalPlayerConnection.current
    val state by radio.state.collectAsStateWithLifecycle()
    val selected = remember { mutableStateMapOf<Int, Boolean>() }
''',
    '''    val context = LocalContext.current
    val playerConnection = LocalPlayerConnection.current
    val state by radio.state.collectAsStateWithLifecycle()
    val selected = remember { mutableStateMapOf<Int, Boolean>() }
    var showScanStartOptions by remember { mutableStateOf(false) }

    fun startScan(clearFavourites: Boolean) {
        playerConnection?.pause()
        if (clearFavourites) {
            radio.clearPresets()
            FmPresetOrderStore.persist(context, emptyList())
        }
        radio.startAutoScan()
    }
''',
)

replace_once(
    SCREEN,
    '''                    Button(
                        onClick = {
                            playerConnection?.pause()
                            radio.startAutoScan()
                        },
                        enabled = state.libraryLoaded,
''',
    '''                    Button(
                        onClick = {
                            if (state.presets.isEmpty()) {
                                startScan(clearFavourites = false)
                            } else {
                                showScanStartOptions = true
                            }
                        },
                        enabled = state.libraryLoaded,
''',
)

replace_once(
    SCREEN,
    '''        }
    }
}

@Composable
private fun FmScanResultRow(''',
    '''        }
    }

    if (showScanStartOptions) {
        AlertDialog(
            onDismissRequest = { showScanStartOptions = false },
            title = { Text("FM-Suchlauf starten") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        "Es sind ${state.presets.size} FM-Favoriten gespeichert. " +
                            "Du kannst sie behalten oder vor dem Suchlauf vollständig löschen.",
                    )
                    Button(
                        onClick = {
                            showScanStartOptions = false
                            startScan(clearFavourites = false)
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("FAVORITEN BEHALTEN UND SUCHEN")
                    }
                    OutlinedButton(
                        onClick = {
                            showScanStartOptions = false
                            startScan(clearFavourites = true)
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            "ALLE FM-FAVORITEN LÖSCHEN UND SUCHEN",
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            },
            confirmButton = {},
            dismissButton = {
                TextButton(onClick = { showScanStartOptions = false }) {
                    Text("ABBRECHEN")
                }
            },
        )
    }
}

@Composable
private fun FmScanResultRow(''',
)

print("Applied clean Dudu7 13.7.23 FM scan favourites choice")
