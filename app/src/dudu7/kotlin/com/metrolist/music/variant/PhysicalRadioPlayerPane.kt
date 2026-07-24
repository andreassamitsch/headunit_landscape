package com.metrolist.music.variant

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.metrolist.music.R
import com.metrolist.music.playback.PlayerConnection
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.utils.SearchRoutes

@Composable
fun PhysicalRadioPlayerPane(
    radio: FytPhysicalRadio,
    playerConnection: PlayerConnection?,
) {
    val state by radio.state.collectAsStateWithLifecycle()
    val searchableText = remember(state.rt, state.ps) { state.rt.ifBlank { state.ps } }

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
        modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp, vertical = 8.dp),
    ) {
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.weight(1f).fillMaxWidth(),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "Physisches FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(190.dp),
            )
        }

        Text(
            text = state.displayStation,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable(enabled = searchableText.isNotBlank()) {
                        playerConnection?.requestRightPaneNavigation(SearchRoutes.resultRoute(searchableText))
                    },
        )
        Text(
            text = state.rt.ifBlank { "${FytPhysicalRadio.formatFrequency(state.frequency)} MHz • Antenne" },
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable(enabled = state.rt.isNotBlank()) {
                        playerConnection?.requestRightPaneNavigation(SearchRoutes.resultRoute(state.rt))
                    },
        )

        Spacer(Modifier.height(10.dp))

        Row(
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            IconButton(onClick = { radio.seek(false) }, enabled = state.isActive && !state.isBusy, modifier = Modifier.size(58.dp)) {
                Icon(painterResource(R.drawable.skip_previous), contentDescription = "Vorherigen Sender suchen", modifier = Modifier.size(34.dp))
            }

            FilledIconButton(
                onClick = {
                    if (!state.isActive) {
                        playerConnection?.pause()
                        radio.powerOn()
                    } else {
                        radio.toggleMute()
                    }
                },
                shape = CircleShape,
                colors =
                    IconButtonDefaults.filledIconButtonColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary,
                    ),
                enabled = !state.isBusy,
                modifier = Modifier.size(76.dp),
            ) {
                Icon(
                    painter =
                        painterResource(
                            when {
                                !state.isActive -> R.drawable.play
                                state.isMuted -> R.drawable.volume_off
                                else -> R.drawable.pause
                            },
                        ),
                    contentDescription = if (state.isMuted) "Radio einschalten" else "Radio stummschalten",
                    modifier = Modifier.size(39.dp),
                )
            }

            IconButton(onClick = { radio.seek(true) }, enabled = state.isActive && !state.isBusy, modifier = Modifier.size(58.dp)) {
                Icon(painterResource(R.drawable.skip_next), contentDescription = "Nächsten Sender suchen", modifier = Modifier.size(34.dp))
            }
        }

        Spacer(Modifier.height(6.dp))

        Row(
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            IconButton(onClick = { radio.step(false) }, enabled = !state.isBusy) {
                Text("−0,1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
            Text(
                text = "●  FM LIVE",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
            IconButton(onClick = { radio.step(true) }, enabled = !state.isBusy) {
                Text("+0,1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
        }

        Text(
            text =
                buildString {
                    append("RSSI ${state.rssi}")
                    append(if (state.stereo) " • Stereo" else " • Mono")
                    if (state.pi != 0) append(" • PI ${state.pi.toString(16).uppercase()}")
                    if (state.pty != 0) append(" • PTY ${state.pty}")
                },
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(5.dp))
    }
}
