package com.metrolist.music.variant

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.currentBackStackEntryAsState
import com.metrolist.music.LocalNavController
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.R
import com.metrolist.music.ui.component.BottomSheetState
import com.metrolist.music.ui.screens.library.LibraryPlaylistsScreen
import com.metrolist.music.ui.screens.library.LibraryScreen
import kotlin.math.max

private enum class VehicleRightPaneTab(
    val title: String,
    val icon: Int,
) {
    QUEUE("Warteschlange", R.drawable.queue_music),
    PLAYLISTS("Playlists", R.drawable.playlist_play),
    LIBRARY("Bibliothek", R.drawable.library_music_outlined),
}

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
    val safePlayerWeight = Dudu7Layout.sanitizePlayerPaneWeight(playerPaneWeight)
    val navController = LocalNavController.current
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route
    var selectedTab by rememberSaveable { mutableStateOf(VehicleRightPaneTab.QUEUE) }
    var routeWhenTabOpened by rememberSaveable { mutableStateOf<String?>(null) }

    LaunchedEffect(selectedTab) {
        routeWhenTabOpened = currentRoute
    }
    LaunchedEffect(currentRoute) {
        if (
            selectedTab != VehicleRightPaneTab.QUEUE &&
            routeWhenTabOpened != null &&
            currentRoute != routeWhenTabOpened &&
            state.isExpanded
        ) {
            state.collapseSoft()
        }
    }

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
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .clickable(onClick = onToggleLyrics),
            ) {
                thumbnailContent()
            }
            controlsContent()
            Spacer(Modifier.height(12.dp))
        }

        Surface(
            shape = RoundedCornerShape(18.dp),
            color = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.96f),
            modifier =
                Modifier
                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 8.dp, end = 8.dp),
        ) {
            Column(Modifier.fillMaxSize()) {
                TabRow(
                    selectedTabIndex = selectedTab.ordinal,
                    containerColor = MaterialTheme.colorScheme.surfaceContainer,
                ) {
                    VehicleRightPaneTab.entries.forEach { tab ->
                        Tab(
                            selected = selectedTab == tab,
                            onClick = { selectedTab = tab },
                            icon = {
                                Icon(
                                    painter = painterResource(tab.icon),
                                    contentDescription = null,
                                )
                            },
                            text = { Text(tab.title, maxLines = 1) },
                        )
                    }
                }

                Box(Modifier.weight(1f).fillMaxWidth()) {
                    CompositionLocalProvider(
                        LocalPlayerAwareWindowInsets provides WindowInsets(
                            left = 0.dp,
                            top = 0.dp,
                            right = 0.dp,
                            bottom = 0.dp,
                        ),
                    ) {
                        when (selectedTab) {
                            VehicleRightPaneTab.QUEUE -> queueContent()
                            VehicleRightPaneTab.PLAYLISTS ->
                                LibraryPlaylistsScreen(
                                    navController = navController,
                                    filterContent = {},
                                )
                            VehicleRightPaneTab.LIBRARY -> LibraryScreen()
                        }
                    }
                }
            }
        }
    }
}
