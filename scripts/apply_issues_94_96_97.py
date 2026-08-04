#!/usr/bin/env python3
from pathlib import Path


def load(path: str) -> str:
    return Path(path).read_text()


def save(path: str, text: str) -> None:
    Path(path).write_text(text)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing marker: {label}")
    return text.replace(old, new, 1)


def extract_block(text: str, start: int) -> str:
    brace = text.index("{", start)
    depth = 0
    in_string = False
    escaped = False
    for pos in range(brace, len(text)):
        char = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]
    raise RuntimeError("unclosed Kotlin block")


# Release version.
path = "app/build.gradle.kts"
text = load(path)
text = replace_once(text, "versionCode = 1370060", "versionCode = 1370061", "versionCode")
text = replace_once(text, 'versionName = "13.7.51"', 'versionName = "13.7.52"', "versionName")
save(path, text)

# Preferences.
path = "app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt"
text = load(path)
marker = 'val Dudu7FrostedBlurStrengthKey = intPreferencesKey("dudu7FrostedBlurStrength")\n'
if "Dudu7FrostTextureEnabledKey" not in text:
    text = replace_once(
        text,
        marker,
        marker
        + 'val Dudu7FrostTextureEnabledKey = booleanPreferencesKey("dudu7FrostTextureEnabled")\n'
        + 'val Dudu7FrostTextureStrengthKey = intPreferencesKey("dudu7FrostTextureStrength")\n',
        "frost preferences",
    )
save(path, text)

# Appearance settings.
path = "app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt"
text = load(path)
if "Dudu7FrostTextureEnabledKey" not in text:
    text = replace_once(
        text,
        "import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n",
        "import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n"
        "import com.metrolist.music.constants.Dudu7FrostTextureEnabledKey\n"
        "import com.metrolist.music.constants.Dudu7FrostTextureStrengthKey\n",
        "appearance imports",
    )
    pref = """    val (dudu7FrostedBlurStrength, onDudu7FrostedBlurStrengthChange) =
        rememberPreference(
            Dudu7FrostedBlurStrengthKey,
            defaultValue = 12,
        )
"""
    text = replace_once(
        text,
        pref,
        pref
        + """    val (dudu7FrostTextureEnabled, onDudu7FrostTextureEnabledChange) =
        rememberPreference(
            Dudu7FrostTextureEnabledKey,
            defaultValue = false,
        )
    val (dudu7FrostTextureStrength, onDudu7FrostTextureStrengthChange) =
        rememberPreference(
            Dudu7FrostTextureStrengthKey,
            defaultValue = 35,
        )
""",
        "appearance preference state",
    )
text = text.replace(
    'description = { Text("Cover-Hintergrund und transparente Oberfläche; standardmäßig aus") }',
    'description = { Text("Transparente Dudu7-Oberflächen; standardmäßig aus") }',
    1,
)
text = replace_once(
    text,
    "valueRange = 15f..90f,\n                                        steps = 14,",
    "valueRange = 0f..100f,\n                                        steps = 19,",
    "glass range",
)
blur_item = """                        add(
                            Material3SettingsItem(
                                icon = painterResource(R.drawable.palette),
                                title = { Text("Glas-Unschärfe") },
                                description = { Text("${dudu7FrostedBlurStrength} dp") },
                                trailingContent = {
                                    Slider(
                                        value = dudu7FrostedBlurStrength.toFloat(),
                                        onValueChange = { onDudu7FrostedBlurStrengthChange(it.roundToInt()) },
                                        valueRange = 0f..24f,
                                        steps = 11,
                                        modifier = Modifier.fillMaxWidth(0.42f),
                                    )
                                },
                                onClick = {},
                            ),
                        )
"""
if "Froststruktur anzeigen" not in text:
    frost_items = blur_item + """                        add(
                            Material3SettingsItem(
                                icon = painterResource(R.drawable.palette),
                                title = { Text("Froststruktur anzeigen") },
                                description = { Text("Feine Eisstruktur über den Glasflächen") },
                                trailingContent = {
                                    Switch(
                                        checked = dudu7FrostTextureEnabled,
                                        onCheckedChange = onDudu7FrostTextureEnabledChange,
                                        thumbContent = {
                                            Icon(
                                                painter = painterResource(
                                                    id = if (dudu7FrostTextureEnabled) R.drawable.check else R.drawable.close,
                                                ),
                                                contentDescription = null,
                                                modifier = Modifier.size(SwitchDefaults.IconSize),
                                            )
                                        },
                                    )
                                },
                                onClick = { onDudu7FrostTextureEnabledChange(!dudu7FrostTextureEnabled) },
                            ),
                        )
                        if (dudu7FrostTextureEnabled) {
                            add(
                                Material3SettingsItem(
                                    icon = painterResource(R.drawable.palette),
                                    title = { Text("Froststruktur-Stärke") },
                                    description = { Text("${dudu7FrostTextureStrength}%") },
                                    trailingContent = {
                                        Slider(
                                            value = dudu7FrostTextureStrength.toFloat(),
                                            onValueChange = { onDudu7FrostTextureStrengthChange(it.roundToInt()) },
                                            valueRange = 0f..100f,
                                            steps = 19,
                                            modifier = Modifier.fillMaxWidth(0.42f),
                                        )
                                    },
                                    onClick = {},
                                ),
                            )
                        }
"""
    text = replace_once(text, blur_item, frost_items, "frost settings")
save(path, text)

# Vehicle layout: remove accidentally duplicated nested glass layers and install one global theme.
path = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
text = load(path)
if "import androidx.compose.foundation.Canvas" not in text:
    text = replace_once(
        text,
        "import androidx.compose.foundation.BorderStroke\n",
        "import androidx.compose.foundation.BorderStroke\nimport androidx.compose.foundation.Canvas\n",
        "Canvas import",
    )
if "import androidx.compose.ui.graphics.BlendMode" not in text:
    text = replace_once(
        text,
        "import androidx.compose.ui.geometry.Offset\n",
        "import androidx.compose.ui.geometry.Offset\nimport androidx.compose.ui.graphics.BlendMode\nimport androidx.compose.ui.graphics.Color\n",
        "graphics imports",
    )
if "Dudu7FrostTextureEnabledKey" not in text:
    text = replace_once(
        text,
        "import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n",
        "import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n"
        "import com.metrolist.music.constants.Dudu7FrostTextureEnabledKey\n"
        "import com.metrolist.music.constants.Dudu7FrostTextureStrengthKey\n",
        "layout preference imports",
    )
if "private fun FrostTextureOverlay" not in text:
    helper = """
@Composable
private fun FrostTextureOverlay(
    strength: Int,
    modifier: Modifier = Modifier,
) {
    val normalized = strength.coerceIn(0, 100) / 100f
    if (normalized <= 0f) return
    Canvas(modifier = modifier) {
        val spacing = 52.dp.toPx()
        val lightAlpha = 0.20f * normalized
        val darkAlpha = 0.08f * normalized
        var x = -size.height
        while (x < size.width + size.height) {
            drawLine(
                color = Color.White.copy(alpha = lightAlpha),
                start = Offset(x, 0f),
                end = Offset(x + size.height, size.height),
                strokeWidth = 1.2.dp.toPx(),
                blendMode = BlendMode.Screen,
            )
            drawLine(
                color = Color.Black.copy(alpha = darkAlpha),
                start = Offset(x + spacing * 0.34f, 0f),
                end = Offset(x + size.height + spacing * 0.34f, size.height),
                strokeWidth = 0.7.dp.toPx(),
                blendMode = BlendMode.Multiply,
            )
            x += spacing
        }
        val dotSpacing = 68.dp.toPx()
        var row = 0
        var y = dotSpacing * 0.45f
        while (y < size.height) {
            var dotX = if (row % 2 == 0) dotSpacing * 0.35f else dotSpacing * 0.85f
            while (dotX < size.width) {
                drawCircle(
                    color = Color.White.copy(alpha = lightAlpha * 0.55f),
                    radius = 1.15.dp.toPx(),
                    center = Offset(dotX, y),
                    blendMode = BlendMode.Screen,
                )
                dotX += dotSpacing
            }
            y += dotSpacing
            row++
        }
    }
}

"""
    text = replace_once(
        text,
        "@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout",
        helper + "@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout",
        "texture helper",
    )
start = text.index("    val (frostedIceEnabled) = rememberPreference(")
old_tail = text[start:]
left_start = old_tail.index("        Column(\n")
left_column = extract_block(old_tail, left_start)
right_start = old_tail.index("            Column(Modifier.fillMaxSize()) {")
right_column = extract_block(old_tail, right_start)
new_tail = """    val (frostedIceEnabled) = rememberPreference(
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
                primaryContainer = baseColors.primaryContainer.copy(alpha = glassAlpha),
                secondaryContainer = baseColors.secondaryContainer.copy(alpha = glassAlpha),
                tertiaryContainer = baseColors.tertiaryContainer.copy(alpha = glassAlpha),
                errorContainer = baseColors.errorContainer.copy(alpha = glassAlpha),
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
""" + left_column + """

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
""" + right_column + """
                    }
                }
            }
        }
    }
}
"""
text = text[:start] + new_tail
save(path, text)

# Invalidate track artwork immediately when the physical station identity changes.
path = "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt"
text = load(path)
if "var lastFmIdentity" not in text:
    text = replace_once(
        text,
        "    var recognitionFrequency by remember { mutableStateOf<Float?>(null) }\n",
        "    var recognitionFrequency by remember { mutableStateOf<Float?>(null) }\n"
        "    var lastFmIdentity by remember { mutableStateOf(\"\") }\n",
        "FM identity state",
    )
old_effect = """    LaunchedEffect(state.isActive, state.displayStation, state.rt) {
        if (state.isActive) {
            FmNowPlayingResolver.resolve(state.displayStation, state.rt)
        } else {
            FmNowPlayingResolver.clear()
        }
    }
"""
new_effect = """    LaunchedEffect(state.isActive, state.frequency, state.pi, state.displayStation, state.rt) {
        if (state.isActive) {
            val identity = "${state.displayStation}|${state.frequency}|${state.pi}|${state.ecc}"
            if (identity != lastFmIdentity) {
                FmNowPlayingResolver.clear()
                lastFmIdentity = identity
            }
            FmNowPlayingResolver.resolve(state.displayStation, state.rt)
        } else {
            lastFmIdentity = ""
            FmNowPlayingResolver.clear()
        }
    }
"""
text = replace_once(text, old_effect, new_effect, "FM resolver effect")
save(path, text)

# Publish sender and recognized-track artwork through the FM Media3 player.
path = "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FmSessionPlayer.kt"
text = load(path)
text = replace_once(text, "import android.content.Context\n", "import android.content.Context\nimport android.net.Uri\n", "Uri import")
text = replace_once(
    text,
    "import com.metrolist.music.radio.fyt.FmFavouriteRef\n",
    "import com.metrolist.music.radio.fyt.FmFavouriteRef\nimport com.metrolist.music.radio.fyt.FmNowPlayingResolver\n",
    "now-playing import",
)
text = replace_once(
    text,
    "import com.metrolist.music.radio.fyt.FytPhysicalRadio\n",
    "import com.metrolist.music.radio.fyt.FytPhysicalRadio\nimport com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver\n",
    "logo resolver import",
)
text = replace_once(text, "import kotlinx.coroutines.Dispatchers\n", "import kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.Job\n", "Job import")
text = replace_once(
    text,
    "    private var released = false\n",
    "    private var released = false\n"
    "    private var nowPlayingSnapshot = FmNowPlayingResolver.state.value\n"
    "    private var stationArtworkUri: String? = null\n"
    "    private var stationArtworkKey: String = \"\"\n"
    "    private var artworkJob: Job? = null\n",
    "artwork state",
)
owner_collect = """        scope.launch {
            Dudu7FmSessionOwnership.claimed.collect { claimed ->
"""
text = replace_once(
    text,
    owner_collect,
    """        scope.launch {
            FmNowPlayingResolver.state.collect { nowPlaying ->
                nowPlayingSnapshot = nowPlaying
                invalidateState()
            }
        }
        scope.launch {
            ReliableFmStationLogoResolver.revisions.collect {
                refreshStationArtwork(snapshot)
            }
        }
""" + owner_collect,
    "artwork collectors",
)
text = replace_once(
    text,
    """    private fun syncFromRadio(state: FytPhysicalRadio.State) {
        snapshot = state
""",
    """    private fun syncFromRadio(state: FytPhysicalRadio.State) {
        val previousArtworkKey = stationArtworkKey
        snapshot = state
        val newArtworkKey = artworkIdentity(state)
        if (newArtworkKey != previousArtworkKey) {
            stationArtworkKey = newArtworkKey
            nowPlayingSnapshot = FmNowPlayingResolver.NowPlaying()
            stationArtworkUri = cachedStationArtwork(state)
            refreshStationArtwork(state)
        }
""",
    "radio sync artwork",
)
text = replace_once(
    text,
    """                radioText = snapshot.rt,
            )""",
    """                radioText = snapshot.rt,
                artworkUri = currentArtworkUri(),
            )""",
    "live metadata artwork",
)
text = replace_once(
    text,
    """                radioText = snapshot.rt.takeIf { isCurrent && snapshot.isActive }.orEmpty(),
            )""",
    """                radioText = snapshot.rt.takeIf { isCurrent && snapshot.isActive }.orEmpty(),
                artworkUri = if (isCurrent) currentArtworkUri() else presetArtworkUri(preset),
            )""",
    "preset metadata artwork",
)
text = replace_once(
    text,
    """        radioText: String,
    ): MediaMetadata {""",
    """        radioText: String,
        artworkUri: Uri?,
    ): MediaMetadata {""",
    "metadata signature",
)
text = replace_once(
    text,
    """            .setAlbumTitle("FM-Radio")
            .setIsPlayable(true)""",
    """            .setAlbumTitle("FM-Radio")
            .setArtworkUri(artworkUri)
            .setIsPlayable(true)""",
    "metadata artwork URI",
)
helpers = """
    private fun currentArtworkUri(): Uri? {
        val recognizedCover =
            nowPlayingSnapshot.coverUrl?.takeIf {
                it.isNotBlank() && nowPlayingSnapshot.stationName.equals(snapshot.displayStation, ignoreCase = true)
            }
        return (recognizedCover ?: stationArtworkUri)
            ?.takeIf(String::isNotBlank)
            ?.let { runCatching { Uri.parse(it) }.getOrNull() }
    }

    private fun presetArtworkUri(preset: FytPhysicalRadio.Preset): Uri? =
        ReliableFmStationLogoResolver.cachedLogo(
            context = appContext,
            stationName = preset.name,
            frequency = preset.frequency,
            pi = preset.pi,
            ecc = preset.ecc,
            allFrequencies = FytPhysicalRadio.presetFrequencies(preset),
        )?.let { runCatching { Uri.parse(it) }.getOrNull() }

    private fun artworkIdentity(state: FytPhysicalRadio.State): String =
        "${state.displayStation}|${formatFrequency(state.frequency)}|${state.pi and 0xffff}|${state.ecc}"

    private fun cachedStationArtwork(state: FytPhysicalRadio.State): String? =
        ReliableFmStationLogoResolver.cachedLogo(
            context = appContext,
            stationName = state.displayStation,
            frequency = state.frequency,
            pi = state.pi,
            ecc = state.ecc,
            allFrequencies = listOf(state.frequency) + state.alternativeFrequencies,
        )

    private fun refreshStationArtwork(state: FytPhysicalRadio.State) {
        if (!state.isActive && !sessionClaimed) return
        val requestKey = artworkIdentity(state)
        artworkJob?.cancel()
        artworkJob =
            scope.launch {
                val resolved =
                    ReliableFmStationLogoResolver.resolve(
                        context = appContext,
                        stationName = state.displayStation,
                        frequency = state.frequency,
                        pi = state.pi,
                        ecc = state.ecc,
                        allFrequencies = listOf(state.frequency) + state.alternativeFrequencies,
                    )
                if (stationArtworkKey == requestKey && resolved != stationArtworkUri) {
                    stationArtworkUri = resolved
                    invalidateState()
                }
            }
    }

"""
text = replace_once(
    text,
    "    private fun availableCommands(hasItems: Boolean): Player.Commands =\n",
    helpers + "    private fun availableCommands(hasItems: Boolean): Player.Commands =\n",
    "session artwork helpers",
)
save(path, text)

# Gradient background cache must react to artwork changes while the media ID remains stable.
path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
text = load(path)
text = replace_once(
    text,
    "LaunchedEffect(mediaMetadata?.id, playerBackground) {",
    "LaunchedEffect(mediaMetadata?.id, mediaMetadata?.thumbnailUrl, playerBackground) {",
    "gradient effect key",
)
text = replace_once(
    text,
    """                val cachedColors = gradientColorsCache[currentMetadata.id]
                if (cachedColors != null) {
                    gradientColors = cachedColors
                    return@LaunchedEffect
                }
""",
    """                val artworkCacheKey = "${currentMetadata.id}|${currentMetadata.thumbnailUrl}"
                val cachedColors = gradientColorsCache[artworkCacheKey]
                if (cachedColors != null) {
                    gradientColors = cachedColors
                    return@LaunchedEffect
                }
""",
    "gradient artwork cache key",
)
text = replace_once(
    text,
    '.memoryCacheKey("gradient_${currentMetadata.id}")',
    '.memoryCacheKey("gradient_${artworkCacheKey.hashCode()}")',
    "Coil gradient cache key",
)
text = replace_once(
    text,
    "gradientColorsCache[currentMetadata.id] = extractedColors",
    "gradientColorsCache[artworkCacheKey] = extractedColors",
    "gradient result cache key",
)
save(path, text)

# Guard against partial application.
assert "versionCode = 1370061" in load("app/build.gradle.kts")
assert "Froststruktur anzeigen" in load("app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt")
layout = load("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
assert layout.count("MaterialTheme(colorScheme = frostedColors)") == 1
assert "background = baseColors.background.copy(alpha = glassAlpha)" in layout
assert "frostedGlassStrength.coerceIn(0, 100)" in layout
session = load("app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FmSessionPlayer.kt")
assert ".setArtworkUri(artworkUri)" in session
assert "stationArtworkKey == requestKey" in session
print("Issues 94, 96 and 97 applied")
