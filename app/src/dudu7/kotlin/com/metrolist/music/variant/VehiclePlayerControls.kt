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
import androidx.compose.ui.unit.dp
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
    textColor: Color,
    playButtonContainerColor: Color,
    playButtonContentColor: Color,
    sideButtonContentColor: Color,
    onPrevious: () -> Unit,
    onPlayPause: () -> Unit,
    onNext: () -> Unit,
    onSliderValueChange: (Long) -> Unit,
    onSliderValueChangeFinished: () -> Unit,
    onStartRadio: () -> Unit,
    onShare: () -> Unit,
    onToggleLike: () -> Unit,
    onTitleClick: () -> Unit,
    onArtistClick: () -> Unit,
    fallbackContent: @Composable ColumnScope.() -> Unit,
) {
    val safeDuration = duration.takeIf { it > 0 } ?: 0L
    val safeSliderValue = sliderValue.coerceIn(0L, safeDuration.coerceAtLeast(0L))

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
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
        Spacer(Modifier.height(2.dp))
        Text(
            text = artists,
            style = MaterialTheme.typography.titleMedium,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            color = textColor.copy(alpha = 0.78f),
            modifier = Modifier.fillMaxWidth().clickable(onClick = onArtistClick),
        )

        Spacer(Modifier.height(8.dp))

        Row(
            horizontalArrangement = Arrangement.spacedBy(24.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(
                onClick = onPrevious,
                enabled = canSkipPrevious,
                modifier = Modifier.size(52.dp),
                colors = IconButtonDefaults.iconButtonColors(contentColor = sideButtonContentColor),
            ) {
                Icon(
                    painter = painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger Titel",
                    modifier = Modifier.size(31.dp),
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
                modifier = Modifier.size(52.dp),
                colors = IconButtonDefaults.iconButtonColors(contentColor = sideButtonContentColor),
            ) {
                Icon(
                    painter = painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster Titel",
                    modifier = Modifier.size(31.dp),
                )
            }
        }

        Spacer(Modifier.height(5.dp))

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

        Spacer(Modifier.height(4.dp))

        Row(
            horizontalArrangement = Arrangement.spacedBy(24.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            VehicleAction(
                icon = R.drawable.radio,
                description = "Radio starten",
                color = textColor,
                onClick = onStartRadio,
            )
            VehicleAction(
                icon = R.drawable.share,
                description = "Teilen",
                color = textColor,
                onClick = onShare,
            )
            VehicleAction(
                icon = if (isFavorite) R.drawable.favorite else R.drawable.favorite_border,
                description = "Gefällt mir",
                color = if (isFavorite) MaterialTheme.colorScheme.primary else textColor,
                onClick = onToggleLike,
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
) {
    IconButton(
        onClick = onClick,
        modifier = Modifier.size(52.dp),
    ) {
        Icon(
            painter = painterResource(icon),
            contentDescription = description,
            tint = color,
            modifier = Modifier.size(29.dp),
        )
    }
}
