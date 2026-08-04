package com.metrolist.music.variant

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.positionInRoot
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.ArtistItem
import com.metrolist.music.BuildConfig
import com.metrolist.music.LocalNavController
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.LocalPlayerConnection
import com.metrolist.music.R
import com.metrolist.music.constants.Dudu7FrostedIceKey
import com.metrolist.music.constants.Dudu7FrostedGlassStrengthKey
import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey
import com.metrolist.music.constants.Dudu7FrostTextureEnabledKey
import com.metrolist.music.constants.Dudu7FrostTextureStrengthKey
import com.metrolist.music.extensions.move
import com.metrolist.music.playback.Dudu7PlaybackSource
import com.metrolist.music.playback.Dudu7SourcePlaybackCoordinator
import com.metrolist.music.radio.fyt.FmNowPlayingResolver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver
import com.metrolist.music.ui.component.BottomSheetState
import com.metrolist.music.ui.component.LocalRightPaneScrollBridge
import com.metrolist.music.ui.component.RightPaneScrollBridge
import com.metrolist.music.ui.screens.Screens
import com.metrolist.music.ui.screens.navigationBuilder
import com.metrolist.music.ui.screens.radio.PhysicalRadioScreen
import com.metrolist.music.ui.screens.radio.WebRadioScreen
import com.metrolist.music.utils.SearchRoutes
import com.metrolist.music.utils.rememberPreference
import kotlinx.coroutines.launch
import sh.calvin.reorderable.ReorderableItem
import sh.calvin.reorderable.rememberReorderableLazyListState
import timber.log.Timber
import java.text.Normalizer
import java.util.Locale
import kotlin.math.abs
import kotlin.math.max

private const val VEHICLE_QUEUE_ROUTE = "vehicle_queue"
private const val VEHICLE_WEBRADIO_ROUTE = "vehicle_webradio"
private const val VEHICLE_PHYSICAL_RADIO_ROUTE = "vehicle_physical_radio"
private const val VEHICLE_PANE_PREFS = "dudu7_vehicle_pane"
private const val VEHICLE_LAST_TAB_ROUTE = "last_main_tab_route"

private enum class VehicleRightPaneTab(
    val title: String,
    val icon: Int,
    val route: String,
) {
    QUEUE("Warteschlange", R.drawable.queue_music, VEHICLE_QUEUE_ROUTE),
    LIBRARY("Bibliothek", R.drawable.library_music_outlined, Screens.Library.route),
    WEBRADIO("WebRadio", R.drawable.radio, VEHICLE_WEBRADIO_ROUTE),
    PHYSICAL_RADIO("FM", R.drawable.radio, VEHICLE_PHYSICAL_RADIO_ROUTE),
    SEARCH("Suche", R.drawable.search, Screens.Search.route),
    HISTORY("Hörverlauf", R.drawable.history, "history"),
}

private fun normalizeArtistName(value: String): String =
    Normalizer
        .normalize(value, Normalizer.Form.NFD)
        .replace(Regex("\\p{Mn}+"), "")
        .lowercase(Locale.ROOT)
        .replace("&", " and ")
        .replace(Regex("[^a-z0-9]+"), " ")
        .trim()

private fun radioArtistMatchScore(requested: String, candidate: String): Int {
    val expected = normalizeArtistName(requested)
    val actual = normalizeArtistName(candidate)
    if (expected.isBlank() || actual.isBlank()) return 0
    if (expected == actual) return 100
    if (actual.startsWith(expected) || expected.startsWith(actual)) return 88
    if (actual.contains(expected) || expected.contains(actual)) return 82
    val expectedTokens = expected.split(' ').filter { it.length >= 2 }.toSet()
    val actualTokens = actual.split(' ').filter { it.length >= 2 }.toSet()
    if (expectedTokens.isEmpty() || actualTokens.isEmpty()) return 0
    val overlap = expectedTokens.intersect(actualTokens).size
    return ((overlap * 100.0) / max(expectedTokens.size, actualTokens.size)).toInt()
}

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }


@Composable
private fun FrostTextureOverlay(
    strength: Int,
    modifier: Modifier = Modifier,
) {
    val normalized = strength.coerceIn(0, 100) / 100f
    if (normalized <= 0f) return
    Image(
        painter = painterResource(R.drawable.dudu7_frost_texture),
        contentDescription = null,
        contentScale = ContentScale.Crop,
        modifier =
            modifier.graphicsLayer {
                alpha = normalized * 0.46f
                compositingStrategy = CompositingStrategy.Offscreen
            },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VehicleLandscapeLayout(
    state: BottomSheetState,
    showInlineLyrics: Boolean,
    playerPaneWeight: Float,
    onToggleLyrics: () -> Unit,
    tabContentColor: Color,
    tabGlassColor: Color,
    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,
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
    val safePlayerWeight = 0.5f

    val context = LocalContext.current
    val initialTab =
        remember(context) {
            val storedRoute =
                context.getSharedPreferences(VEHICLE_PANE_PREFS, Context.MODE_PRIVATE)
                    .getString(VEHICLE_LAST_TAB_ROUTE, null)
            VehicleRightPaneTab.entries.firstOrNull { it.route == storedRoute } ?: VehicleRightPaneTab.QUEUE
        }
    val paneNavController = rememberNavController()
    val paneBackStackEntry by paneNavController.currentBackStackEntryAsState()
    val currentPaneRoute = paneBackStackEntry?.destination?.route
    var selectedTab by rememberSaveable { mutableStateOf(initialTab) }
    val activity = context.findActivity()
    val haptic = LocalHapticFeedback.current
    val snackbarHostState = remember { SnackbarHostState() }
    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()
    val playerConnection = LocalPlayerConnection.current
    val physicalRadio = remember(context) { FytPhysicalRadio.get(context) }
    val physicalRadioState by physicalRadio.state.collectAsStateWithLifecycle()
    val fmNowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
    val fmLogoRevision by ReliableFmStationLogoResolver.revisions.collectAsStateWithLifecycle()
    val androidIsPlayingState =
        playerConnection?.isEffectivelyPlaying?.collectAsStateWithLifecycle()
            ?: remember { mutableStateOf(false) }
    val androidIsPlaying by androidIsPlayingState
    val rightPaneScope = rememberCoroutineScope()
    val rightPaneScrollBridge = remember { RightPaneScrollBridge() }
    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }

    LaunchedEffect(
        physicalRadioState.isActive,
        physicalRadioState.displayStation,
        physicalRadioState.frequency,
        physicalRadioState.pi,
        physicalRadioState.ecc,
        fmNowPlaying.key,
        fmNowPlaying.coverUrl,
        fmLogoRevision,
    ) {
        if (!physicalRadioState.isActive) {
            onPhysicalRadioVisualChanged(false, "", null)
            return@LaunchedEffect
        }

        val identity =
            "${physicalRadioState.displayStation}|${FytPhysicalRadio.formatFrequency(physicalRadioState.frequency)}|" +
                "${physicalRadioState.pi and 0xffff}|${physicalRadioState.ecc}"
        val recognizedCover =
            fmNowPlaying.coverUrl?.takeIf {
                it.isNotBlank() &&
                    fmNowPlaying.stationName.equals(physicalRadioState.displayStation, ignoreCase = true)
            }
        val cachedStationLogo =
            ReliableFmStationLogoResolver.cachedLogo(
                context = context,
                stationName = physicalRadioState.displayStation,
                frequency = physicalRadioState.frequency,
                pi = physicalRadioState.pi,
                ecc = physicalRadioState.ecc,
                allFrequencies =
                    listOf(physicalRadioState.frequency) + physicalRadioState.alternativeFrequencies,
            )
        onPhysicalRadioVisualChanged(true, identity, recognizedCover ?: cachedStationLogo)
        if (recognizedCover != null) return@LaunchedEffect

        val resolvedStationLogo =
            ReliableFmStationLogoResolver.resolve(
                context = context,
                stationName = physicalRadioState.displayStation,
                frequency = physicalRadioState.frequency,
                pi = physicalRadioState.pi,
                ecc = physicalRadioState.ecc,
                allFrequencies =
                    listOf(physicalRadioState.frequency) + physicalRadioState.alternativeFrequencies,
            )
        val latestState = physicalRadio.state.value
        val latestIdentity =
            "${latestState.displayStation}|${FytPhysicalRadio.formatFrequency(latestState.frequency)}|" +
                "${latestState.pi and 0xffff}|${latestState.ecc}"
        if (latestState.isActive && latestIdentity == identity) {
            onPhysicalRadioVisualChanged(true, identity, resolvedStationLogo)
        }
    }

    val orderedTabs =
        remember(context) {
            mutableStateListOf<VehicleRightPaneTab>().apply {
                val byName = VehicleRightPaneTab.entries.associateBy { it.name }
                addAll(
                    VehicleTabOrderStore
                        .read(context, byName.keys)
                        .mapNotNull(byName::get),
                )
            }
        }
    val tabListState = rememberLazyListState()
    val tabReorderState =
        rememberReorderableLazyListState(tabListState) { from, to ->
            if (from.index in orderedTabs.indices && to.index in orderedTabs.indices) {
                orderedTabs.move(from.index, to.index)
            }
        }
    val isTabDragging = tabReorderState.isAnyItemDragging
    var wasTabDragging by remember { mutableStateOf(false) }

    LaunchedEffect(isTabDragging) {
        if (wasTabDragging && !isTabDragging) {
            VehicleTabOrderStore.persist(context, orderedTabs.map { it.name })
        }
        wasTabDragging = isTabDragging
    }

    LaunchedEffect(selectedTab, orderedTabs.toList()) {
        context.getSharedPreferences(VEHICLE_PANE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(VEHICLE_LAST_TAB_ROUTE, selectedTab.route)
            .apply()
        val index = orderedTabs.indexOf(selectedTab)
        if (index >= 0) {
            tabListState.animateScrollToItem(index)
        }
    }

    LaunchedEffect(currentPaneRoute) {
        VehicleRightPaneTab.entries
            .firstOrNull { it.route == currentPaneRoute }
            ?.let { selectedTab = it }
    }

    LaunchedEffect(selectedTab, playerConnection) {
        val activeConnection = playerConnection ?: return@LaunchedEffect
        val targetSource =
            when (selectedTab) {
                VehicleRightPaneTab.QUEUE -> Dudu7PlaybackSource.YT_MUSIC
                VehicleRightPaneTab.WEBRADIO -> Dudu7PlaybackSource.WEBRADIO
                VehicleRightPaneTab.PHYSICAL_RADIO -> Dudu7PlaybackSource.FM
                else -> null
            }
        if (targetSource != null) {
            Dudu7SourcePlaybackCoordinator.activate(
                context = context,
                target = targetSource,
                playerConnection = activeConnection,
                physicalRadio = physicalRadio,
            )
        }
    }

    LaunchedEffect(androidIsPlaying, physicalRadioState.isActive) {
        if (
            androidIsPlaying &&
            physicalRadioState.isActive &&
            Dudu7SourcePlaybackCoordinator.activeSource != Dudu7PlaybackSource.FM
        ) {
            physicalRadio.powerOff()
        }
    }

    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {
        paneNavController.popBackStack()
    }

    DisposableEffect(playerConnection, paneNavController) {
        val activeConnection = playerConnection
        val returnToQueue: () -> Unit = {
            if (activeConnection != null) {
                Dudu7SourcePlaybackCoordinator.prepareForUserSongSelection(
                    context = context,
                    playerConnection = activeConnection,
                    physicalRadio = physicalRadio,
                )
            } else if (physicalRadio.state.value.isActive) {
                physicalRadio.powerOff()
            }
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
        val openRouteInRightPane: (String) -> Unit = { route ->
            selectedTab = VehicleRightPaneTab.SEARCH
            if (
                route.startsWith("search/") &&
                paneNavController.currentDestination?.route == SearchRoutes.ROUTE
            ) {
                paneNavController.popBackStack()
            }
            paneNavController.navigate(route)
        }
        val openRadioArtistInRightPane: (String) -> Unit = { artistName ->
            rightPaneScope.launch {
                selectedTab = VehicleRightPaneTab.SEARCH
                val artists =
                    YouTube
                        .search(artistName, YouTube.SearchFilter.FILTER_ARTIST)
                        .getOrNull()
                        ?.items
                        ?.filterIsInstance<ArtistItem>()
                        .orEmpty()
                val bestMatch =
                    artists
                        .map { it to radioArtistMatchScore(artistName, it.title) }
                        .filter { (artist, score) -> !artist.id.isNullOrBlank() && score >= 70 }
                        .maxByOrNull { (_, score) -> score }
                        ?.first
                val route =
                    bestMatch?.id?.let { "artist/$it" }
                        ?: SearchRoutes.resultRoute(artistName)
                Timber.tag("Dudu7RadioArtist").d(
                    "Resolved radio artist navigation: %s -> %s (%s)",
                    artistName,
                    bestMatch?.title ?: "search results",
                    bestMatch?.id ?: "no exact artist",
                )
                paneNavController.navigate(route) {
                    launchSingleTop = true
                }
            }
        }
        activeConnection?.onUserSongSelection = returnToQueue
        activeConnection?.onRadioArtistSelection = openRadioArtistInRightPane
        activeConnection?.onRightPaneNavigation = openRouteInRightPane
        onDispose {
            if (activeConnection?.onUserSongSelection === returnToQueue) {
                activeConnection.onUserSongSelection = null
            }
            if (activeConnection?.onRadioArtistSelection === openRadioArtistInRightPane) {
                activeConnection.onRadioArtistSelection = null
            }
            if (activeConnection?.onRightPaneNavigation === openRouteInRightPane) {
                activeConnection.onRightPaneNavigation = null
            }
        }
    }

    val (frostedIceEnabled) = rememberPreference(
        Dudu7FrostedIceKey,
        defaultValue = false,
    )
    val (frostedGlassStrength) = rememberPreference(
        Dudu7FrostedGlassStrengthKey,
        defaultValue = 55,
    )
    val (frostedBlurStrength) = rememberPreference(
        Dudu7FrostedBlurStrengthKey,
        defaultValue = 12,
    )
    val (frostTextureEnabled) = rememberPreference(
        Dudu7FrostTextureEnabledKey,
        defaultValue = false,
    )
    val (frostTextureStrength) = rememberPreference(
        Dudu7FrostTextureStrengthKey,
        defaultValue = 35,
    )
    val glassAlpha = frostedGlassStrength.coerceIn(0, 100) / 100f
    val glassBlur = frostedBlurStrength.coerceIn(0, 24).dp
    val baseColors = MaterialTheme.colorScheme
    val adaptiveContentColor = tabContentColor
    val adaptiveSecondaryContentColor = adaptiveContentColor.copy(alpha = 0.76f)
    val adaptiveDisabledContentColor = adaptiveContentColor.copy(alpha = 0.46f)
    val inverseAdaptiveContentColor =
        if (adaptiveContentColor.luminance() > 0.5f) Color.Black else Color.White
    val frostedColors =
        if (frostedIceEnabled) {
            baseColors.copy(
                background = baseColors.background.copy(alpha = glassAlpha),
                surface = baseColors.surface.copy(alpha = glassAlpha),
                surfaceDim = baseColors.surfaceDim.copy(alpha = glassAlpha),
                surfaceBright = baseColors.surfaceBright.copy(alpha = glassAlpha),
                surfaceVariant = baseColors.surfaceVariant.copy(alpha = glassAlpha),
                surfaceContainerLowest = baseColors.surfaceContainerLowest.copy(alpha = glassAlpha),
                surfaceContainerLow = baseColors.surfaceContainerLow.copy(alpha = glassAlpha),
                surfaceContainer = baseColors.surfaceContainer.copy(alpha = glassAlpha),
                surfaceContainerHigh = baseColors.surfaceContainerHigh.copy(alpha = glassAlpha),
                surfaceContainerHighest = baseColors.surfaceContainerHighest.copy(alpha = glassAlpha),
                primary = adaptiveContentColor,
                onPrimary = inverseAdaptiveContentColor,
                secondary = adaptiveContentColor.copy(alpha = 0.88f),
                onSecondary = inverseAdaptiveContentColor,
                tertiary = adaptiveContentColor.copy(alpha = 0.88f),
                onTertiary = inverseAdaptiveContentColor,
                primaryContainer = baseColors.primaryContainer.copy(alpha = glassAlpha),
                secondaryContainer = baseColors.secondaryContainer.copy(alpha = glassAlpha),
                tertiaryContainer = baseColors.tertiaryContainer.copy(alpha = glassAlpha),
                errorContainer = baseColors.errorContainer.copy(alpha = glassAlpha),
                onBackground = adaptiveContentColor,
                onSurface = adaptiveContentColor,
                onSurfaceVariant = adaptiveSecondaryContentColor,
                onPrimaryContainer = adaptiveContentColor,
                onSecondaryContainer = adaptiveContentColor,
                onTertiaryContainer = adaptiveContentColor,
                onErrorContainer = adaptiveContentColor,
                outline = adaptiveContentColor.copy(alpha = 0.62f),
                outlineVariant = adaptiveDisabledContentColor,
                surfaceTint = Color.Transparent,
            )
        } else {
            baseColors
        }
    val glassShape = RoundedCornerShape(24.dp)

    Box(
        modifier = Modifier.fillMaxSize().clipToBounds(),
    ) {
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
            if (physicalRadioState.isActive) {
                PhysicalRadioPlayerPane(
                    radio = physicalRadio,
                    playerConnection = playerConnection,
                )
            } else {
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
        }

            Surface(
                shape = if (frostedIceEnabled) glassShape else RoundedCornerShape(12.dp),
                color = if (frostedIceEnabled) frostedColors.surfaceContainer else baseColors.surfaceContainer,
                border = null,
                tonalElevation = if (frostedIceEnabled) 0.dp else 2.dp,
                shadowElevation = 0.dp,
                modifier =
                    Modifier
                        .weight(1f - safePlayerWeight)
                        .fillMaxSize()
                        .padding(horizontal = 8.dp, vertical = 4.dp),
            ) {
                Box(Modifier.fillMaxSize()) {
                    if (frostedIceEnabled && frostedBlurStrength > 0 && glassAlpha > 0f) {
                        Box(
                            Modifier
                                .fillMaxSize()
                                .clip(glassShape)
                                .background(baseColors.surface.copy(alpha = glassAlpha * 0.45f))
                                .blur(glassBlur),
                        )
                    }
                    if (frostedIceEnabled && frostTextureEnabled && frostTextureStrength > 0) {
                        FrostTextureOverlay(
                            strength = frostTextureStrength,
                            modifier = Modifier.fillMaxSize().clip(glassShape),
                        )
                    }
                    MaterialTheme(colorScheme = frostedColors) {
            Column(Modifier.fillMaxSize()) {
                val effectiveTabContentColor =
                    if (frostedIceEnabled) tabContentColor else baseColors.onSurface
                val effectiveTabGlassColor =
                    if (frostedIceEnabled) tabGlassColor else baseColors.surfaceContainerHigh
                Box(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(64.dp)
                            .background(effectiveTabGlassColor),
                ) {
                    LazyRow(
                        state = tabListState,
                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        itemsIndexed(
                            items = orderedTabs,
                            key = { _, tab -> tab.name },
                        ) { _, tab ->
                            ReorderableItem(tabReorderState, key = tab.name) { isDragging ->
                                val isSelected = selectedTab == tab
                                val itemColor =
                                    if (isSelected) {
                                        effectiveTabContentColor
                                    } else {
                                        effectiveTabContentColor.copy(alpha = 0.76f)
                                    }
                                Box(
                                    modifier =
                                        Modifier
                                            .height(64.dp)
                                            .longPressDraggableHandle(
                                                onDragStarted = {
                                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                },
                                            ),
                                ) {
                                    Tab(
                                        selected = isSelected,
                                        selectedContentColor = itemColor,
                                        unselectedContentColor = itemColor,
                                        onClick = {
                                            if (!isDragging && (selectedTab != tab || currentPaneRoute != tab.route)) {
                                                selectedTab = tab
                                                val restoredExistingTab =
                                                    paneNavController.popBackStack(tab.route, inclusive = false)
                                                if (!restoredExistingTab) {
                                                    paneNavController.navigate(tab.route) {
                                                        launchSingleTop = true
                                                        restoreState = false
                                                    }
                                                }
                                            }
                                        },
                                        icon = {
                                            Icon(
                                                painter = painterResource(tab.icon),
                                                contentDescription = tab.title,
                                                tint = itemColor,
                                            )
                                        },
                                        text = {
                                            Text(
                                                text = tab.title,
                                                maxLines = 1,
                                                color = itemColor,
                                            )
                                        },
                                        modifier = Modifier.fillMaxSize(),
                                    )
                                    if (isSelected) {
                                        Box(
                                            modifier =
                                                Modifier
                                                    .align(Alignment.BottomCenter)
                                                    .padding(bottom = 4.dp)
                                                    .width(30.dp)
                                                    .height(3.dp)
                                                    .clip(RoundedCornerShape(50))
                                                    .background(effectiveTabContentColor.copy(alpha = 0.88f)),
                                        )
                                    }
                                }
                            }
                        }
                    }
                    Box(
                        modifier =
                            Modifier
                                .align(Alignment.BottomCenter)
                                .fillMaxWidth()
                                .height(1.dp)
                                .background(effectiveTabContentColor.copy(alpha = 0.10f)),
                    )
                }

                CompositionLocalProvider(
                    LocalNavController provides paneNavController,
                    LocalRightPaneScrollBridge provides rightPaneScrollBridge,
                    LocalPlayerAwareWindowInsets provides
                        WindowInsets(
                            left = 0.dp,
                            top = 0.dp,
                            right = 0.dp,
                            bottom = 0.dp,
                        ),
                ) {
                    Box(
                        modifier =
                            Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .onGloballyPositioned { coordinates ->
                                    rightPaneOriginInRoot = coordinates.positionInRoot()
                                }
                                .pointerInput(
                                    currentPaneRoute,
                                    rightPaneScrollBridge.handler,
                                    rightPaneScrollBridge.tapHandler,
                                ) {
                                    val scrollHandler = rightPaneScrollBridge.handler
                                    awaitPointerEventScope {
                                        var downPosition: Offset? = null
                                        var lastPosition: Offset? = null
                                        var accumulatedX = 0f
                                        var accumulatedY = 0f
                                        var verticalDrag = false
                                        while (true) {
                                            val event = awaitPointerEvent(PointerEventPass.Final)
                                            val change = event.changes.firstOrNull() ?: continue
                                            if (change.pressed && !change.previousPressed) {
                                                downPosition = change.position
                                                lastPosition = change.position
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                                continue
                                            }
                                            if (change.pressed) {
                                                val previous = lastPosition ?: change.position
                                                val delta = change.position - previous
                                                lastPosition = change.position
                                                accumulatedX += delta.x
                                                accumulatedY += delta.y
                                                if (
                                                    !verticalDrag &&
                                                    abs(accumulatedY) > viewConfiguration.touchSlop &&
                                                    abs(accumulatedY) > abs(accumulatedX)
                                                ) {
                                                    verticalDrag = true
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag started route=%s",
                                                        currentPaneRoute,
                                                    )
                                                }
                                                if (verticalDrag && scrollHandler != null && !change.isConsumed) {
                                                    change.consume()
                                                    scrollHandler(-delta.y)
                                                }
                                                continue
                                            }
                                            if (change.previousPressed) {
                                                if (!verticalDrag && change.isConsumed) {
                                                    Timber.tag("Dudu7RightPaneTap").d(
                                                        "Right-pane child handled tap route=%s",
                                                        currentPaneRoute,
                                                    )
                                                } else if (verticalDrag) {
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag ended route=%s",
                                                        currentPaneRoute,
                                                    )
                                                } else {
                                                    val start = downPosition
                                                    val moved =
                                                        start == null ||
                                                            (change.position - start).getDistance() > viewConfiguration.touchSlop
                                                    if (!moved) {
                                                        val positionInRoot = rightPaneOriginInRoot + change.position
                                                        val handled = rightPaneScrollBridge.dispatchTap(positionInRoot)
                                                        Timber.tag("Dudu7RightPaneTap").i(
                                                            "Right-pane tap route=%s x=%.1f y=%.1f handled=%s",
                                                            currentPaneRoute,
                                                            positionInRoot.x,
                                                            positionInRoot.y,
                                                            handled,
                                                        )
                                                        if (handled) change.consume()
                                                    }
                                                }
                                                downPosition = null
                                                lastPosition = null
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                            }
                                        }
                                    }
                                },
                    ) {
                        if (activity != null) {
                            NavHost(
                                navController = paneNavController,
                                startDestination = initialTab.route,
                                modifier = Modifier.fillMaxSize(),
                            ) {
                                composable(VEHICLE_QUEUE_ROUTE) {
                                    queueContent()
                                }
                                composable(VEHICLE_PHYSICAL_RADIO_ROUTE) {
                                    PhysicalRadioScreen()
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
        }
    }
}
