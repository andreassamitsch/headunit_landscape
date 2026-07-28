#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


# Version --------------------------------------------------------------------
build_path = "app/build.gradle.kts"
build = read(build_path)
build = replace_once(build, 'versionCode = 1370025', 'versionCode = 1370026', 'versionCode')
build = replace_once(build, 'versionName = "13.7.16"', 'versionName = "13.7.17"', 'versionName')
write(build_path, build)


# Artwork composable ---------------------------------------------------------
artwork_path = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmStationArtwork.kt"
artwork = read(artwork_path)
start = artwork.index("@Composable\nfun FmStationArtwork(")
new_tail = r'''@Composable
fun FmStationArtwork(
    stationName: String,
    frequency: Float,
    pi: Int = 0,
    ecc: String? = null,
    size: Dp,
    modifier: Modifier = Modifier,
    allFrequencies: List<Float> = emptyList(),
) {
    val context = LocalContext.current
    val revision by ReliableFmStationLogoResolver.revisions.collectAsState()
    val lookupFrequencies =
        remember(frequency, allFrequencies) {
            (listOf(frequency) + allFrequencies)
                .filter { it in 65f..110f }
                .distinctBy { (it * 100f).roundToInt() }
        }
    val artworkKey =
        remember(stationName, frequency, lookupFrequencies, pi, ecc, revision) {
            val frequencyKey = lookupFrequencies.joinToString("-") { (it * 100f).roundToInt().toString() }
            if (pi > 0) {
                "pi-${(pi and 0xffff).toString(16)}-${ecc.orEmpty()}-$frequencyKey-$revision"
            } else {
                "${stationName.trim()}-$frequencyKey-$revision"
            }
        }
    var artworkUrl by
        remember(artworkKey) {
            mutableStateOf(
                ReliableFmStationLogoResolver.cachedLogo(
                    context = context,
                    stationName = stationName,
                    frequency = frequency,
                    pi = pi,
                    ecc = ecc,
                    allFrequencies = lookupFrequencies,
                ),
            )
        }
    LaunchedEffect(artworkKey) {
        if (artworkUrl.isNullOrBlank()) {
            artworkUrl =
                ReliableFmStationLogoResolver.resolve(
                    context = context,
                    stationName = stationName,
                    frequency = frequency,
                    pi = pi,
                    ecc = ecc,
                    allFrequencies = lookupFrequencies,
                )
        }
    }
    val shape = RoundedCornerShape((size.value / 7f).dp)
    if (!artworkUrl.isNullOrBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo $stationName",
            contentScale = ContentScale.Fit,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        )
    } else {
        Box(
            contentAlignment = Alignment.Center,
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size((size.value * 0.62f).dp),
            )
        }
    }
}
'''
artwork = artwork[:start] + new_tail
write(artwork_path, artwork)


# Logo picker ---------------------------------------------------------------
picker_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/FmLogoPickerDialog.kt"
picker = read(picker_path)
picker = replace_once(
    picker,
    "import com.metrolist.music.radio.fyt.FmStationLogoResolver",
    "import com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver",
    "picker resolver import",
)
picker = replace_once(
    picker,
    "val info = FmStationLogoResolver.logoInfo(context, preset.name, preset.frequency, preset.pi)",
    "val info = ReliableFmStationLogoResolver.logoInfo(\n        context, preset.name, preset.frequency, preset.pi, preset.ecc, FytPhysicalRadio.presetFrequencies(preset),\n    )",
    "picker info",
)
picker = replace_once(
    picker,
    "FmStationLogoResolver.searchCandidates(\n                    context = context,\n                    stationName = preset.name,\n                    frequency = preset.frequency,\n                    pi = preset.pi,\n                    ecc = preset.ecc,\n                )",
    "ReliableFmStationLogoResolver.searchCandidates(\n                    context = context,\n                    stationName = preset.name,\n                    frequency = preset.frequency,\n                    pi = preset.pi,\n                    ecc = preset.ecc,\n                    allFrequencies = FytPhysicalRadio.presetFrequencies(preset),\n                )",
    "picker candidates",
)
picker = replace_once(
    picker,
    "FmStationLogoResolver.setManualLogo(\n                    context = context,\n                    stationName = preset.name,\n                    frequency = preset.frequency,\n                    pi = preset.pi,\n                    sourceUrl = candidate.url,",
    "ReliableFmStationLogoResolver.setManualLogo(\n                    context = context,\n                    stationName = preset.name,\n                    frequency = preset.frequency,\n                    pi = preset.pi,\n                    ecc = preset.ecc,\n                    sourceUrl = candidate.url,",
    "picker manual store",
)
picker = replace_once(
    picker,
    "ecc = preset.ecc,\n                        size = 72.dp,",
    "ecc = preset.ecc,\n                        size = 72.dp,\n                        allFrequencies = FytPhysicalRadio.presetFrequencies(preset),",
    "picker preview frequencies",
)
picker = replace_once(
    picker,
    "FmStationLogoResolver.clearManualLogo(context, preset.name, preset.frequency, preset.pi)",
    "ReliableFmStationLogoResolver.clearManualLogo(context, preset.name, preset.frequency, preset.pi, preset.ecc)",
    "picker clear manual",
)
picker = replace_once(
    picker,
    "FmStationLogoResolver.invalidateAuto(context, preset.name, preset.frequency, preset.pi)\n                            FmStationLogoResolver.resolve(\n                                context,\n                                preset.name,\n                                preset.frequency,\n                                preset.pi,\n                                preset.ecc,\n                                force = true,\n                            )",
    "ReliableFmStationLogoResolver.invalidateAuto(context, preset.name, preset.frequency, preset.pi, preset.ecc)\n                            ReliableFmStationLogoResolver.resolve(\n                                context = context,\n                                stationName = preset.name,\n                                frequency = preset.frequency,\n                                pi = preset.pi,\n                                ecc = preset.ecc,\n                                force = true,\n                                allFrequencies = FytPhysicalRadio.presetFrequencies(preset),\n                            )",
    "picker automatic refresh",
)
write(picker_path, picker)


# Diagnostics ---------------------------------------------------------------
diag_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/FmRadioDiagnostics.kt"
diag = read(diag_path)
diag = replace_once(
    diag,
    "import com.metrolist.music.radio.fyt.FmStationLogoResolver",
    "import com.metrolist.music.radio.fyt.ReliableFmStationLogoResolver",
    "diagnostics resolver import",
)
diag = diag.replace("FmStationLogoResolver", "ReliableFmStationLogoResolver")
diag = replace_once(
    diag,
    "val info = ReliableFmStationLogoResolver.logoInfo(context, state.displayStation, state.frequency, state.pi)",
    "val info = ReliableFmStationLogoResolver.logoInfo(\n        context, state.displayStation, state.frequency, state.pi, state.ecc,\n        listOf(state.frequency) + state.alternativeFrequencies,\n    )",
    "diagnostics info",
)
diag = replace_once(
    diag,
    "ReliableFmStationLogoResolver.invalidateAuto(context, state.displayStation, state.frequency, state.pi)\n                    ReliableFmStationLogoResolver.resolve(\n                        context,\n                        state.displayStation,\n                        state.frequency,\n                        state.pi,\n                        state.ecc,\n                        force = true,\n                    )",
    "ReliableFmStationLogoResolver.invalidateAuto(\n                        context, state.displayStation, state.frequency, state.pi, state.ecc,\n                    )\n                    ReliableFmStationLogoResolver.resolve(\n                        context = context,\n                        stationName = state.displayStation,\n                        frequency = state.frequency,\n                        pi = state.pi,\n                        ecc = state.ecc,\n                        force = true,\n                        allFrequencies = listOf(state.frequency) + state.alternativeFrequencies,\n                    )",
    "diagnostics refresh",
)
write(diag_path, diag)


# Physical radio list/search/manual artwork ---------------------------------
screen_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
screen = read(screen_path)
screen = replace_once(
    screen,
    "pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    isActive = isActive,",
    "pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    activeFrequency = state.frequency,\n                                    activeEcc = state.ecc,\n                                    activeAlternativeFrequencies = state.alternativeFrequencies,\n                                    isActive = isActive,",
    "favourite live identity arguments",
)
screen = replace_once(
    screen,
    "private fun FmFavouriteRow(\n    preset: FytPhysicalRadio.Preset,\n    pi: Int,\n    isActive: Boolean,",
    "private fun FmFavouriteRow(\n    preset: FytPhysicalRadio.Preset,\n    pi: Int,\n    activeFrequency: Float,\n    activeEcc: String,\n    activeAlternativeFrequencies: List<Float>,\n    isActive: Boolean,",
    "favourite row signature",
)
screen = replace_once(
    screen,
    "FmStationArtwork(\n            stationName = preset.name,\n            frequency = preset.frequency,\n            pi = pi,\n            ecc = preset.ecc,\n            size = 56.dp,\n        )",
    "FmStationArtwork(\n            stationName = preset.name,\n            frequency = if (isActive) activeFrequency else preset.frequency,\n            pi = pi,\n            ecc = if (isActive) activeEcc.ifBlank { preset.ecc } else preset.ecc,\n            size = 56.dp,\n            allFrequencies =\n                FytPhysicalRadio.presetFrequencies(preset) +\n                    if (isActive) activeAlternativeFrequencies else emptyList(),\n        )",
    "favourite artwork",
)
screen = replace_once(
    screen,
    "ecc = preset.ecc,\n                    size = 72.dp,",
    "ecc = preset.ecc,\n                    size = 72.dp,\n                    allFrequencies = FytPhysicalRadio.presetFrequencies(preset),",
    "editor artwork",
)
screen = replace_once(
    screen,
    "ecc = result.ecc,\n            size = 54.dp,",
    "ecc = result.ecc,\n            size = 54.dp,\n            allFrequencies = FytPhysicalRadio.scanFrequencies(result),",
    "scan artwork",
)
screen = replace_once(
    screen,
    "ecc = state.ecc,\n                    size = 82.dp,",
    "ecc = state.ecc,\n                    size = 82.dp,\n                    allFrequencies = listOf(state.frequency) + state.alternativeFrequencies,",
    "manual artwork",
)
write(screen_path, screen)


# Large player artwork ------------------------------------------------------
player_path = "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt"
player = read(player_path)
player = replace_once(
    player,
    "ecc = state.ecc,\n                    size = artworkSize,",
    "ecc = state.ecc,\n                    size = artworkSize,\n                    allFrequencies =\n                        (currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty() +\n                            state.alternativeFrequencies + state.frequency),",
    "player artwork frequencies",
)
write(player_path, player)


# Verification --------------------------------------------------------------
checks = {
    build_path: ['versionCode = 1370026', 'versionName = "13.7.17"'],
    artwork_path: ['ReliableFmStationLogoResolver.revisions', 'allFrequencies: List<Float> = emptyList()'],
    picker_path: ['ReliableFmStationLogoResolver.searchCandidates', 'allFrequencies = FytPhysicalRadio.presetFrequencies(preset)'],
    diag_path: ['ReliableFmStationLogoResolver.logoInfo'],
    screen_path: ['activeAlternativeFrequencies: List<Float>', 'FytPhysicalRadio.scanFrequencies(result)'],
    player_path: ['currentPreset?.let(FytPhysicalRadio::presetFrequencies)'],
}
for path, markers in checks.items():
    text = read(path)
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"{path}: missing marker {marker}")

print("Applied reliable FM logo integration for Dudu7 13.7.17")
