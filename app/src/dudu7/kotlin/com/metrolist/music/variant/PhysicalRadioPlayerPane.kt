package com.metrolist.music.variant

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.core.content.ContextCompat
import coil3.compose.AsyncImage
import com.metrolist.music.LocalSyncUtils
import com.metrolist.music.R
import com.metrolist.music.db.entities.Song
import com.metrolist.music.db.entities.SongEntity
import com.metrolist.music.models.toMediaMetadata
import com.metrolist.music.playback.PlayerConnection
import com.metrolist.music.ui.player.VehicleRadioPlayerMetrics
import com.metrolist.music.recognition.MusicRecognitionService
import com.metrolist.music.radio.fyt.FmNowPlayingResolver
import com.metrolist.music.radio.fyt.FmPresetOrderStore
import com.metrolist.music.radio.fyt.FmStationArtwork
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.tuneAdjacentFavourite
import com.metrolist.music.utils.SearchRoutes
import com.metrolist.shazamkit.models.RecognitionStatus
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.launch
import kotlin.math.abs

@Composable
fun PhysicalRadioPlayerPane(
    radio: FytPhysicalRadio,
    playerConnection: PlayerConnection?,
    titleColor: Color,
    secondaryTextColor: Color,
    playButtonContainerColor: Color,
    playButtonContentColor: Color,
    sideButtonContentColor: Color,
    actionColor: Color,
) {
    val context = LocalContext.current
    val syncUtils = LocalSyncUtils.current
    val state by radio.state.collectAsStateWithLifecycle()
    val nowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
    val recognitionStatus by MusicRecognitionService.recognitionStatus.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var recognitionRequested by remember { mutableStateOf(false) }
    var recognitionFrequency by remember { mutableStateOf<Float?>(null) }
    var lastFmIdentity by remember { mutableStateOf("") }
    val recognitionInProgress =
        recognitionRequested &&
            (recognitionStatus is RecognitionStatus.Listening || recognitionStatus is RecognitionStatus.Processing)

    val beginFmRecognition: () -> Unit = {
        recognitionRequested = true
        recognitionFrequency = state.frequency
        MusicRecognitionService.reset()
        scope.launch { MusicRecognitionService.recognize(context) }
        Unit
    }
    val recordPermissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            if (granted) {
                beginFmRecognition()
            } else {
                Toast.makeText(context, "Mikrofonberechtigung für Musikerkennung fehlt", Toast.LENGTH_SHORT).show()
            }
        }

    LaunchedEffect(recognitionStatus, recognitionRequested, state.frequency, state.isActive) {
        if (!recognitionRequested) return@LaunchedEffect
        when (val status = recognitionStatus) {
            is RecognitionStatus.Success -> {
                val requestedFrequency = recognitionFrequency
                if (state.isActive && requestedFrequency != null && abs(state.frequency - requestedFrequency) < 0.05f) {
                    FmNowPlayingResolver.applyRecognized(state.displayStation, status.result)
                    Toast
                        .makeText(
                            context,
                            "Erkannt: ${status.result.artist} – ${status.result.title}",
                            Toast.LENGTH_SHORT,
                        ).show()
                }
                recognitionRequested = false
                recognitionFrequency = null
                MusicRecognitionService.reset()
            }

            is RecognitionStatus.NoMatch -> {
                Toast.makeText(context, "Titel konnte nicht erkannt werden", Toast.LENGTH_SHORT).show()
                recognitionRequested = false
                recognitionFrequency = null
                MusicRecognitionService.reset()
            }

            is RecognitionStatus.Error -> {
                Toast.makeText(context, status.message, Toast.LENGTH_SHORT).show()
                recognitionRequested = false
                recognitionFrequency = null
                MusicRecognitionService.reset()
            }

            else -> Unit
        }
    }
    val currentPreset =
        remember(state.frequency, state.pi, state.presets) {
            state.presets.firstOrNull {
                FytPhysicalRadio.presetMatches(it, state.frequency, state.pi)
            }
        }
    val isStationFavourite = currentPreset != null

    LaunchedEffect(state.isActive, state.frequency, state.pi, state.displayStation, state.rt) {
        if (state.isActive) {
            val identity = "${state.displayStation}|${state.frequency}|${state.pi}|${state.ecc}"
            if (identity != lastFmIdentity) {
                FmNowPlayingResolver.clear()
                lastFmIdentity = identity
            }
            FmNowPlayingResolver.resolve(state.displayStation, state.rt)
        } else {
            lastFmIdentity = ""
            FmNowPlayingResolver.clear()
        }
    }

    val resolvedSong = nowPlaying.resolvedSong
    val hasRecognizedTrackArtwork = nowPlaying.hasTrackMetadata && !nowPlaying.coverUrl.isNullOrBlank()
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
                "${FytPhysicalRadio.formatFrequency(state.frequency)} MHz"
            } else {
                state.displayStation
            }

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
        modifier = Modifier.fillMaxSize(),
    ) {
        BoxWithConstraints(
            contentAlignment = Alignment.Center,
            modifier = Modifier.weight(1f).fillMaxWidth().padding(top = 2.dp, bottom = 2.dp),
        ) {
            val artworkSize =
                (minOf(maxWidth, maxHeight) -
                    (VehicleRadioPlayerMetrics.ArtworkHorizontalPadding * 2)).coerceAtLeast(0.dp)
            val artworkShape = RoundedCornerShape(VehicleRadioPlayerMetrics.ArtworkCornerRadius)
            Box(modifier = Modifier.size(artworkSize)) {
                if (hasRecognizedTrackArtwork) {
                    AsyncImage(
                        model = nowPlaying.coverUrl,
                        contentDescription = "Cover $displayTitle",
                        contentScale = ContentScale.Fit,
                        error = painterResource(R.drawable.radio),
                        fallback = painterResource(R.drawable.radio),
                        modifier = Modifier.fillMaxSize().clip(artworkShape),
                    )
                    Box(
                        modifier =
                            Modifier
                                .align(Alignment.BottomEnd)
                                .padding(10.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White.copy(alpha = 0.78f))
                                .padding(3.dp)
                                .graphicsLayer { alpha = 0.86f },
                    ) {
                        FmStationArtwork(
                            stationName = state.displayStation,
                            frequency = state.frequency,
                            pi = state.pi,
                            ecc = state.ecc,
                            size = 52.dp,
                            allFrequencies =
                                (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                                    state.alternativeFrequencies + state.frequency),
                        )
                    }
                } else {
                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier.fillMaxSize().clip(artworkShape),
                    ) {
                        FmStationArtwork(
                            stationName = state.displayStation,
                            frequency = state.frequency,
                            pi = state.pi,
                            ecc = state.ecc,
                            size = artworkSize,
                            allFrequencies =
                                (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                                    state.alternativeFrequencies + state.frequency),
                        )
                    }
                }
                if (nowPlaying.resolving) {
                    CircularProgressIndicator(
                        color = actionColor,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.BottomEnd).padding(4.dp).size(24.dp),
                    )
                }
            }
        }

        Text(
            text = displayTitle,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            color = titleColor,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
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
            color = secondaryTextColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 8.dp)
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

        Spacer(Modifier.height(5.dp))

        Row(
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
        ) {
            IconButton(
                onClick = { radio.tuneAdjacentFavourite(context, next = false) },
                enabled = state.isActive && !state.isBusy,
                modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextButtonSize),
            ) {
                Icon(
                    painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger FM-Favorit",
                    tint = sideButtonContentColor,
                    modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextIconSize),
                )
            }

            FilledIconButton(
                onClick = {
                    if (!state.isActive) {
                        playerConnection?.pause()
                        radio.powerOn()
                    } else {
                        radio.powerOff()
                    }
                },
                shape = CircleShape,
                colors =
                    IconButtonDefaults.filledIconButtonColors(
                        containerColor = playButtonContainerColor,
                        contentColor = playButtonContentColor,
                    ),
                enabled = !state.isBusy,
                modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayButtonSize),
            ) {
                Icon(
                    painter =
                        painterResource(
                            if (!state.isActive) R.drawable.play else R.drawable.pause,
                        ),
                    contentDescription = if (state.isActive) "FM-Radio ausschalten" else "FM-Radio einschalten",
                    modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayIconSize),
                )
            }

            IconButton(
                onClick = { radio.tuneAdjacentFavourite(context, next = true) },
                enabled = state.isActive && !state.isBusy,
                modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextButtonSize),
            ) {
                Icon(
                    painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster FM-Favorit",
                    tint = sideButtonContentColor,
                    modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextIconSize),
                )
            }
        }

        Spacer(Modifier.height(4.dp))

        Box(
            contentAlignment = Alignment.Center,
            modifier = Modifier.fillMaxWidth().height(VehicleRadioPlayerMetrics.SecondaryActionButtonSize).padding(horizontal = 8.dp),
        ) {
            IconButton(
                onClick = {
                    if (isStationFavourite) {
                        val preset = currentPreset ?: return@IconButton
                        val remaining = state.presets.filterNot { it == preset }
                        radio.removePreset(preset)
                        FmPresetOrderStore.persist(context, remaining)
                    } else {
                        radio.saveCurrentPreset()
                    }
                },
                enabled = state.isActive,
                modifier = Modifier.align(Alignment.CenterStart).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),
            ) {
                Icon(
                    painter = painterResource(R.drawable.radio),
                    contentDescription =
                        if (isStationFavourite) {
                            "FM-Sender aus Favoriten entfernen"
                        } else {
                            "FM-Sender als Favorit speichern"
                        },
                    tint = if (isStationFavourite) actionColor else sideButtonContentColor,
                    modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionIconSize),
                )
            }

            Text(
                text = if (state.ta && state.taEnabled) "●  TA VERKEHR" else "●  FM LIVE",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = if (state.ta && state.taEnabled) MaterialTheme.colorScheme.error else actionColor,
                textAlign = TextAlign.Center,
                modifier = Modifier.align(Alignment.Center),
            )

            if (resolvedSong != null && playerConnection != null) {
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
                    modifier = Modifier.align(Alignment.CenterEnd).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),
                ) {
                    Icon(
                        painter = painterResource(if (isSongLiked) R.drawable.favorite else R.drawable.favorite_border),
                        contentDescription = if (isSongLiked) "Song-Like entfernen" else "Song auf YouTube Music liken",
                        tint = if (isSongLiked) actionColor else sideButtonContentColor,
                        modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize),
                    )
                }
            } else {
                IconButton(
                    onClick = {
                        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                            PackageManager.PERMISSION_GRANTED
                        ) {
                            beginFmRecognition()
                        } else {
                            recordPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    },
                    enabled = state.isActive && !recognitionInProgress,
                    modifier = Modifier.align(Alignment.CenterEnd).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),
                ) {
                    if (recognitionInProgress) {
                        CircularProgressIndicator(color = actionColor, strokeWidth = 2.dp, modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize))
                    } else {
                        Icon(
                            painter = painterResource(R.drawable.manage_search),
                            contentDescription = "FM-Musik erkennen",
                            tint = sideButtonContentColor,
                            modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize),
                        )
                    }
                }
            }
        }
    }
}
