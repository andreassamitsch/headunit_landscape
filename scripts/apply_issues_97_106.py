from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
LAYOUT = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
BUILD = ROOT / "app/build.gradle.kts"


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one occurrence, found {count}: {old[:120]!r}")
    return text.replace(old, new, 1)


def replace_range(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Start marker missing: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"End marker missing: {end_marker!r}")
    return text[:start] + replacement + text[end:]


player = PLAYER.read_text(encoding="utf-8")
player = replace_once(
    player,
    "\n\n@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun BottomSheetPlayer(",
    """

private data class Dudu7FmVisualSnapshot(
    val active: Boolean = false,
    val identity: String = "",
    val artworkUrl: String? = null,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BottomSheetPlayer(""",
)
player = replace_once(
    player,
    """    val playbackState by playerConnection.playbackState.collectAsState()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsState()
    val radioStationStore = remember(context) { RadioStationStore.get(context) }
""",
    """    val playbackState by playerConnection.playbackState.collectAsState()
    val mediaMetadata by playerConnection.mediaMetadata.collectAsState()
    var dudu7FmVisual by remember { mutableStateOf(Dudu7FmVisualSnapshot()) }
    val effectiveVisualId =
        if (VehicleVariantConfig.isDudu7 && dudu7FmVisual.active) {
            "fm:${dudu7FmVisual.identity}"
        } else {
            mediaMetadata?.id
        }
    val effectiveArtworkUrl =
        if (VehicleVariantConfig.isDudu7 && dudu7FmVisual.active) {
            dudu7FmVisual.artworkUrl
        } else {
            mediaMetadata?.thumbnailUrl
        }
    val radioStationStore = remember(context) { RadioStationStore.get(context) }
""",
)
player = replace_range(
    player,
    "    LaunchedEffect(mediaMetadata?.id, mediaMetadata?.thumbnailUrl, playerBackground) {",
    "    val (textButtonColor, iconButtonColor) =",
    """    val visualArtworkKey = "${effectiveVisualId.orEmpty()}|${effectiveArtworkUrl.orEmpty()}"
    val latestVisualArtworkKey by rememberUpdatedState(visualArtworkKey)

    LaunchedEffect(visualArtworkKey, playerBackground) {
        val needsArtworkPalette =
            playerBackground == PlayerBackgroundStyle.GRADIENT ||
                (VehicleVariantConfig.isDudu7 && playerBackground == PlayerBackgroundStyle.BLUR)
        val artworkUrl = effectiveArtworkUrl?.takeIf { it.isNotBlank() }
        if (!needsArtworkPalette || artworkUrl == null) {
            gradientColors = emptyList()
            return@LaunchedEffect
        }

        val artworkCacheKey = visualArtworkKey
        val cachedColors = gradientColorsCache[artworkCacheKey]
        if (cachedColors != null) {
            gradientColors = cachedColors
            return@LaunchedEffect
        }
        withContext(Dispatchers.IO) {
            val request =
                ImageRequest
                    .Builder(context)
                    .data(artworkUrl)
                    .size(100, 100)
                    .allowHardware(false)
                    .memoryCacheKey("gradient_${artworkCacheKey.hashCode()}")
                    .build()

            val result = runCatching { context.imageLoader.execute(request) }.getOrNull()
            val bitmap = result?.image?.toBitmap()
            if (bitmap != null) {
                val palette =
                    withContext(Dispatchers.Default) {
                        Palette
                            .from(bitmap)
                            .maximumColorCount(8)
                            .resizeBitmapArea(100 * 100)
                            .generate()
                    }
                val extractedColors =
                    PlayerColorExtractor.extractGradientColors(
                        palette = palette,
                        fallbackColor = fallbackColor,
                    )
                gradientColorsCache[artworkCacheKey] = extractedColors
                withContext(Dispatchers.Main) {
                    if (latestVisualArtworkKey == artworkCacheKey) {
                        gradientColors = extractedColors
                    }
                }
            } else {
                withContext(Dispatchers.Main) {
                    if (latestVisualArtworkKey == artworkCacheKey) {
                        gradientColors = emptyList()
                    }
                }
            }
        }
    }

    val visualBackdropColor =
        when {
            playerBackground == PlayerBackgroundStyle.DEFAULT -> MaterialTheme.colorScheme.surfaceContainer
            gradientColors.isNotEmpty() -> gradientColors.first()
            else -> MaterialTheme.colorScheme.surface
        }
    val visualBackdropLuminance =
        when (playerBackground) {
            PlayerBackgroundStyle.BLUR -> visualBackdropColor.luminance() * 0.70f
            PlayerBackgroundStyle.GRADIENT -> visualBackdropColor.luminance() * 0.80f
            PlayerBackgroundStyle.DEFAULT -> visualBackdropColor.luminance()
        }
    val adaptiveVisualContentColor =
        if (visualBackdropLuminance >= 0.52f) {
            Color.Black.copy(alpha = 0.90f)
        } else {
            Color.White.copy(alpha = 0.96f)
        }
    val inverseAdaptiveVisualContentColor =
        if (adaptiveVisualContentColor.luminance() > 0.5f) Color.Black else Color.White

    val TextBackgroundColor by animateColorAsState(
        targetValue =
            when (playerBackground) {
                PlayerBackgroundStyle.DEFAULT -> MaterialTheme.colorScheme.onBackground
                PlayerBackgroundStyle.BLUR, PlayerBackgroundStyle.GRADIENT -> adaptiveVisualContentColor
            },
        label = "TextBackgroundColor",
    )

    val icBackgroundColor by animateColorAsState(
        targetValue =
            when (playerBackground) {
                PlayerBackgroundStyle.DEFAULT -> MaterialTheme.colorScheme.surface
                PlayerBackgroundStyle.BLUR, PlayerBackgroundStyle.GRADIENT -> inverseAdaptiveVisualContentColor
            },
        label = "icBackgroundColor",
    )

""",
)
player = replace_once(
    player,
    """                    PlayerButtonsStyle.DEFAULT -> {
                        Pair(Color.White, Color.Black)
                    }
""",
    """                    PlayerButtonsStyle.DEFAULT -> {
                        Pair(adaptiveVisualContentColor, inverseAdaptiveVisualContentColor)
                    }
""",
)
player = replace_once(
    player,
    """                    PlayerButtonsStyle.DEFAULT -> {
                        Pair(
                            Color.White.copy(alpha = 0.2f),
                            Color.White,
                        )
                    }
""",
    """                    PlayerButtonsStyle.DEFAULT -> {
                        Pair(
                            adaptiveVisualContentColor.copy(alpha = 0.20f),
                            adaptiveVisualContentColor,
                        )
                    }
""",
)
player = replace_once(player, "targetState = mediaMetadata?.thumbnailUrl,", "targetState = effectiveArtworkUrl,")
player = replace_once(
    player,
    """                val tabBackdropColor =
                    when {
                        playerBackground == PlayerBackgroundStyle.GRADIENT && gradientColors.isNotEmpty() ->
                            gradientColors.first()
                        playerBackground == PlayerBackgroundStyle.DEFAULT ->
                            MaterialTheme.colorScheme.surfaceContainer
                        else ->
                            MaterialTheme.colorScheme.surface
                    }
                val tabBackdropIsLight = tabBackdropColor.luminance() >= 0.52f
                val tabContentColor =
                    if (tabBackdropIsLight) {
                        Color.Black.copy(alpha = 0.88f)
                    } else {
                        Color.White.copy(alpha = 0.94f)
                    }
                val tabGlassColor =
                    Color.White.copy(
                        alpha = if (tabBackdropIsLight) 0.24f else 0.13f,
                    )
                VehicleLandscapeLayout(
                    state = state,
                    showInlineLyrics = showInlineLyrics,
                    playerPaneWeight = dudu7PlayerPaneWeight,
                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },
                    tabContentColor = tabContentColor,
                    tabGlassColor = tabGlassColor,
""",
    """                val tabContentColor =
                    if (playerBackground == PlayerBackgroundStyle.DEFAULT) {
                        MaterialTheme.colorScheme.onSurface
                    } else {
                        adaptiveVisualContentColor
                    }
                val tabGlassColor =
                    tabContentColor.copy(
                        alpha = if (tabContentColor.luminance() > 0.5f) 0.13f else 0.18f,
                    )
                VehicleLandscapeLayout(
                    state = state,
                    showInlineLyrics = showInlineLyrics,
                    playerPaneWeight = dudu7PlayerPaneWeight,
                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },
                    tabContentColor = tabContentColor,
                    tabGlassColor = tabGlassColor,
                    onPhysicalRadioVisualChanged = { active, identity, artworkUrl ->
                        val next = Dudu7FmVisualSnapshot(active, identity, artworkUrl)
                        if (dudu7FmVisual != next) dudu7FmVisual = next
                    },
""",
)
PLAYER.write_text(player, encoding="utf-8")

layout = LAYOUT.read_text(encoding="utf-8")
layout = replace_once(
    layout,
    "import androidx.compose.ui.graphics.graphicsLayer\n",
    "import androidx.compose.ui.graphics.graphicsLayer\nimport androidx.compose.ui.graphics.luminance\n",
)
layout = replace_once(
    layout,
    "import com.metrolist.music.radio.fyt.FytPhysicalRadio\n",
    """import com.metrolist.music.radio.fyt.FmNowPlayingResolver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver
""",
)
layout = replace_once(
    layout,
    """    tabContentColor: Color,
    tabGlassColor: Color,
    thumbnailContent: @Composable () -> Unit,
""",
    """    tabContentColor: Color,
    tabGlassColor: Color,
    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,
    thumbnailContent: @Composable () -> Unit,
""",
)
layout = replace_once(
    layout,
    """    val physicalRadio = remember(context) { FytPhysicalRadio.get(context) }
    val physicalRadioState by physicalRadio.state.collectAsStateWithLifecycle()
    val androidIsPlayingState =
""",
    """    val physicalRadio = remember(context) { FytPhysicalRadio.get(context) }
    val physicalRadioState by physicalRadio.state.collectAsStateWithLifecycle()
    val fmNowPlaying by FmNowPlayingResolver.state.collectAsStateWithLifecycle()
    val fmLogoRevision by ReliableFmStationLogoResolver.revisions.collectAsStateWithLifecycle()
    val androidIsPlayingState =
""",
)
layout = replace_once(
    layout,
    """    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }

    val orderedTabs =
""",
    """    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }

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
""",
)
layout = replace_range(
    layout,
    "    val glassAlpha = frostedGlassStrength.coerceIn(0, 100) / 100f",
    "    val glassShape = RoundedCornerShape(24.dp)",
    """    val glassAlpha = frostedGlassStrength.coerceIn(0, 100) / 100f
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
""",
)
LAYOUT.write_text(layout, encoding="utf-8")

build = BUILD.read_text(encoding="utf-8")
build = replace_once(build, "versionCode = 1370064", "versionCode = 1370065")
build = replace_once(build, 'versionName = "13.7.55"', 'versionName = "13.7.56"')
BUILD.write_text(build, encoding="utf-8")

print("Issues #97 and #106 visual-state patch applied")
