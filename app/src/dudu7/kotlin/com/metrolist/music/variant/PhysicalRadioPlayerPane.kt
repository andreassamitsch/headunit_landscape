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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.AsyncImage
import com.metrolist.music.LocalSyncUtils
import com.metrolist.music.R
import com.metrolist.music.db.entities.Song
import com.metrolist.music.db.entities.SongEntity
import com.metrolist.music.models.toMediaMetadata
import com.metrolist.music.playback.PlayerConnection
import com.metrolist.music.radio.fyt.FmNowPlayingResolver
import com.metrolist.music.radio.fyt.FmPresetOrderStore
import com.metrolist.music.radio.fyt.FmStationArtwork
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.tuneAdjacentFavourite
import com.metrolist.music.utils.SearchRoutes
import kotlinx.coroutines.flow.flowOf

@Composable
fun PhysicalRadioPlayerPane(
    radio: FytPhysicalRadio,
    playerConnection: PlayerConnection?,
) {
    val context = LocalContext.current
    val syncUtils = LocalSyncUtils.current
    val state by radio.state.collectAsStateWithLifecycle()
    val nowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
    val isStationFavourite =
        remember(state.frequency, state.presets) {
            state.presets.any { FmPresetOrderStore.sameFrequency(it.frequency, state.frequency) }
        }

    LaunchedEffect(state.isActive, state.displayStation, state.rt) {
        if (state.isActive) {
            FmNowPlayingResolver.resolve(state.displayStation, state.rt)
        } else {
            FmNowPlayingResolver.clear()
        }
    }

    val resolvedSong = nowPlaying.resolvedSong
    val librarySongFlow =
        remember(playerConnection, resolvedSong?.id) {
            if (playerConnection != null && resolvedSong != null) {
                playerConnection.database.song(resolvedSong.id)
            } else {
                flowOf<Song?>(null)
            }
        }
    val librarySong by librarySongFlow.collectAsStateWithLifecycle(initialValue = null)
    val isSongLiked = librarySong?.song?.liked == true

    val displayTitle =
        nowPlaying.title.takeIf { it.isNotBlank() }
            ?: state.displayStation
    val displayArtist =
        nowPlaying.artist?.takeIf { it.isNotBlank() }
            ?: if (displayTitle == state.displayStation) {
                "${FytPhysicalRadio.formatFrequency(state.frequency)} MHz • Antenne"
            } else {
                state.displayStation
            }

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
        modifier = Modifier.fillMaxSize().padding(horizontal = 18.dp, vertical = 8.dp),
    ) {
        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.weight(1f).fillMaxWidth(),
        ) {
            if (!nowPlaying.coverUrl.isNullOrBlank()) {
                AsyncImage(
                    model = nowPlaying.coverUrl,
                    contentDescription = "Cover $displayTitle",
                    contentScale = ContentScale.Fit,
                    error = painterResource(R.drawable.radio),
                    fallback = painterResource(R.drawable.radio),
                    modifier =
                        Modifier
                            .size(190.dp)
                            .clip(RoundedCornerShape(26.dp)),
                )
            } else {
                FmStationArtwork(
                    stationName = state.displayStation,
                    frequency = state.frequency,
                    size = 190.dp,
                )
            }
            if (nowPlaying.resolving) {
                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.align(Alignment.BottomEnd).size(24.dp),
                )
            }
        }

        Text(
            text = displayTitle,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable(enabled = nowPlaying.hasTrackMetadata) {
                        val artist = resolvedSong?.artists?.joinToString(" ") { it.name } ?: displayArtist
                        playerConnection?.requestRightPaneNavigation(
                            SearchRoutes.resultRoute("$artist $displayTitle".trim()),
                        )
                    },
        )
        Text(
            text = displayArtist,
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .clickable(enabled = nowPlaying.hasTrackMetadata) {
                        val matchedArtist = resolvedSong?.artists?.firstOrNull()
                        val route = matchedArtist?.id?.let { "artist/$it" }
                        if (route != null) {
                            playerConnection?.requestRightPaneNavigation(route)
                        } else {
                            playerConnection?.requestRadioArtistNavigation(displayArtist)
                        }
                    },
        )

        Spacer(Modifier.height(10.dp))

        Row(
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            IconButton(
                onClick = { radio.tuneAdjacentFavourite(context, next = false) },
                enabled = state.isActive && !state.isBusy,
                modifier = Modifier.size(58.dp),
            ) {
                Icon(
                    painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger FM-Favorit",
                    modifier = Modifier.size(34.dp),
                )
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

            IconButton(
                onClick = { radio.tuneAdjacentFavourite(context, next = true) },
                enabled = state.isActive && !state.isBusy,
                modifier = Modifier.size(58.dp),
            ) {
                Icon(
                    painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster FM-Favorit",
                    modifier = Modifier.size(34.dp),
                )
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
            IconButton(
                onClick = {
                    if (isStationFavourite) {
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
            ) {
                Icon(
                    painter = painterResource(R.drawable.radio),
                    contentDescription =
                        if (isStationFavourite) {
                            "FM-Sender aus Favoriten entfernen"
                        } else {
                            "FM-Sender als Favorit speichern"
                        },
                    tint =
                        if (isStationFavourite) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                )
            }
            Text(
                text = if (state.ta && state.taEnabled) "●  TA VERKEHR" else "●  FM LIVE",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color =
                    if (state.ta && state.taEnabled) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
            )
            IconButton(
                onClick = {
                    val matchedSong = resolvedSong ?: return@IconButton
                    val connection = playerConnection ?: return@IconButton
                    val currentLibrarySong = librarySong
                    connection.database.transaction {
                        val updated: SongEntity
                        if (currentLibrarySong == null) {
                            insert(matchedSong.toMediaMetadata(), SongEntity::toggleLike)
                            updated = matchedSong.toMediaMetadata().toSongEntity().toggleLike()
                        } else {
                            updated = currentLibrarySong.song.toggleLike()
                            update(updated)
                        }
                        syncUtils.likeSong(updated)
                    }
                },
                enabled = resolvedSong != null && playerConnection != null,
            ) {
                Icon(
                    painter = painterResource(if (isSongLiked) R.drawable.favorite else R.drawable.favorite_border),
                    contentDescription = if (isSongLiked) "Song-Like entfernen" else "Song auf YouTube Music liken",
                    tint =
                        if (isSongLiked) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                )
            }
            IconButton(onClick = { radio.step(true) }, enabled = !state.isBusy) {
                Text("+0,1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
        }

        Text(
            text =
                buildString {
                    append("${state.displayStation} • RSSI ${state.rssi}")
                    append(if (state.stereo) " • Stereo" else " • Mono")
                    if (state.pi != 0) append(" • PI ${state.pi.toString(16).uppercase()}")
                    val pty = FytPhysicalRadio.ptyLabel(state.pty)
                    if (pty.isNotBlank()) append(" • $pty")
                    if (state.afEnabled) append(" • AF")
                    if (state.tp) append(" • TP")
                    if (state.ta && state.taEnabled) append(" • TA")
                },
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.height(5.dp))
    }
}
