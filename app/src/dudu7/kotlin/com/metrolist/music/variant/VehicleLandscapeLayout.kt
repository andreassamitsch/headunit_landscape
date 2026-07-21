package com.metrolist.music.variant

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.add
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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

@Composable
fun VehicleLandscapeLayout(
    state: BottomSheetState,
    showInlineLyrics: Boolean,
    playerPaneWeight: Float,
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
    val safePlayerWeight = Dudu7Layout.sanitizePlayerPaneWeight(playerPaneWeight)

    Row(
        modifier =
            Modifier
                .windowInsetsPadding(
                    WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                ).padding(bottom = 12.dp)
                .fillMaxSize(),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier =
                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(horizontal = 20.dp, vertical = 8.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),
        ) {
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier.weight(1f).fillMaxWidth(),
            ) {
                thumbnailContent()
            }
            controlsContent()
            Spacer(Modifier.height(12.dp))
        }

        Box(
            modifier =
                Modifier
                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 8.dp),
        ) {
            queueContent()
        }
    }
}
