#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


root = Path(__file__).resolve().parents[1]
resolver = root / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmNowPlayingResolver.kt"
replace_once(
    resolver,
    'import com.metrolist.music.ui.utils.resize\n',
    'import com.metrolist.music.ui.utils.resize\nimport com.metrolist.shazamkit.models.RecognitionResult\n',
)
replace_once(
    resolver,
    '''    fun clear() {
        lookupJob?.cancel()
        lookupJob = null
        _state.value = NowPlaying()
    }
''',
    '''    /** Apply a Shazam-compatible audio fingerprint result to physical FM. */
    fun applyRecognized(
        stationName: String,
        result: RecognitionResult,
    ) {
        lookupJob?.cancel()
        val artist = result.artist.trim()
        val title = result.title.trim()
        if (artist.isBlank() || title.isBlank()) return
        val preferredCover = result.coverArtHqUrl ?: result.coverArtUrl
        val key =
            "fingerprint|${normalizeTrackText(stationName)}|" +
                "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        _state.value =
            NowPlaying(
                key = key,
                stationName = stationName,
                rawText = "$artist - $title",
                title = title,
                artist = artist,
                coverUrl = preferredCover,
                hasTrackMetadata = true,
                resolving = true,
            )

        val lookupKey = "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        if (cache.containsKey(lookupKey)) {
            applyResolved(key, cache[lookupKey], preferredCover)
            return
        }
        lookupJob =
            scope.launch {
                val song =
                    runCatching {
                        YouTube
                            .search("$artist - $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { candidate -> isStrongMatch(candidate, artist, title) }
                    }.onFailure {
                        Timber.tag(TAG).w(it, "FM fingerprint YTM lookup failed for %s - %s", artist, title)
                    }.getOrNull()
                cache[lookupKey] = song
                applyResolved(key, song, preferredCover)
            }
    }

    fun clear() {
        lookupJob?.cancel()
        lookupJob = null
        _state.value = NowPlaying()
    }
''',
)
replace_once(
    resolver,
    '''    private fun applyResolved(
        key: String,
        song: SongItem?,
    ) {
''',
    '''    private fun applyResolved(
        key: String,
        song: SongItem?,
        preferredCover: String? = null,
    ) {
''',
)
replace_once(
    resolver,
    '                    coverUrl = song.thumbnail.resize(1200, 1200),\n',
    '                    coverUrl = preferredCover ?: song.thumbnail.resize(1200, 1200),\n',
)
replace_once(
    resolver,
    '''            } else {
                current.copy(resolving = false)
            }
''',
    '''            } else {
                current.copy(
                    coverUrl = preferredCover ?: current.coverUrl,
                    resolving = false,
                )
            }
''',
)

player = root / "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt"
replace_once(
    player,
    'package com.metrolist.music.variant\n\n',
    'package com.metrolist.music.variant\n\n'
    'import android.Manifest\n'
    'import android.content.pm.PackageManager\n'
    'import android.widget.Toast\n'
    'import androidx.activity.compose.rememberLauncherForActivityResult\n'
    'import androidx.activity.result.contract.ActivityResultContracts\n',
)
replace_once(
    player,
    'import androidx.compose.foundation.layout.Box\n',
    'import androidx.compose.foundation.layout.Box\nimport androidx.compose.foundation.layout.BoxWithConstraints\n',
)
replace_once(
    player,
    'import androidx.compose.runtime.getValue\n'
    'import androidx.compose.runtime.remember\n',
    'import androidx.compose.runtime.getValue\n'
    'import androidx.compose.runtime.mutableStateOf\n'
    'import androidx.compose.runtime.remember\n'
    'import androidx.compose.runtime.rememberCoroutineScope\n'
    'import androidx.compose.runtime.setValue\n',
)
replace_once(
    player,
    'import androidx.lifecycle.compose.collectAsStateWithLifecycle\n',
    'import androidx.lifecycle.compose.collectAsStateWithLifecycle\nimport androidx.core.content.ContextCompat\n',
)
replace_once(
    player,
    'import com.metrolist.music.playback.PlayerConnection\n',
    'import com.metrolist.music.playback.PlayerConnection\nimport com.metrolist.music.recognition.MusicRecognitionService\n',
)
replace_once(
    player,
    'import com.metrolist.music.utils.SearchRoutes\n'
    'import kotlinx.coroutines.flow.flowOf\n',
    'import com.metrolist.music.utils.SearchRoutes\n'
    'import com.metrolist.shazamkit.models.RecognitionStatus\n'
    'import kotlinx.coroutines.flow.flowOf\n'
    'import kotlinx.coroutines.launch\n'
    'import kotlin.math.abs\n',
)
replace_once(
    player,
    '''    val state by radio.state.collectAsStateWithLifecycle()
    val nowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
''',
    '''    val state by radio.state.collectAsStateWithLifecycle()
    val nowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
    val recognitionStatus by MusicRecognitionService.recognitionStatus.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var recognitionRequested by remember { mutableStateOf(false) }
    var recognitionFrequency by remember { mutableStateOf<Float?>(null) }
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
''',
)
replace_once(
    player,
    '''        Box(
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
''',
    '''        BoxWithConstraints(
            contentAlignment = Alignment.Center,
            modifier = Modifier.weight(1f).fillMaxWidth(),
        ) {
            // Match the large WebRadio artwork footprint instead of the old 190 dp FM tile.
            val artworkSize = minOf(maxWidth, maxHeight).coerceAtMost(320.dp)
            if (!nowPlaying.coverUrl.isNullOrBlank()) {
                AsyncImage(
                    model = nowPlaying.coverUrl,
                    contentDescription = "Cover $displayTitle",
                    contentScale = ContentScale.Fit,
                    error = painterResource(R.drawable.radio),
                    fallback = painterResource(R.drawable.radio),
                    modifier =
                        Modifier
                            .size(artworkSize)
                            .clip(RoundedCornerShape(26.dp)),
                )
            } else {
                FmStationArtwork(
                    stationName = state.displayStation,
                    frequency = state.frequency,
                    size = artworkSize,
                )
            }
            if (nowPlaying.resolving) {
                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.align(Alignment.BottomEnd).size(24.dp),
                )
            }
        }
''',
)
replace_once(
    player,
    '''            Text(
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
''',
    '''            Text(
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
                    if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) ==
                        PackageManager.PERMISSION_GRANTED
                    ) {
                        beginFmRecognition()
                    } else {
                        recordPermissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                    }
                },
                enabled = state.isActive && !recognitionInProgress,
            ) {
                if (recognitionInProgress) {
                    CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(24.dp))
                } else {
                    Icon(
                        painter = painterResource(R.drawable.search),
                        contentDescription = "FM-Musik erkennen",
                    )
                }
            }
            IconButton(
                onClick = {
                    val matchedSong = resolvedSong ?: return@IconButton
''',
)

print("Applied Dudu7 FM artwork and fingerprint recognition round 3 patches")
