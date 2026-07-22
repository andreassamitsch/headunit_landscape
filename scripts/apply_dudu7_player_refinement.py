#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path: str, content: str) -> None:
    target = ROOT / path
    if not target.exists():
        raise SystemExit(f"Missing expected file: {path}")
    target.write_text(content, encoding="utf-8")
    print(f"Replaced {path}")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one match in {path}, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Updated {path}")


DUDU_CONTROLS = r'''package com.metrolist.music.variant

import androidx.annotation.DrawableRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.media3.common.Player
import com.metrolist.music.R
import com.metrolist.music.utils.makeTimeString

@Suppress("UNUSED_PARAMETER")
@Composable
fun ColumnScope.VehiclePlayerControls(
    title: String,
    artists: String,
    isPlaying: Boolean,
    isEnded: Boolean,
    isGuest: Boolean,
    isMuted: Boolean,
    canSkipPrevious: Boolean,
    canSkipNext: Boolean,
    sliderValue: Long,
    duration: Long,
    canSeek: Boolean,
    isFavorite: Boolean,
    shuffleModeEnabled: Boolean,
    repeatMode: Int,
    textColor: Color,
    playButtonContainerColor: Color,
    playButtonContentColor: Color,
    sideButtonContentColor: Color,
    onPrevious: () -> Unit,
    onPlayPause: () -> Unit,
    onNext: () -> Unit,
    onToggleShuffle: () -> Unit,
    onToggleRepeat: () -> Unit,
    onSliderValueChange: (Long) -> Unit,
    onSliderValueChangeFinished: () -> Unit,
    onStartRadio: () -> Unit,
    onToggleLike: () -> Unit,
    onTitleClick: () -> Unit,
    onArtistClick: () -> Unit,
    fallbackContent: @Composable ColumnScope.() -> Unit,
) {
    val safeDuration = duration.takeIf { it > 0 } ?: 0L
    val safeSliderValue = sliderValue.coerceIn(0L, safeDuration.coerceAtLeast(0L))
    val activeControlColor = MaterialTheme.colorScheme.primary
    val inactiveControlColor = sideButtonContentColor.copy(alpha = 0.58f)

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            color = textColor,
            modifier = Modifier.fillMaxWidth().clickable(onClick = onTitleClick),
        )
        Spacer(Modifier.height(1.dp))
        Text(
            text = artists,
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            color = textColor.copy(alpha = 0.78f),
            modifier = Modifier.fillMaxWidth().clickable(onClick = onArtistClick),
        )

        Spacer(Modifier.height(5.dp))

        Row(
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            VehicleAction(
                icon = R.drawable.shuffle,
                description =
                    if (shuffleModeEnabled) {
                        "Zufallswiedergabe aktiviert"
                    } else {
                        "Zufallswiedergabe deaktiviert"
                    },
                color = if (shuffleModeEnabled) activeControlColor else inactiveControlColor,
                onClick = onToggleShuffle,
                buttonSize = 46.dp,
                iconSize = 27.dp,
                enabled = !isGuest,
            )

            IconButton(
                onClick = onPrevious,
                enabled = canSkipPrevious,
                modifier = Modifier.size(48.dp),
                colors = IconButtonDefaults.iconButtonColors(contentColor = sideButtonContentColor),
            ) {
                Icon(
                    painter = painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger Titel",
                    modifier = Modifier.size(30.dp),
                )
            }

            FilledIconButton(
                onClick = onPlayPause,
                shape = CircleShape,
                colors =
                    IconButtonDefaults.filledIconButtonColors(
                        containerColor = playButtonContainerColor,
                        contentColor = playButtonContentColor,
                    ),
                modifier = Modifier.size(68.dp),
            ) {
                Icon(
                    painter =
                        painterResource(
                            when {
                                isGuest && isMuted -> R.drawable.volume_off
                                isGuest -> R.drawable.volume_up
                                isEnded -> R.drawable.replay
                                isPlaying -> R.drawable.pause
                                else -> R.drawable.play
                            },
                        ),
                    contentDescription = "Wiedergabe",
                    modifier = Modifier.size(36.dp),
                )
            }

            IconButton(
                onClick = onNext,
                enabled = canSkipNext,
                modifier = Modifier.size(48.dp),
                colors = IconButtonDefaults.iconButtonColors(contentColor = sideButtonContentColor),
            ) {
                Icon(
                    painter = painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster Titel",
                    modifier = Modifier.size(30.dp),
                )
            }

            VehicleAction(
                icon =
                    when (repeatMode) {
                        Player.REPEAT_MODE_ONE -> R.drawable.repeat_one
                        else -> R.drawable.repeat
                    },
                description =
                    when (repeatMode) {
                        Player.REPEAT_MODE_ONE -> "Aktuellen Titel wiederholen"
                        Player.REPEAT_MODE_ALL -> "Warteschlange wiederholen"
                        else -> "Wiederholen deaktiviert"
                    },
                color = if (repeatMode == Player.REPEAT_MODE_OFF) inactiveControlColor else activeControlColor,
                onClick = onToggleRepeat,
                buttonSize = 46.dp,
                iconSize = 27.dp,
                enabled = !isGuest,
            )
        }

        Spacer(Modifier.height(1.dp))

        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            VehicleAction(
                icon = R.drawable.radio,
                description = "Radio starten",
                color = textColor,
                onClick = onStartRadio,
                buttonSize = 46.dp,
                iconSize = 27.dp,
            )

            Column(
                modifier = Modifier.weight(1f).padding(horizontal = 2.dp),
            ) {
                Slider(
                    value = safeSliderValue.toFloat(),
                    valueRange = 0f..safeDuration.coerceAtLeast(1L).toFloat(),
                    onValueChange = { onSliderValueChange(it.toLong()) },
                    onValueChangeFinished = onSliderValueChangeFinished,
                    enabled = canSeek && safeDuration > 0,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp),
                ) {
                    Text(
                        text = makeTimeString(safeSliderValue),
                        style = MaterialTheme.typography.labelMedium,
                        color = textColor,
                    )
                    Text(
                        text = if (safeDuration > 0) makeTimeString(safeDuration) else "",
                        style = MaterialTheme.typography.labelMedium,
                        color = textColor,
                    )
                }
            }

            VehicleAction(
                icon = if (isFavorite) R.drawable.favorite else R.drawable.favorite_border,
                description = "Gefällt mir",
                color = if (isFavorite) activeControlColor else textColor,
                onClick = onToggleLike,
                buttonSize = 46.dp,
                iconSize = 28.dp,
            )
        }
    }
}

@Composable
private fun VehicleAction(
    @DrawableRes icon: Int,
    description: String,
    color: Color,
    onClick: () -> Unit,
    buttonSize: Dp,
    iconSize: Dp,
    enabled: Boolean = true,
) {
    IconButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.size(buttonSize),
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = description,
            tint = color,
            modifier = Modifier.size(iconSize),
        )
    }
}
'''

STANDARD_CONTROLS = r'''package com.metrolist.music.variant

import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

@Suppress("UNUSED_PARAMETER")
@Composable
fun ColumnScope.VehiclePlayerControls(
    title: String,
    artists: String,
    isPlaying: Boolean,
    isEnded: Boolean,
    isGuest: Boolean,
    isMuted: Boolean,
    canSkipPrevious: Boolean,
    canSkipNext: Boolean,
    sliderValue: Long,
    duration: Long,
    canSeek: Boolean,
    isFavorite: Boolean,
    shuffleModeEnabled: Boolean,
    repeatMode: Int,
    textColor: Color,
    playButtonContainerColor: Color,
    playButtonContentColor: Color,
    sideButtonContentColor: Color,
    onPrevious: () -> Unit,
    onPlayPause: () -> Unit,
    onNext: () -> Unit,
    onToggleShuffle: () -> Unit,
    onToggleRepeat: () -> Unit,
    onSliderValueChange: (Long) -> Unit,
    onSliderValueChangeFinished: () -> Unit,
    onStartRadio: () -> Unit,
    onToggleLike: () -> Unit,
    onTitleClick: () -> Unit,
    onArtistClick: () -> Unit,
    fallbackContent: @Composable ColumnScope.() -> Unit,
) {
    fallbackContent()
}
'''

write("app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt", DUDU_CONTROLS)
write("app/src/standard/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt", STANDARD_CONTROLS)

player_path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
replace_once(
    player_path,
    """    val repeatMode by playerConnection.repeatMode.collectAsStateWithLifecycle()\n    val canSkipPrevious by playerConnection.canSkipPrevious.collectAsStateWithLifecycle()\n""",
    """    val repeatMode by playerConnection.repeatMode.collectAsStateWithLifecycle()\n    val shuffleModeEnabled by playerConnection.shuffleModeEnabled.collectAsStateWithLifecycle()\n    val canSkipPrevious by playerConnection.canSkipPrevious.collectAsStateWithLifecycle()\n""",
)
replace_once(player_path, "landscapeHorizontalPadding = 8.dp,", "landscapeHorizontalPadding = 2.dp,")
replace_once(
    player_path,
    """                                isFavorite = isFavorite,\n                                textColor = TextBackgroundColor,\n""",
    """                                isFavorite = isFavorite,\n                                shuffleModeEnabled = shuffleModeEnabled,\n                                repeatMode = repeatMode,\n                                textColor = TextBackgroundColor,\n""",
)
replace_once(
    player_path,
    """                                onNext = playerConnection::seekToNext,\n                                onSliderValueChange = {\n""",
    """                                onNext = playerConnection::seekToNext,\n                                onToggleShuffle = {\n                                    playerConnection.player.shuffleModeEnabled =\n                                        !playerConnection.player.shuffleModeEnabled\n                                },\n                                onToggleRepeat = playerConnection.player::toggleRepeatMode,\n                                onSliderValueChange = {\n""",
)
replace_once(
    player_path,
    """                                onShare = {\n                                    val intent =\n                                        Intent().apply {\n                                            action = Intent.ACTION_SEND\n                                            type = \"text/plain\"\n                                            putExtra(\n                                                Intent.EXTRA_TEXT,\n                                                \"https://music.youtube.com/watch?v=${currentMediaMetadata.id}\",\n                                            )\n                                        }\n                                    context.startActivity(Intent.createChooser(intent, null))\n                                },\n""",
    "",
)

queue_path = "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt"
replace_once(
    queue_path,
    """                                top = ListItemHeight + 8.dp,\n                                bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp,\n""",
    """                                top = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp,\n                                bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp,\n""",
)
queue_header = r'''            Row(
                horizontalArrangement = Arrangement.spacedBy(6.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier =
                    Modifier
                        .height(ListItemHeight)
                        .padding(horizontal = 12.dp),
            ) {
                Text(
                    text = queueTitle.orEmpty(),
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )

                AnimatedVisibility(
                    visible = !inSelectMode,
                    enter = fadeIn() + slideInVertically { it },
                    exit = fadeOut() + slideOutVertically { it },
                ) {
                    Row {
                        VehicleQueueActions()
                        IconButton(
                            onClick = { locked = !locked },
                            modifier = Modifier.padding(horizontal = 6.dp),
                        ) {
                            Icon(
                                painter = painterResource(if (locked) R.drawable.lock else R.drawable.lock_open),
                                contentDescription = null,
                            )
                        }
                    }
                }

                Column(
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                    horizontalAlignment = Alignment.End,
                ) {
                    Text(
                        text =
                            pluralStringResource(
                                R.plurals.n_song,
                                queueWindows.size,
                                queueWindows.size,
                            ),
                        style = MaterialTheme.typography.bodyMedium,
                    )

                    Text(
                        text = makeTimeString(queueLength * 1000L),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
'''
replace_once(
    queue_path,
    queue_header,
    """            if (!VehicleVariantConfig.isDudu7) {\n${queue_header.replace(chr(10), chr(10) + '    ').rstrip()}\n            }\n""",
)

thumbnail_path = "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt"
replace_once(
    thumbnail_path,
    """import com.metrolist.music.R\nimport com.metrolist.music.constants.CropAlbumArtKey\n""",
    """import com.metrolist.music.R\nimport com.metrolist.music.constants.CropAlbumArtKey\nimport com.metrolist.music.variant.VehicleVariantConfig\n""",
)
replace_once(
    thumbnail_path,
    ".padding(horizontal = PlayerHorizontalPadding)\n            .graphicsLayer {",
    ".padding(horizontal = if (isLandscape) landscapeHorizontalPadding else PlayerHorizontalPadding)\n            .graphicsLayer {",
)
replace_once(
    thumbnail_path,
    r'''            // Cast button at top-right corner of thumbnail
            CastButton(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(8.dp),
                tintColor = textBackgroundColor
            )
''',
    r'''            if (!VehicleVariantConfig.isDudu7) {
                CastButton(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .padding(8.dp),
                    tintColor = textBackgroundColor,
                )
            }
''',
)

smoke_path = "scripts/dudu7_ui_smoke.sh"
replace_once(
    smoke_path,
    """find_and_tap \"playback\" \"wiedergabe\" \"play\" \"pause\" && capture \"playback-toggle\" || true\nfind_and_tap \"like\" \"gefällt mir\" \"like\" && capture \"like\" || true\nfind_and_tap \"radio\" \"radio starten\" && capture \"radio\" || true\n""",
    """find_and_tap \"playback\" \"wiedergabe\" \"play\" \"pause\" && capture \"playback-toggle\" || true\nfind_and_tap \"shuffle\" \"zufallswiedergabe\" \"shuffle\" && capture \"shuffle\" || true\nfind_and_tap \"repeat\" \"wiederholen\" \"repeat\" && capture \"repeat\" || true\nfind_and_tap \"like\" \"gefällt mir\" \"like\" && capture \"like\" || true\nfind_and_tap \"radio\" \"radio starten\" && capture \"radio\" || true\n""",
)

print("Dudu7 player refinement applied successfully")
