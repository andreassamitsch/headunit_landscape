package com.metrolist.music.ui.screens.radio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.metrolist.music.radio.RadioLogoCandidate
import com.metrolist.music.radio.fyt.FmStationArtwork
import com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import kotlinx.coroutines.launch

@Composable
internal fun FmLogoPickerDialog(
    preset: FytPhysicalRadio.Preset,
    onDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var candidates by remember(preset) { mutableStateOf<List<RadioLogoCandidate>>(emptyList()) }
    var loading by remember(preset) { mutableStateOf(true) }
    var applying by remember(preset) { mutableStateOf(false) }
    var error by remember(preset) { mutableStateOf<String?>(null) }
    var searchRevision by remember(preset) { mutableIntStateOf(0) }
    val info = ReliableFmStationLogoResolver.logoInfo(
        context, preset.name, preset.frequency, preset.pi, preset.ecc, FytPhysicalRadio.presetFrequencies(preset),
    )

    LaunchedEffect(preset, searchRevision) {
        loading = true
        error = null
        candidates =
            runCatching {
                ReliableFmStationLogoResolver.searchCandidates(
                    context = context,
                    stationName = preset.name,
                    frequency = preset.frequency,
                    pi = preset.pi,
                    ecc = preset.ecc,
                    allFrequencies = FytPhysicalRadio.presetFrequencies(preset),
                )
            }.getOrElse {
                error = it.message ?: "Logosuche fehlgeschlagen"
                emptyList()
            }
        if (candidates.isEmpty() && error == null) error = "Keine darstellbaren Logos gefunden"
        loading = false
    }

    fun choose(candidate: RadioLogoCandidate) {
        if (applying) return
        applying = true
        scope.launch {
            val stored =
                ReliableFmStationLogoResolver.setManualLogo(
                    context = context,
                    stationName = preset.name,
                    frequency = preset.frequency,
                    pi = preset.pi,
                    ecc = preset.ecc,
                    sourceUrl = candidate.url,
                    sourceLabel = candidate.source.label,
                )
            applying = false
            if (stored != null) onDismiss() else error = "Dieses Logo konnte nicht gespeichert werden"
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("FM-Senderlogo auswählen") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    FmStationArtwork(
                        stationName = preset.name,
                        frequency = preset.frequency,
                        pi = preset.pi,
                        ecc = preset.ecc,
                        size = 72.dp,
                        allFrequencies = FytPhysicalRadio.presetFrequencies(preset),
                    )
                    Column(Modifier.weight(1f)) {
                        Text(preset.name, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(
                            info?.sourceLabel ?: "Noch kein Logo gespeichert",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                when {
                    loading -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
                    candidates.isNotEmpty() -> {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            items(candidates, key = { it.url }) { candidate ->
                                Column(
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    modifier =
                                        Modifier
                                            .size(width = 126.dp, height = 150.dp)
                                            .clip(RoundedCornerShape(12.dp))
                                            .clickable { choose(candidate) }
                                            .padding(8.dp),
                                ) {
                                    AsyncImage(
                                        model = candidate.url,
                                        contentDescription = candidate.title,
                                        contentScale = ContentScale.Fit,
                                        modifier = Modifier.size(96.dp),
                                    )
                                    Text(
                                        candidate.source.label,
                                        style = MaterialTheme.typography.labelSmall,
                                        maxLines = 2,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                            }
                        }
                    }
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

                OutlinedButton(
                    onClick = {
                        ReliableFmStationLogoResolver.clearManualLogo(context, preset.name, preset.frequency, preset.pi, preset.ecc)
                        searchRevision += 1
                    },
                    enabled = info?.manual == true && !applying,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("MANUELLES LOGO ENTFERNEN") }

                Button(
                    onClick = {
                        scope.launch {
                            ReliableFmStationLogoResolver.invalidateAuto(context, preset.name, preset.frequency, preset.pi, preset.ecc)
                            ReliableFmStationLogoResolver.resolve(
                                context = context,
                                stationName = preset.name,
                                frequency = preset.frequency,
                                pi = preset.pi,
                                ecc = preset.ecc,
                                force = true,
                                allFrequencies = FytPhysicalRadio.presetFrequencies(preset),
                            )
                            searchRevision += 1
                        }
                    },
                    enabled = !loading && !applying,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("AUTOMATIK NEU SUCHEN") }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("FERTIG") } },
    )
}
