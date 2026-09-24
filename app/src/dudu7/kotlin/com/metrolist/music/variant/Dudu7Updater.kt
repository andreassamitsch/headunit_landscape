package com.metrolist.music.variant

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.metrolist.music.BuildConfig
import com.metrolist.music.update.Dudu7UpdateManager
import com.metrolist.music.update.Dudu7UpdatePhase

@Composable
fun Dudu7UpdaterCard() {
    val context = LocalContext.current
    val manager = remember(context.applicationContext) { Dudu7UpdateManager(context.applicationContext) }
    val state by manager.state.collectAsStateWithLifecycle()
    val candidate = state.candidate

    LaunchedEffect(Unit) { manager.checkForUpdates() }

    ElevatedCard(
        shape = RoundedCornerShape(28.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.linearGradient(
                        listOf(
                            MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.72f),
                            MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.38f),
                            MaterialTheme.colorScheme.surfaceContainerHigh,
                        ),
                    ),
                ),
        ) {
            Column(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxWidth().padding(20.dp),
            ) {
                Row(
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Dudu7 Update Center",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Black,
                        )
                        Text(
                            text = "Installiert: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = when (state.phase) {
                            Dudu7UpdatePhase.AVAILABLE, Dudu7UpdatePhase.READY -> MaterialTheme.colorScheme.primary
                            Dudu7UpdatePhase.ERROR -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.surfaceContainerHighest
                        },
                    ) {
                        Text(
                            text = when (state.phase) {
                                Dudu7UpdatePhase.AVAILABLE -> "NEU"
                                Dudu7UpdatePhase.READY -> "BEREIT"
                                Dudu7UpdatePhase.CURRENT -> "AKTUELL"
                                Dudu7UpdatePhase.ERROR -> "FEHLER"
                                else -> "DUDU7"
                            },
                            color = when (state.phase) {
                                Dudu7UpdatePhase.AVAILABLE, Dudu7UpdatePhase.READY -> MaterialTheme.colorScheme.onPrimary
                                Dudu7UpdatePhase.ERROR -> MaterialTheme.colorScheme.onError
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            },
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        )
                    }
                }

                if (candidate != null) {
                    Text(
                        text = "Verfügbar: ${candidate.manifest.versionName} (${candidate.manifest.versionCode})",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    if (candidate.release.publishedAt.isNotBlank()) {
                        Text(
                            text = "Veröffentlicht: ${candidate.release.publishedAt.replace('T', ' ').removeSuffix("Z")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val notes = candidate.release.notes
                        .replace("**", "")
                        .replace(Regex("(?m)^#{1,6}\\s*"), "")
                        .trim()
                    if (notes.isNotBlank()) {
                        Text(
                            text = notes,
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 8,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }

                if (state.message.isNotBlank()) {
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (state.phase == Dudu7UpdatePhase.ERROR) {
                            MaterialTheme.colorScheme.error
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }

                if (state.phase == Dudu7UpdatePhase.DOWNLOADING || state.phase == Dudu7UpdatePhase.VERIFYING) {
                    LinearProgressIndicator(
                        progress = { state.progress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        text = if (state.phase == Dudu7UpdatePhase.DOWNLOADING) {
                            "${(state.progress * 100).toInt()} %"
                        } else {
                            "Integrität wird geprüft"
                        },
                        style = MaterialTheme.typography.labelMedium,
                    )
                }

                Row(
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    OutlinedButton(
                        onClick = manager::checkForUpdates,
                        enabled = state.phase != Dudu7UpdatePhase.CHECKING &&
                            state.phase != Dudu7UpdatePhase.DOWNLOADING &&
                            state.phase != Dudu7UpdatePhase.VERIFYING,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(if (state.phase == Dudu7UpdatePhase.CHECKING) "Prüfe …" else "Neu prüfen")
                    }
                    when (state.phase) {
                        Dudu7UpdatePhase.AVAILABLE -> {
                            Button(onClick = manager::downloadAndVerify, modifier = Modifier.weight(1f)) {
                                Text("Laden & prüfen")
                            }
                        }
                        Dudu7UpdatePhase.READY, Dudu7UpdatePhase.PERMISSION_REQUIRED -> {
                            Button(onClick = manager::installVerifiedUpdate, modifier = Modifier.weight(1f)) {
                                Text(if (state.phase == Dudu7UpdatePhase.PERMISSION_REQUIRED) "Installation fortsetzen" else "Installieren")
                            }
                        }
                        else -> Unit
                    }
                }

                Spacer(Modifier.height(1.dp))
                Text(
                    text = "Vor der Installation werden SHA-256, Paketname, VersionCode und App-Signatur geprüft. Android führt die Installation anschließend selbst aus.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
