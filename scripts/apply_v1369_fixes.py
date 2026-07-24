#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:100]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# 1. Artist category routes: query parameters must be separated with '&'.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt",
    'route = "artist/{artistId}/items?browseId={browseId}?params={params}",',
    'route = "artist/{artistId}/items?browseId={browseId}&params={params}",',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt",
    '"artist/${viewModel.artistId}/items?browseId=${it.browseId}?params=${it.params}",',
    '"artist/${viewModel.artistId}/items?browseId=${android.net.Uri.encode(it.browseId)}&params=${android.net.Uri.encode(it.params.orEmpty())}",',
)

# 2 + 3. Saved radio drag handle and manual station-logo selection.
radio_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt")
radio = radio_path.read_text(encoding="utf-8")
if "private fun RadioDragHandle" not in radio:
    radio = radio.replace(
        "import androidx.compose.foundation.background\n",
        "import androidx.compose.foundation.background\nimport androidx.compose.foundation.border\n",
        1,
    )
    radio = radio.replace(
        '''                                    dragHandleModifier =
                                        Modifier.longPressDraggableHandle(
                                            onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                        ),''',
        '''                                    dragHandle = {
                                        RadioDragHandle(
                                            Modifier.draggableHandle(
                                                onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                            ),
                                        )
                                    },''',
        1,
    )
    radio = radio.replace(
        '''                                    dragHandleModifier =
                                        Modifier.longPressDraggableHandle(
                                            onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                        ),''',
        '''                                    dragHandle = {
                                        RadioDragHandle(
                                            Modifier.draggableHandle(
                                                onDragStarted = { haptic.performHapticFeedback(HapticFeedbackType.LongPress) },
                                            ),
                                        )
                                    },''',
        1,
    )
    radio = radio.replace(
        "    dragHandleModifier: Modifier = Modifier,\n",
        "    dragHandle: @Composable () -> Unit = {},\n",
        1,
    )
    radio = radio.replace(
        "        RadioStationArtwork(station, 54, dragHandleModifier, onLogoResolved)\n",
        "        RadioStationArtwork(station, 54, Modifier, onLogoResolved)\n",
        1,
    )
    radio = radio.replace(
        '''        if (!isSaved) {
            IconButton(onClick = onSave) {''',
        '''        if (isSaved) {
            dragHandle()
        } else {
            IconButton(onClick = onSave) {''',
        1,
    )
    radio = radio.replace(
        "    dragHandleModifier: Modifier = Modifier,\n",
        "    dragHandle: @Composable () -> Unit = {},\n",
        1,
    )
    radio = radio.replace(
        "            RadioStationArtwork(station, 88, dragHandleModifier, onLogoResolved)\n",
        "            RadioStationArtwork(station, 88, Modifier, onLogoResolved)\n",
        1,
    )
    radio = radio.replace(
        '''            if (!isSaved) {
                IconButton(onClick = onSave, modifier = Modifier.align(Alignment.TopEnd).size(34.dp)) {''',
        '''            if (isSaved) {
                Box(Modifier.align(Alignment.TopEnd)) { dragHandle() }
            } else {
                IconButton(onClick = onSave, modifier = Modifier.align(Alignment.TopEnd).size(34.dp)) {''',
        1,
    )
    insert_marker = "\n@Composable\nprivate fun RadioStationArtwork("
    radio = radio.replace(
        insert_marker,
        '''
@Composable
private fun RadioDragHandle(modifier: Modifier) {
    IconButton(
        onClick = {},
        modifier = modifier.size(42.dp),
    ) {
        Icon(
            painter = painterResource(R.drawable.drag_handle),
            contentDescription = "Sender verschieben",
        )
    }
}

@Composable
private fun RadioStationArtwork(''',
        1,
    )
    radio = radio.replace(
        'contentDescription = "Senderlogo ${station.name}; lange drücken und ziehen zum Sortieren",',
        'contentDescription = "Senderlogo ${station.name}",',
        1,
    )

    # Replace the compact editor with logo search and a persistent manual choice.
    old_editor = '''@Composable
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
'''
    new_editor = '''@Composable
private fun RadioStationEditorDialog(
    initial: RadioStation?,
    onDismiss: () -> Unit,
    onSave: (RadioStation) -> Unit,
) {
    var name by remember(initial) { mutableStateOf(initial?.name.orEmpty()) }
    var streamUrl by remember(initial) { mutableStateOf(initial?.streamUrl.orEmpty()) }
    var favicon by remember(initial) { mutableStateOf(initial?.favicon.orEmpty()) }
    var manualFavicon by remember(initial) { mutableStateOf(initial?.manualFavicon == true) }
    var logoCandidates by remember(initial) { mutableStateOf<List<String>>(emptyList()) }
    var logoSearchLoading by remember(initial) { mutableStateOf(false) }
    var logoSearchError by remember(initial) { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun searchLogos() {
        if (name.isBlank() || logoSearchLoading) return
        scope.launch {
            logoSearchLoading = true
            logoSearchError = null
            RadioBrowserClient.search(name.trim())
                .onSuccess { stations ->
                    logoCandidates =
                        stations
                            .asSequence()
                            .map { it.favicon.trim() }
                            .filter { it.startsWith("https://") || it.startsWith("http://") }
                            .distinct()
                            .take(16)
                            .toList()
                    if (logoCandidates.isEmpty()) logoSearchError = "Keine passenden Logos gefunden"
                }.onFailure { logoSearchError = it.message ?: "Logosuche fehlgeschlagen" }
            logoSearchLoading = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (initial == null) "Radiosender hinzufügen" else "Radiosender bearbeiten") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = name, onValueChange = { name = it }, label = { Text("Sendername") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(value = streamUrl, onValueChange = { streamUrl = it }, label = { Text("Stream-, M3U- oder PLS-Adresse") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    value = favicon,
                    onValueChange = {
                        favicon = it
                        manualFavicon = it.isNotBlank()
                    },
                    label = { Text("Senderbild (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (favicon.isNotBlank()) {
                    AsyncImage(
                        model = favicon,
                        contentDescription = "Ausgewähltes Senderlogo",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.size(82.dp).clip(RoundedCornerShape(10.dp)),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedButton(onClick = ::searchLogos, enabled = name.isNotBlank() && !logoSearchLoading) {
                        Text("Logos suchen")
                    }
                    TextButton(
                        onClick = {
                            favicon = ""
                            manualFavicon = false
                            logoCandidates = emptyList()
                            logoSearchError = null
                        },
                    ) { Text("Automatisch") }
                    if (logoSearchLoading) CircularProgressIndicator(Modifier.size(24.dp))
                }
                if (logoCandidates.isNotEmpty()) {
                    Text("Logo auswählen", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(logoCandidates, key = { it }) { candidate ->
                            AsyncImage(
                                model = candidate,
                                contentDescription = "Logo auswählen",
                                contentScale = ContentScale.Fit,
                                modifier =
                                    Modifier
                                        .size(72.dp)
                                        .clip(RoundedCornerShape(10.dp))
                                        .then(
                                            if (favicon == candidate && manualFavicon) {
                                                Modifier.border(2.dp, MaterialTheme.colorScheme.primary, RoundedCornerShape(10.dp))
                                            } else {
                                                Modifier
                                            },
                                        ).clickable {
                                            favicon = candidate
                                            manualFavicon = true
                                        },
                            )
                        }
                    }
                }
                logoSearchError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                if (manualFavicon && favicon.isNotBlank()) {
                    Text("Dieses Logo bleibt fest eingestellt.", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(
                enabled = name.isNotBlank() && streamUrl.isNotBlank(),
                onClick = {
                    onSave(
                        (initial ?: RadioStation(UUID.randomUUID().toString(), name.trim(), streamUrl.trim()))
                            .copy(
                                name = name.trim(),
                                streamUrl = streamUrl.trim(),
                                favicon = favicon.trim(),
                                manualFavicon = manualFavicon && favicon.isNotBlank(),
                            ),
                    )
                },
            ) { Text("Speichern") }
        },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
'''
    if old_editor not in radio:
        raise SystemExit("RadioStationEditorDialog marker missing")
    radio = radio.replace(old_editor, new_editor, 1)
    radio_path.write_text(radio, encoding="utf-8")

# Radio model/store/resolver: manual logo survives and disables auto replacement.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt",
    "    val favicon: String = \"\",\n    val country: String = \"\",",
    "    val favicon: String = \"\",\n    val manualFavicon: Boolean = false,\n    val country: String = \"\",",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt",
    '                            putString("radio_favicon", favicon)\n                            putString("radio_country", country)',
    '                            putString("radio_favicon", favicon)\n                            putBoolean("radio_manual_favicon", manualFavicon)\n                            putString("radio_country", country)',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt",
    '        favicon = extras?.getString("radio_favicon").orEmpty(),\n        country = extras?.getString("radio_country").orEmpty(),',
    '        favicon = extras?.getString("radio_favicon").orEmpty(),\n        manualFavicon = extras?.getBoolean("radio_manual_favicon", false) == true,\n        country = extras?.getString("radio_country").orEmpty(),',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationStore.kt",
    '                        put("favicon", station.favicon)\n                        put("country", station.country)',
    '                        put("favicon", station.favicon)\n                        put("manualFavicon", station.manualFavicon)\n                        put("country", station.country)',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationStore.kt",
    '            favicon = optString("favicon"),\n            country = optString("country"),',
    '            favicon = optString("favicon"),\n            manualFavicon = optBoolean("manualFavicon", false),\n            country = optString("country"),',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt",
    '        withContext(Dispatchers.IO) {\n            val candidates = mutableListOf<Candidate>()',
    '        withContext(Dispatchers.IO) {\n            if (station.manualFavicon) return@withContext station.favicon.trim().takeIf(::isHttpUrl)\n            val candidates = mutableListOf<Candidate>()',
)

# 4 + 5. Always execute a fresh radio-title search and restore the exact WebRadio tab destination.
layout_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
layout = layout_path.read_text(encoding="utf-8")
old_open = '''        val openRouteInRightPane: (String) -> Unit = { route ->
            selectedTab = VehicleRightPaneTab.SEARCH
            paneNavController.navigate(route) {
                launchSingleTop = true
            }
        }'''
new_open = '''        val openRouteInRightPane: (String) -> Unit = { route ->
            selectedTab = VehicleRightPaneTab.SEARCH
            if (
                route.startsWith("search/") &&
                paneNavController.currentDestination?.route == SearchRoutes.ROUTE
            ) {
                paneNavController.popBackStack()
            }
            paneNavController.navigate(route)
        }'''
if new_open not in layout:
    if old_open not in layout:
        raise SystemExit("Right-pane route callback marker missing")
    layout = layout.replace(old_open, new_open, 1)
old_tab = '''                                if (selectedTab != tab || currentPaneRoute != tab.route) {
                                    selectedTab = tab
                                    paneNavController.navigate(tab.route) {
                                        popUpTo(VEHICLE_QUEUE_ROUTE) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }'''
new_tab = '''                                if (selectedTab != tab || currentPaneRoute != tab.route) {
                                    selectedTab = tab
                                    val restoredExistingTab =
                                        paneNavController.popBackStack(tab.route, inclusive = false)
                                    if (!restoredExistingTab) {
                                        paneNavController.popBackStack(VEHICLE_QUEUE_ROUTE, inclusive = false)
                                        if (tab != VehicleRightPaneTab.QUEUE) {
                                            paneNavController.navigate(tab.route) {
                                                launchSingleTop = true
                                            }
                                        }
                                    }
                                }'''
if new_tab not in layout:
    if old_tab not in layout:
        raise SystemExit("Right-pane tab callback marker missing")
    layout = layout.replace(old_tab, new_tab, 1)
layout_path.write_text(layout, encoding="utf-8")

# Release/update identity and user-agent labels.
replace_once(
    "app/build.gradle.kts",
    'versionCode = 157\n        versionName = "13.6.8"',
    'versionCode = 158\n        versionName = "13.6.9"',
)
for path in [
    "app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt",
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt",
]:
    file = Path(path)
    text = file.read_text(encoding="utf-8").replace("MetrolistHU/13.6.8", "MetrolistHU/13.6.9").replace("MetrolistHU/13.6.6", "MetrolistHU/13.6.9")
    file.write_text(text, encoding="utf-8")

print("Applied Metrolist Dudu7 13.6.9 fixes")
