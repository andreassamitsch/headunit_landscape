package com.metrolist.music.ui.screens.radio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.radio.fyt.FytPhysicalRadio

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PhysicalRadioScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val playerConnection = LocalPlayerConnection.current
    val radio = remember(context) { FytPhysicalRadio.get(context) }
    val state by radio.state.collectAsStateWithLifecycle()
    var frequencyInput by remember { mutableStateOf(FytPhysicalRadio.formatFrequency(state.frequency)) }

    LaunchedEffect(state.frequency) {
        frequencyInput = FytPhysicalRadio.formatFrequency(state.frequency)
    }

    Column(
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxSize().padding(horizontal = 14.dp, vertical = 10.dp),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = state.displayStation,
                    style = MaterialTheme.typography.headlineMedium,
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
            if (state.isBusy) CircularProgressIndicator()
        }

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

        state.error?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodyMedium,
            )
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedTextField(
                value = frequencyInput,
                onValueChange = { frequencyInput = it.replace(',', '.') },
                label = { Text("Frequenz") },
                suffix = { Text("MHz") },
                singleLine = true,
                keyboardOptions = KeyboardOptions.Default,
                modifier = Modifier.weight(1f),
            )
            Button(
                onClick = {
                    frequencyInput.toFloatOrNull()?.let { frequency ->
                        playerConnection?.pause()
                        radio.tune(frequency)
                    }
                },
                enabled = !state.isBusy,
            ) {
                Text("TUNE")
            }
        }

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
                onClick = radio::saveCurrentPreset,
                enabled = state.isActive,
                modifier = Modifier.weight(1f),
            ) {
                Icon(painterResource(R.drawable.favorite_border), contentDescription = null)
                Text("MERKEN", modifier = Modifier.padding(start = 6.dp))
            }
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedButton(onClick = { radio.seek(false) }, enabled = state.isActive && !state.isBusy, modifier = Modifier.weight(1f)) {
                Text("SEEK ◀")
            }
            OutlinedButton(onClick = { radio.step(false) }, enabled = !state.isBusy, modifier = Modifier.weight(1f)) {
                Text("− 0,1")
            }
            OutlinedButton(onClick = { radio.step(true) }, enabled = !state.isBusy, modifier = Modifier.weight(1f)) {
                Text("+ 0,1")
            }
            OutlinedButton(onClick = { radio.seek(true) }, enabled = state.isActive && !state.isBusy, modifier = Modifier.weight(1f)) {
                Text("SEEK ▶")
            }
            OutlinedButton(onClick = radio::enableRds, enabled = state.isActive, modifier = Modifier.weight(1f)) {
                Text("RDS")
            }
        }

        HorizontalDivider()
        Text("FM-Favoriten", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)

        if (state.presets.isEmpty()) {
            Text(
                text = "Mit „Merken“ wird die aktuelle Frequenz gespeichert.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            LazyColumn(Modifier.fillMaxSize()) {
                items(state.presets, key = { it.frequency }) { preset ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .clickable {
                                    playerConnection?.pause()
                                    radio.tune(preset.frequency)
                                }.padding(vertical = 7.dp),
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(preset.name, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                            Text("${FytPhysicalRadio.formatFrequency(preset.frequency)} MHz", style = MaterialTheme.typography.bodyMedium)
                        }
                        IconButton(onClick = { radio.removePreset(preset.frequency) }) {
                            Icon(painterResource(R.drawable.delete), contentDescription = "Favorit löschen")
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(2.dp))
        Text(
            text = "FYT ${state.platform.ifBlank { "Dudu7" }} • radio_type=${state.radioType.ifBlank { "?" }} • libfmjni=${if (state.libraryLoaded) "bereit" else "fehlt"}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
