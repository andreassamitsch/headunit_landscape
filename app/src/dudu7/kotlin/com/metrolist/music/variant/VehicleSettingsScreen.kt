package com.metrolist.music.variant

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import com.metrolist.music.R
import com.metrolist.music.constants.Dudu7AlwaysStartPlayerKey
import com.metrolist.music.constants.Dudu7AutoCenterQueueKey
import com.metrolist.music.constants.Dudu7PlayerPaneWeightKey
import com.metrolist.music.constants.Dudu7StartWithLyricsKey
import com.metrolist.music.constants.Dudu7SwipeToRemoveQueueKey
import com.metrolist.music.constants.KeepScreenOn
import com.metrolist.music.constants.QueueEditLockKey
import com.metrolist.music.constants.ResumeOnBluetoothConnectKey
import com.metrolist.music.utils.rememberPreference

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VehicleSettingsScreen(navController: NavController) {
    val (alwaysStartPlayer, setAlwaysStartPlayer) = rememberPreference(Dudu7AlwaysStartPlayerKey, true)
    val (paneWeight, setPaneWeight) = rememberPreference(Dudu7PlayerPaneWeightKey, 0.45f)
    val (startWithLyrics, setStartWithLyrics) = rememberPreference(Dudu7StartWithLyricsKey, false)
    val (swipeToRemove, setSwipeToRemove) = rememberPreference(Dudu7SwipeToRemoveQueueKey, true)
    val (autoCenterQueue, setAutoCenterQueue) = rememberPreference(Dudu7AutoCenterQueueKey, true)
    val (queueLocked, setQueueLocked) = rememberPreference(QueueEditLockKey, false)
    val (keepScreenOn, setKeepScreenOn) = rememberPreference(KeepScreenOn, true)
    val (resumeBluetooth, setResumeBluetooth) = rememberPreference(ResumeOnBluetoothConnectKey, true)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Dudu7-Oberfläche") },
                navigationIcon = {
                    IconButton(onClick = navController::popBackStack) {
                        Icon(painterResource(R.drawable.arrow_back), contentDescription = "Zurück")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()),
        ) {
            SectionTitle("Startverhalten")
            SwitchRow(
                title = "Immer mit Player und Warteschlange starten",
                summary = "Die Wiedergabeansicht ist die Startoberfläche des Autoradios.",
                checked = alwaysStartPlayer,
                onCheckedChange = setAlwaysStartPlayer,
            )
            SwitchRow(
                title = "Mit Songtext statt Warteschlange starten",
                summary = "Die Warteschlange bleibt jederzeit über den rechten Bereich erreichbar.",
                checked = startWithLyrics,
                onCheckedChange = setStartWithLyrics,
            )

            HorizontalDivider()
            SectionTitle("Player")
            Text(
                "Breite des linken Player-Bereichs: ${(paneWeight * 100).toInt()} %",
                modifier = Modifier.padding(16.dp),
            )
            Slider(
                value = Dudu7Layout.sanitizePlayerPaneWeight(paneWeight),
                onValueChange = setPaneWeight,
                valueRange = Dudu7Layout.MIN_PLAYER_PANE_WEIGHT..Dudu7Layout.MAX_PLAYER_PANE_WEIGHT,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            SwitchRow(
                title = "Bildschirm während der Wiedergabe eingeschaltet lassen",
                checked = keepScreenOn,
                onCheckedChange = setKeepScreenOn,
            )
            SwitchRow(
                title = "Nach Bluetooth-Verbindung fortsetzen",
                checked = resumeBluetooth,
                onCheckedChange = setResumeBluetooth,
            )

            HorizontalDivider()
            SectionTitle("Warteschlange")
            SwitchRow(
                title = "Bearbeitung beim Start sperren",
                summary = "Ausgeschaltet bleiben Drag-and-drop-Griffe sofort verfügbar.",
                checked = queueLocked,
                onCheckedChange = setQueueLocked,
            )
            SwitchRow(
                title = "Titel per Wischgeste entfernen",
                checked = swipeToRemove,
                onCheckedChange = setSwipeToRemove,
            )
            SwitchRow(
                title = "Aktuellen Titel automatisch zentrieren",
                checked = autoCenterQueue,
                onCheckedChange = setAutoCenterQueue,
            )

            HorizontalDivider()
            TextButton(
                onClick = { navController.navigate("settings") },
                modifier = Modifier.padding(8.dp),
            ) {
                Text("Alle MetroList-Einstellungen öffnen")
            }
        }
    }
}

@Composable
private fun SectionTitle(title: String) {
    Text(title, modifier = Modifier.padding(start = 16.dp, top = 20.dp, end = 16.dp, bottom = 8.dp))
}

@Composable
private fun SwitchRow(
    title: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    summary: String? = null,
) {
    ListItem(
        headlineContent = { Text(title) },
        supportingContent = summary?.let { { Text(it) } },
        trailingContent = { Switch(checked = checked, onCheckedChange = onCheckedChange) },
    )
}
