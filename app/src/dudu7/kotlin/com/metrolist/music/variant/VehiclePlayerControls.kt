package com.metrolist.music.variant

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
