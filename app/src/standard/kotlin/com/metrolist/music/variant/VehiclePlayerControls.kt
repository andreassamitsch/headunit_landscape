package com.metrolist.music.variant

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
