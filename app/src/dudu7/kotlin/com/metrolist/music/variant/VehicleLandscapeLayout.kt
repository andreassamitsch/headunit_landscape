package com.metrolist.music.variant

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.activity.compose.BackHandler
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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.metrolist.music.BuildConfig
import com.metrolist.music.LocalNavController
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.ui.component.BottomSheetState
import com.metrolist.music.ui.screens.Screens
import com.metrolist.music.ui.screens.navigationBuilder
import com.metrolist.music.ui.screens.radio.WebRadioScreen
import kotlin.math.max

private const val VEHICLE_QUEUE_ROUTE = "vehicle_queue"
private const val VEHICLE_WEBRADIO_ROUTE = "vehicle_webradio"

private enum class VehicleRightPaneTab(
    val title: String,
    val icon: Int,
    val route: String,
) {
    QUEUE("Warteschlange", R.drawable.queue_music, VEHICLE_QUEUE_ROUTE),
    LIBRARY("Bibliothek", R.drawable.library_music_outlined, Screens.Library.route),
    SEARCH("Suche", R.drawable.search, Screens.Search.route),
    HISTORY("Hörverlauf", R.drawable.history, "history"),
    WEBRADIO("WebRadio", R.drawable.radio, VEHICLE_WEBRADIO_ROUTE),
    HOME("Startseite", R.drawable.home_outlined, Screens.Home.route),
}

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }

@OptIn(ExperimentalMaterial3Api::class)
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

    val paneNavController = rememberNavController()
    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()
    val currentPaneRoute = paneBackStackEntry?.destination?.route
    var selectedTab by rememberSaveable { mutableStateOf(VehicleRightPaneTab.QUEUE) }
    val activity = LocalContext.current.findActivity()
    val snackbarHostState = remember { SnackbarHostState() }
    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()
    val playerConnection = LocalPlayerConnection.current

    LaunchedEffect(currentPaneRoute) {
        VehicleRightPaneTab.entries
            .firstOrNull { it.route == currentPaneRoute }
            ?.let { selectedTab = it }
    }

    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {
        paneNavController.popBackStack()
    }

    // User selections happen on the main UI thread. Use a direct callback so
    // the right pane returns immediately and no event can be dropped or consumed
    // by a stale collector during service/player recomposition.
    DisposableEffect(playerConnection, paneNavController) {
        val activeConnection = playerConnection
        val returnToQueue: () -> Unit = {
            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {
                selectedTab = VehicleRightPaneTab.QUEUE
                val popped = paneNavController.popBackStack(VEHICLE_QUEUE_ROUTE, inclusive = false)
                if (!popped) {
                    paneNavController.navigate(VEHICLE_QUEUE_ROUTE) {
                        launchSingleTop = true
                    }
                }
            }
        }
        activeConnection?.onUserSongSelection = returnToQueue
        onDispose {
            if (activeConnection?.onUserSongSelection === returnToQueue) {
                activeConnection.onUserSongSelection = null
            }
        }
    }

    Row(
        modifier =
            Modifier
                .windowInsetsPadding(
                    WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                ).padding(bottom = 8.dp)
                .fillMaxSize(),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier =
                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(horizontal = 12.dp, vertical = 4.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),
        ) {
            Box(
                contentAlignment = Alignment.Center,
                modifier =
                    Modifier
                        .weight(1f)
                        .fillMaxWidth()
                        .padding(top = 2.dp, bottom = 2.dp)
                        .clickable(onClick = onToggleLyrics),
            ) {
                thumbnailContent()
            }
            controlsContent()
            Spacer(Modifier.height(2.dp))
        }

        Surface(
            shape = RoundedCornerShape(16.dp),
            color = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.96f),
            modifier =
                Modifier
                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 6.dp, end = 8.dp),
        ) {
            Column(Modifier.fillMaxSize()) {
                ScrollableTabRow(
                    selectedTabIndex = selectedTab.ordinal,
                    edgePadding = 0.dp,
                    containerColor = MaterialTheme.colorScheme.surfaceContainer,
                    divider = {},
                ) {
                    VehicleRightPaneTab.entries.forEach { tab ->
                        Tab(
                            selected = selectedTab == tab,
                            onClick = {
                                if (selectedTab != tab || currentPaneRoute != tab.route) {
                                    selectedTab = tab
                                    paneNavController.navigate(tab.route) {
                                        popUpTo(VEHICLE_QUEUE_ROUTE) {
                                            saveState = true
                                        }
                                        launchSingleTop = true
                                        restoreState = true
                                    }
                                }
                            },
                            icon = {
                                Icon(
                                    painter = painterResource(tab.icon),
                                    contentDescription = tab.title,
                                )
                            },
                            text = { Text(tab.title, maxLines = 1) },
                            modifier = Modifier.height(64.dp),
                        )
                    }
                }

                CompositionLocalProvider(
                    LocalNavController provides paneNavController,
                    LocalPlayerAwareWindowInsets provides
                        WindowInsets(
                            left = 0.dp,
                            top = 0.dp,
                            right = 0.dp,
                            bottom = 0.dp,
                        ),
                ) {
                    Box(Modifier.weight(1f).fillMaxWidth()) {
                        if (activity != null) {
                            NavHost(
                                navController = paneNavController,
                                startDestination = VEHICLE_QUEUE_ROUTE,
                                modifier = Modifier.fillMaxSize(),
                            ) {
                                composable(VEHICLE_QUEUE_ROUTE) {
                                    queueContent()
                                }
                                composable(VEHICLE_WEBRADIO_ROUTE) {
                                    WebRadioScreen()
                                }
                                navigationBuilder(
                                    navController = paneNavController,
                                    scrollBehavior = scrollBehavior,
                                    latestVersionName = BuildConfig.VERSION_NAME,
                                    activity = activity,
                                    snackbarHostState = snackbarHostState,
                                    embeddedInPlayer = true,
                                )
                            }
                        } else {
                            queueContent()
                        }

                        SnackbarHost(
                            hostState = snackbarHostState,
                            modifier = Modifier.align(Alignment.BottomCenter),
                        )
                    }
                }
            }
        }
    }
}
