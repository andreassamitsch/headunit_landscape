from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'Expected exactly one match in {path}: found {count} for {old[:120]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


metrics = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/player/VehicleRadioPlayerMetrics.kt'
metrics.parent.mkdir(parents=True, exist_ok=True)
metrics.write_text(
    '''package com.metrolist.music.ui.player

import androidx.compose.ui.unit.dp
import com.metrolist.music.constants.ThumbnailCornerRadius

/** Shared dimensions for the Dudu7 radio/player presentation. */
object VehicleRadioPlayerMetrics {
    val ArtworkHorizontalPadding = 2.dp
    val ArtworkCornerRadius = ThumbnailCornerRadius * 2

    val PreviousNextButtonSize = 48.dp
    val PreviousNextIconSize = 30.dp
    val PlayButtonSize = 68.dp
    val PlayIconSize = 36.dp

    val SecondaryActionButtonSize = 46.dp
    val SecondaryActionIconSize = 27.dp
    val SecondaryActionLargeIconSize = 28.dp
}
''',
    encoding='utf-8',
)

prefs = ROOT / 'app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt'
replace_once(
    prefs,
    'val Dudu7BackgroundBlurStrengthKey = intPreferencesKey("dudu7BackgroundBlurStrength")\n',
    'val Dudu7BackgroundBlurStrengthKey = intPreferencesKey("dudu7BackgroundBlurStrength")\n'
    'val Dudu7BackgroundBottomScrimStrengthKey = intPreferencesKey("dudu7BackgroundBottomScrimStrength")\n',
)

appearance = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt'
replace_once(
    appearance,
    'import com.metrolist.music.constants.Dudu7BackgroundBlurStrengthKey\n',
    'import com.metrolist.music.constants.Dudu7BackgroundBlurStrengthKey\n'
    'import com.metrolist.music.constants.Dudu7BackgroundBottomScrimStrengthKey\n',
)
replace_once(
    appearance,
    '''    val (dudu7BackgroundBlurStrength, onDudu7BackgroundBlurStrengthChange) =
        rememberPreference(
            Dudu7BackgroundBlurStrengthKey,
            defaultValue = 120,
        )
''',
    '''    val (dudu7BackgroundBlurStrength, onDudu7BackgroundBlurStrengthChange) =
        rememberPreference(
            Dudu7BackgroundBlurStrengthKey,
            defaultValue = 120,
        )
    val (dudu7BackgroundBottomScrimStrength, onDudu7BackgroundBottomScrimStrengthChange) =
        rememberPreference(
            Dudu7BackgroundBottomScrimStrengthKey,
            defaultValue = 35,
        )
''',
)
replace_once(
    appearance,
    '''                    add(
                        Material3SettingsItem(
                            icon = painterResource(R.drawable.palette),
                            title = { Text("Dudu7-Hintergrund-Unschärfe") },
                            description = { Text("${dudu7BackgroundBlurStrength} dp · unabhängig vom Glas") },
                            trailingContent = {
                                Slider(
                                    value = dudu7BackgroundBlurStrength.toFloat(),
                                    onValueChange = { onDudu7BackgroundBlurStrengthChange(it.roundToInt()) },
                                    valueRange = 0f..200f,
                                    steps = 199,
                                    modifier = Modifier.fillMaxWidth(0.42f),
                                )
                            },
                            onClick = {},
                        ),
                    )
''',
    '''                    add(
                        Material3SettingsItem(
                            icon = painterResource(R.drawable.palette),
                            title = { Text("Dudu7-Hintergrund-Unschärfe") },
                            description = { Text("${dudu7BackgroundBlurStrength} dp · unabhängig vom Glas") },
                            trailingContent = {
                                Slider(
                                    value = dudu7BackgroundBlurStrength.toFloat(),
                                    onValueChange = { onDudu7BackgroundBlurStrengthChange(it.roundToInt()) },
                                    valueRange = 0f..200f,
                                    steps = 199,
                                    modifier = Modifier.fillMaxWidth(0.42f),
                                )
                            },
                            onClick = {},
                        ),
                    )
                    add(
                        Material3SettingsItem(
                            icon = painterResource(R.drawable.palette),
                            title = { Text("Unteren Hintergrund abdunkeln") },
                            description = {
                                Text(
                                    if (dudu7BackgroundBlurStrength > 0) {
                                        "${dudu7BackgroundBottomScrimStrength}% · weicher Verlauf"
                                    } else {
                                        "Wirkt bei aktivierter Hintergrund-Unschärfe"
                                    },
                                )
                            },
                            trailingContent = {
                                Slider(
                                    value = dudu7BackgroundBottomScrimStrength.toFloat(),
                                    onValueChange = { onDudu7BackgroundBottomScrimStrengthChange(it.roundToInt()) },
                                    valueRange = 0f..100f,
                                    steps = 99,
                                    enabled = dudu7BackgroundBlurStrength > 0,
                                    modifier = Modifier.fillMaxWidth(0.42f),
                                )
                            },
                            onClick = {},
                        ),
                    )
''',
)

player = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt'
replace_once(
    player,
    'import com.metrolist.music.constants.Dudu7BackgroundBlurStrengthKey\n',
    'import com.metrolist.music.constants.Dudu7BackgroundBlurStrengthKey\n'
    'import com.metrolist.music.constants.Dudu7BackgroundBottomScrimStrengthKey\n',
)
replace_once(
    player,
    '''    val dudu7BackgroundBlurStrength by rememberPreference(Dudu7BackgroundBlurStrengthKey, defaultValue = 120)
    val artworkBackgroundBlur =
''',
    '''    val dudu7BackgroundBlurStrength by rememberPreference(Dudu7BackgroundBlurStrengthKey, defaultValue = 120)
    val dudu7BackgroundBottomScrimStrength by
        rememberPreference(Dudu7BackgroundBottomScrimStrengthKey, defaultValue = 35)
    val dudu7BackgroundBottomScrimAlpha =
        dudu7BackgroundBottomScrimStrength.coerceIn(0, 100) / 100f * 0.80f
    val artworkBackgroundBlur =
''',
)
replace_once(
    player,
    '                                    landscapeHorizontalPadding = 2.dp,\n',
    '                                    landscapeHorizontalPadding = VehicleRadioPlayerMetrics.ArtworkHorizontalPadding,\n',
)
replace_once(
    player,
    '''                    else -> {
                        PlayerBackgroundStyle.DEFAULT
                    }
                }
            }
''',
    '''                    else -> {
                        PlayerBackgroundStyle.DEFAULT
                    }
                }
                if (
                    VehicleVariantConfig.isDudu7 &&
                    playerBackground == PlayerBackgroundStyle.BLUR &&
                    dudu7BackgroundBlurStrength > 0 &&
                    dudu7BackgroundBottomScrimAlpha > 0f
                ) {
                    Box(
                        modifier =
                            Modifier
                                .fillMaxSize()
                                .alpha(backgroundAlpha)
                                .background(
                                    Brush.verticalGradient(
                                        colorStops =
                                            arrayOf(
                                                0.00f to Color.Transparent,
                                                0.48f to Color.Transparent,
                                                0.72f to Color.Black.copy(alpha = dudu7BackgroundBottomScrimAlpha * 0.22f),
                                                0.88f to Color.Black.copy(alpha = dudu7BackgroundBottomScrimAlpha * 0.58f),
                                                1.00f to Color.Black.copy(alpha = dudu7BackgroundBottomScrimAlpha),
                                            ),
                                    ),
                                ),
                    )
                }
            }
''',
)

controls = ROOT / 'app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt'
replace_once(
    controls,
    'import com.metrolist.music.R\n',
    'import com.metrolist.music.R\nimport com.metrolist.music.ui.player.VehicleRadioPlayerMetrics\n',
)
text = controls.read_text(encoding='utf-8')
text = text.replace('buttonSize = 46.dp,', 'buttonSize = VehicleRadioPlayerMetrics.SecondaryActionButtonSize,')
text = text.replace('iconSize = 27.dp,', 'iconSize = VehicleRadioPlayerMetrics.SecondaryActionIconSize,')
text = text.replace('iconSize = 28.dp,', 'iconSize = VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize,')
text = text.replace('modifier = Modifier.size(48.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextButtonSize),')
text = text.replace('modifier = Modifier.size(30.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextIconSize),')
text = text.replace('modifier = Modifier.size(68.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayButtonSize),')
text = text.replace('modifier = Modifier.size(36.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayIconSize),')
controls.write_text(text, encoding='utf-8')

fm = ROOT / 'app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt'
replace_once(
    fm,
    'import com.metrolist.music.playback.PlayerConnection\n',
    'import com.metrolist.music.playback.PlayerConnection\nimport com.metrolist.music.ui.player.VehicleRadioPlayerMetrics\n',
)
replace_once(
    fm,
    '        modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp, vertical = 4.dp),\n',
    '        modifier = Modifier.fillMaxSize(),\n',
)
replace_once(
    fm,
    '            modifier = Modifier.weight(1f).fillMaxWidth(),\n',
    '            modifier = Modifier.weight(1f).fillMaxWidth().padding(top = 2.dp, bottom = 2.dp),\n',
)
replace_once(
    fm,
    '''            // Match the large WebRadio artwork footprint instead of the old 190 dp FM tile.
            val artworkSize = minOf(maxWidth, maxHeight).coerceAtMost(340.dp)
            if (hasRecognizedTrackArtwork) {
                AsyncImage(
                    model = nowPlaying.coverUrl,
                    contentDescription = "Cover $displayTitle",
                    contentScale = ContentScale.Fit,
                    error = painterResource(R.drawable.radio),
                    fallback = painterResource(R.drawable.radio),
                    modifier =
                        Modifier
                            .size(artworkSize)
                            .clip(RoundedCornerShape(26.dp)),
                )
                Box(
                    modifier =
                        Modifier
                            .align(Alignment.BottomEnd)
                            .padding(10.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color.White.copy(alpha = 0.78f))
                            .padding(3.dp)
                            .graphicsLayer { alpha = 0.86f },
                ) {
                    FmStationArtwork(
                        stationName = state.displayStation,
                        frequency = state.frequency,
                        pi = state.pi,
                        ecc = state.ecc,
                        size = 52.dp,
                        allFrequencies =
                            (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                                state.alternativeFrequencies + state.frequency),
                    )
                }
            } else {
                FmStationArtwork(
                    stationName = state.displayStation,
                    frequency = state.frequency,
                    pi = state.pi,
                    ecc = state.ecc,
                    size = artworkSize,
                    allFrequencies =
                        (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                            state.alternativeFrequencies + state.frequency),
                )
            }
            if (nowPlaying.resolving) {
                CircularProgressIndicator(
                    color = actionColor,
                    strokeWidth = 2.dp,
                    modifier = Modifier.align(Alignment.BottomEnd).size(24.dp),
                )
            }
''',
    '''            val artworkSize =
                (minOf(maxWidth, maxHeight) -
                    (VehicleRadioPlayerMetrics.ArtworkHorizontalPadding * 2)).coerceAtLeast(0.dp)
            val artworkShape = RoundedCornerShape(VehicleRadioPlayerMetrics.ArtworkCornerRadius)
            Box(modifier = Modifier.size(artworkSize)) {
                if (hasRecognizedTrackArtwork) {
                    AsyncImage(
                        model = nowPlaying.coverUrl,
                        contentDescription = "Cover $displayTitle",
                        contentScale = ContentScale.Fit,
                        error = painterResource(R.drawable.radio),
                        fallback = painterResource(R.drawable.radio),
                        modifier = Modifier.fillMaxSize().clip(artworkShape),
                    )
                    Box(
                        modifier =
                            Modifier
                                .align(Alignment.BottomEnd)
                                .padding(10.dp)
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White.copy(alpha = 0.78f))
                                .padding(3.dp)
                                .graphicsLayer { alpha = 0.86f },
                    ) {
                        FmStationArtwork(
                            stationName = state.displayStation,
                            frequency = state.frequency,
                            pi = state.pi,
                            ecc = state.ecc,
                            size = 52.dp,
                            allFrequencies =
                                (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                                    state.alternativeFrequencies + state.frequency),
                        )
                    }
                } else {
                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier.fillMaxSize().clip(artworkShape),
                    ) {
                        FmStationArtwork(
                            stationName = state.displayStation,
                            frequency = state.frequency,
                            pi = state.pi,
                            ecc = state.ecc,
                            size = artworkSize,
                            allFrequencies =
                                (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +
                                    state.alternativeFrequencies + state.frequency),
                        )
                    }
                }
                if (nowPlaying.resolving) {
                    CircularProgressIndicator(
                        color = actionColor,
                        strokeWidth = 2.dp,
                        modifier = Modifier.align(Alignment.BottomEnd).padding(4.dp).size(24.dp),
                    )
                }
            }
''',
)
replace_once(fm, '            style = MaterialTheme.typography.headlineMedium,\n', '            style = MaterialTheme.typography.titleLarge,\n')
replace_once(
    fm,
    '                    .fillMaxWidth()\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n',
    '                    .fillMaxWidth()\n                    .padding(horizontal = 8.dp)\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n',
)
text = fm.read_text(encoding='utf-8')
needle = '                    .fillMaxWidth()\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n'
if needle not in text:
    raise RuntimeError('Artist modifier marker missing after title replacement')
text = text.replace(
    needle,
    '                    .fillMaxWidth()\n                    .padding(horizontal = 8.dp)\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n',
    1,
)
fm.write_text(text, encoding='utf-8')
replace_once(
    fm,
    '            maxLines = 2,\n            overflow = TextOverflow.Ellipsis,\n            modifier =\n                Modifier\n                    .fillMaxWidth()\n                    .padding(horizontal = 8.dp)\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n                        val matchedArtist',
    '            maxLines = 1,\n            overflow = TextOverflow.Ellipsis,\n            modifier =\n                Modifier\n                    .fillMaxWidth()\n                    .padding(horizontal = 8.dp)\n                    .clickable(enabled = nowPlaying.hasTrackMetadata) {\n                        val matchedArtist',
)
replace_once(fm, '        Spacer(Modifier.height(10.dp))\n', '        Spacer(Modifier.height(5.dp))\n')
text = fm.read_text(encoding='utf-8')
text = text.replace(
    'modifier = Modifier.fillMaxWidth(),\n        ) {\n            IconButton(',
    'modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),\n        ) {\n            IconButton(',
    1,
)
text = text.replace('modifier = Modifier.size(58.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextButtonSize),')
text = text.replace('modifier = Modifier.size(34.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PreviousNextIconSize),')
text = text.replace('modifier = Modifier.size(76.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayButtonSize),')
text = text.replace('modifier = Modifier.size(39.dp),', 'modifier = Modifier.size(VehicleRadioPlayerMetrics.PlayIconSize),')
text = text.replace(
    'modifier = Modifier.fillMaxWidth().height(52.dp),',
    'modifier = Modifier.fillMaxWidth().height(VehicleRadioPlayerMetrics.SecondaryActionButtonSize).padding(horizontal = 8.dp),',
)
text = text.replace(
    'modifier = Modifier.align(Alignment.CenterStart),',
    'modifier = Modifier.align(Alignment.CenterStart).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),',
    1,
)
text = text.replace(
    'tint = if (isStationFavourite) actionColor else sideButtonContentColor,\n                )',
    'tint = if (isStationFavourite) actionColor else sideButtonContentColor,\n                    modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionIconSize),\n                )',
    1,
)
text = text.replace(
    'modifier = Modifier.align(Alignment.CenterEnd),\n                ) {\n                    Icon(',
    'modifier = Modifier.align(Alignment.CenterEnd).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),\n                ) {\n                    Icon(',
    1,
)
text = text.replace(
    'tint = if (isSongLiked) actionColor else sideButtonContentColor,\n                    )',
    'tint = if (isSongLiked) actionColor else sideButtonContentColor,\n                        modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize),\n                    )',
    1,
)
text = text.replace(
    'modifier = Modifier.align(Alignment.CenterEnd),\n                ) {\n                    if (recognitionInProgress)',
    'modifier = Modifier.align(Alignment.CenterEnd).size(VehicleRadioPlayerMetrics.SecondaryActionButtonSize),\n                ) {\n                    if (recognitionInProgress)',
    1,
)
text = text.replace(
    'modifier = Modifier.size(24.dp))',
    'modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize))',
    1,
)
text = text.replace('painter = painterResource(R.drawable.search),', 'painter = painterResource(R.drawable.manage_search),', 1)
text = text.replace(
    'tint = sideButtonContentColor,\n                        )',
    'tint = sideButtonContentColor,\n                            modifier = Modifier.size(VehicleRadioPlayerMetrics.SecondaryActionLargeIconSize),\n                        )',
    1,
)
fm.write_text(text, encoding='utf-8')

build = ROOT / 'app/build.gradle.kts'
replace_once(build, 'versionCode = 1370071', 'versionCode = 1370072')
replace_once(build, 'versionName = "13.7.62"', 'versionName = "13.7.63"')

assert 'coerceAtMost(340.dp)' not in fm.read_text(encoding='utf-8')
assert 'R.drawable.search' not in fm.read_text(encoding='utf-8')
assert 'Dudu7BackgroundBottomScrimStrengthKey' in player.read_text(encoding='utf-8')
assert 'VehicleRadioPlayerMetrics.ArtworkHorizontalPadding' in player.read_text(encoding='utf-8')
assert 'versionCode = 1370072' in build.read_text(encoding='utf-8')
print('Issues #111 and #122 patch applied')
