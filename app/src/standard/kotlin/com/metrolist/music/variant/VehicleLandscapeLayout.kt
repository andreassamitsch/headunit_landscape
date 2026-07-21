package com.metrolist.music.variant

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.add
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import com.metrolist.music.ui.component.BottomSheetState
import kotlin.math.max

@Suppress("UNUSED_PARAMETER")
@Composable
fun VehicleLandscapeLayout(
    state: BottomSheetState,
    showInlineLyrics: Boolean,
    playerPaneWeight: Float,
    onToggleLyrics: () -> Unit,
    thumbnailContent: @Composable () -> Unit,
    controlsContent: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
    queueContent: @Composable () -> Unit,
) {
    val density = LocalDensity.current
    val verticalPadding =
        max(
            WindowInsets.systemBars.getTop(density),
            WindowInsets.systemBars.getBottom(density),
        )
    val verticalPaddingDp = with(density) { verticalPadding.toDp() }
    val verticalWindowInsets =
        WindowInsets(left = 0.dp, top = verticalPaddingDp, right = 0.dp, bottom = verticalPaddingDp)

    Row(
        modifier =
            Modifier
                .windowInsetsPadding(
                    WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                ).padding(bottom = 24.dp)
                .fillMaxSize(),
    ) {
        Box(
            contentAlignment = Alignment.Center,
            modifier =
                Modifier
                    .weight(1f)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),
        ) {
            thumbnailContent()
        }

        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier =
                Modifier
                    .weight(if (showInlineLyrics) 0.65f else 1f, false)
                    .animateContentSize()
                    .windowInsetsPadding(WindowInsets.systemBars.only(WindowInsetsSides.Top)),
        ) {
            Spacer(Modifier.weight(1f))
            controlsContent()
            Spacer(Modifier.weight(1f))
        }
    }
}
