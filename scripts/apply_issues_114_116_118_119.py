from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def p(rel): return ROOT / rel

def replace_once(path, old, new):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected one occurrence, found {count}: {old[:120]!r}')
    path.write_text(text.replace(old, new, 1))

def replace_range(path, start_marker, end_marker, new):
    text = path.read_text()
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f'{path}: start marker not found: {start_marker[:120]!r}')
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f'{path}: end marker not found: {end_marker[:120]!r}')
    path.write_text(text[:start] + new + text[end:])

# Version
build = p('app/build.gradle.kts')
text = build.read_text().replace('versionCode = 1370069', 'versionCode = 1370070').replace('versionName = "13.7.60"', 'versionName = "13.7.61"')
build.write_text(text)

# Preference key for FM grid/list parity
prefs = p('app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt')
replace_once(prefs, 'val WebRadioViewTypeKey = stringPreferencesKey("webRadioViewType")\n', 'val WebRadioViewTypeKey = stringPreferencesKey("webRadioViewType")\nval FmRadioViewTypeKey = stringPreferencesKey("fmRadioViewType")\n')

# Finer slider steps
appearance = p('app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt')
replace_once(
    appearance,
    '''                                    valueRange = 0f..200f,\n                                    steps = 19,\n                                    modifier = Modifier.fillMaxWidth(0.42f),\n''',
    '''                                    valueRange = 0f..200f,\n                                    steps = 199,\n                                    modifier = Modifier.fillMaxWidth(0.42f),\n''',
)
replace_once(
    appearance,
    '''                                        valueRange = 0f..24f,\n                                        steps = 11,\n                                        modifier = Modifier.fillMaxWidth(0.42f),\n''',
    '''                                        valueRange = 0f..24f,\n                                        steps = 23,\n                                        modifier = Modifier.fillMaxWidth(0.42f),\n''',
)

# Preserve the best available station logo up to a safe 1600 px cap instead of always reducing to 512 px.
logo_cache = p('app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoCache.kt')
replace_once(
    logo_cache,
    ''' * selected logo becomes a new local 512 x 512 PNG URI, so Coil cannot keep\n * displaying an older bitmap under the same file-cache key.\n''',
    ''' * selected logo becomes a versioned local square PNG URI. Source detail is preserved\n * up to 1600 px so the full-screen Dudu7 background does not reuse a 512 px list thumbnail.\n''',
)
replace_once(
    logo_cache,
    '''    private const val TARGET_SIZE = 512\n    private const val MIN_SOURCE_SIZE = 24\n''',
    '''    private const val MIN_TARGET_SIZE = 512\n    private const val MAX_TARGET_SIZE = 1600\n    private const val MIN_SOURCE_SIZE = 24\n''',
)
replace_once(
    logo_cache,
    '''                    .size(TARGET_SIZE, TARGET_SIZE)\n''',
    '''                    .size(MAX_TARGET_SIZE, MAX_TARGET_SIZE)\n''',
)
replace_once(
    logo_cache,
    '''            val square = Bitmap.createBitmap(TARGET_SIZE, TARGET_SIZE, Bitmap.Config.ARGB_8888)\n            val canvas = Canvas(square)\n            canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)\n            val scale = min(TARGET_SIZE.toFloat() / decoded.width, TARGET_SIZE.toFloat() / decoded.height)\n            val width = decoded.width * scale\n            val height = decoded.height * scale\n            val left = (TARGET_SIZE - width) / 2f\n            val top = (TARGET_SIZE - height) / 2f\n''',
    '''            val targetSize =\n                maxOf(decoded.width, decoded.height).coerceIn(MIN_TARGET_SIZE, MAX_TARGET_SIZE)\n            val square = Bitmap.createBitmap(targetSize, targetSize, Bitmap.Config.ARGB_8888)\n            val canvas = Canvas(square)\n            canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)\n            val scale = min(targetSize.toFloat() / decoded.width, targetSize.toFloat() / decoded.height)\n            val width = decoded.width * scale\n            val height = decoded.height * scale\n            val left = (targetSize - width) / 2f\n            val top = (targetSize - height) / 2f\n''',
)

# Explicit radio track artwork state: overlay only for a real recognized/resolved title cover.
connection = p('app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt')
replace_once(
    connection,
    '''    /** True only when the stream or manual recognition supplied artist + title. */\n    val radioHasTrackMetadata = MutableStateFlow(false)\n''',
    '''    /** True only when the stream or manual recognition supplied artist + title. */\n    val radioHasTrackMetadata = MutableStateFlow(false)\n    /** True only when the current WebRadio metadata has a real title artwork, not the station logo fallback. */\n    val radioHasTrackArtwork = MutableStateFlow(false)\n''',
)
replace_once(
    connection,
    '''        radioResolvedSong.value = null\n        radioHasTrackMetadata.value = false\n        mediaMetadata.value = withStoredRadioArtwork(mediaItem?.metadata)\n''',
    '''        radioResolvedSong.value = null\n        radioHasTrackMetadata.value = false\n        radioHasTrackArtwork.value = false\n        mediaMetadata.value = withStoredRadioArtwork(mediaItem?.metadata)\n''',
)
replace_once(
    connection,
    '''        mediaMetadata.value = dynamic\n\n        val artist = parsed.first\n''',
    '''        mediaMetadata.value = dynamic\n        radioHasTrackArtwork.value = false\n\n        val artist = parsed.first\n''',
)
replace_once(
    connection,
    '''        radioHasTrackMetadata.value = result.artist.isNotBlank() && result.title.isNotBlank()\n        if (radioHasTrackMetadata.value) {\n''',
    '''        radioHasTrackMetadata.value = result.artist.isNotBlank() && result.title.isNotBlank()\n        radioHasTrackArtwork.value = !preferredCover.isNullOrBlank()\n        if (radioHasTrackMetadata.value) {\n''',
)
replace_once(
    connection,
    '''        val key = "${normalizeRadioTrackText(artist)}|${normalizeRadioTrackText(title)}"\n        if (radioSongCache.containsKey(key)) {\n''',
    '''        val key = "${normalizeRadioTrackText(artist)}|${normalizeRadioTrackText(title)}"\n        radioHasTrackArtwork.value = !preferredCover.isNullOrBlank()\n        if (radioSongCache.containsKey(key)) {\n''',
)
replace_once(
    connection,
    '''        radioResolvedSong.value = song\n        val cover = preferredCover ?: song?.thumbnail?.resize(1200, 1200)\n        if (song != null) {\n''',
    '''        radioResolvedSong.value = song\n        val cover = preferredCover ?: song?.thumbnail?.resize(1200, 1200)\n        radioHasTrackArtwork.value = !cover.isNullOrBlank()\n        if (song != null) {\n''',
)

# Thumbnail receives explicit overlay state instead of guessing from unequal URLs.
thumb = p('app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt')
replace_once(
    thumb,
    '''    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n) {\n''',
    '''    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n    showRadioStationLogoOverlay: Boolean = false,\n) {\n''',
)
replace_once(
    thumb,
    '''                                currentMediaId = mediaMetadata?.id,\n                                currentMediaThumbnail = mediaMetadata?.thumbnailUrl\n''',
    '''                                currentMediaId = mediaMetadata?.id,\n                                currentMediaThumbnail = mediaMetadata?.thumbnailUrl,\n                                showRadioStationLogoOverlay = showRadioStationLogoOverlay,\n''',
)
replace_once(
    thumb,
    '''    currentMediaId: String? = null,\n    currentMediaThumbnail: String? = null,\n    modifier: Modifier = Modifier,\n''',
    '''    currentMediaId: String? = null,\n    currentMediaThumbnail: String? = null,\n    showRadioStationLogoOverlay: Boolean = false,\n    modifier: Modifier = Modifier,\n''',
)
replace_once(
    thumb,
    '''                val showStationLogoOverlay =\n                    VehicleVariantConfig.isDudu7 &&\n                        isLandscape &&\n                        com.metrolist.music.radio.isRadioMediaId(item.mediaId) &&\n                        item.mediaId == currentMediaId &&\n                        !currentMediaThumbnail.isNullOrBlank() &&\n                        !stableRadioArtwork.isNullOrBlank() &&\n                        currentMediaThumbnail != stableRadioArtwork\n''',
    '''                val showStationLogoOverlay =\n                    showRadioStationLogoOverlay &&\n                        VehicleVariantConfig.isDudu7 &&\n                        isLandscape &&\n                        com.metrolist.music.radio.isRadioMediaId(item.mediaId) &&\n                        item.mediaId == currentMediaId &&\n                        !currentMediaThumbnail.isNullOrBlank() &&\n                        !stableRadioArtwork.isNullOrBlank()\n''',
)

# FM overlay follows actual recognized track state.
fm_player = p('app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt')
replace_once(
    fm_player,
    '''    val resolvedSong = nowPlaying.resolvedSong\n''',
    '''    val resolvedSong = nowPlaying.resolvedSong\n    val hasRecognizedTrackArtwork = nowPlaying.hasTrackMetadata && !nowPlaying.coverUrl.isNullOrBlank()\n''',
)
replace_once(fm_player, '''            if (!nowPlaying.coverUrl.isNullOrBlank()) {\n''', '''            if (hasRecognizedTrackArtwork) {\n''')

# High-resolution background URL normalization and explicit overlay state.
player = p('app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt')
replace_once(
    player,
    '''private data class Dudu7FmVisualSnapshot(\n    val active: Boolean = false,\n    val identity: String = "",\n    val artworkUrl: String? = null,\n)\n\n''',
    '''private data class Dudu7FmVisualSnapshot(\n    val active: Boolean = false,\n    val identity: String = "",\n    val artworkUrl: String? = null,\n)\n\nprivate fun dudu7HighResolutionArtworkUrl(value: String?): String? {\n    val url = value?.trim()?.takeIf { it.isNotBlank() } ?: return null\n    if (url.startsWith("file:", ignoreCase = true) || url.startsWith("content:", ignoreCase = true)) return url\n    return when {\n        "googleusercontent.com" in url || "ytimg.com" in url ->\n            url\n                .replace(Regex("=w\\\\d+-h\\\\d+[^?]*"), "=w1600-h1600-l90-rj")\n                .replace(Regex("=s\\\\d+[^?]*"), "=s1600-c-k-c0x00ffffff-no-rj")\n        "mzstatic.com" in url -> url.replace(Regex("/\\\\d+x\\\\d+bb\\\\."), "/1600x1600bb.")\n        else -> url\n    }\n}\n\n''',
)
replace_once(
    player,
    '''    val effectiveArtworkFallbackUrl =\n        if (isWebRadio) {\n            currentRadioStation?.favicon?.takeIf { it.isNotBlank() && it != effectiveArtworkUrl }\n        } else {\n            null\n        }\n''',
    '''    val effectiveArtworkFallbackUrl =\n        if (isWebRadio) {\n            currentRadioStation?.favicon?.takeIf { it.isNotBlank() && it != effectiveArtworkUrl }\n        } else {\n            null\n        }\n    val effectiveBackgroundArtworkUrl =\n        if (VehicleVariantConfig.isDudu7) dudu7HighResolutionArtworkUrl(effectiveArtworkUrl) else effectiveArtworkUrl\n    val effectiveBackgroundFallbackUrl =\n        if (VehicleVariantConfig.isDudu7) dudu7HighResolutionArtworkUrl(effectiveArtworkFallbackUrl) else effectiveArtworkFallbackUrl\n''',
)
replace_once(
    player,
    '''    val radioHasTrackMetadata by playerConnection.radioHasTrackMetadata.collectAsStateWithLifecycle()\n''',
    '''    val radioHasTrackMetadata by playerConnection.radioHasTrackMetadata.collectAsStateWithLifecycle()\n    val radioHasTrackArtwork by playerConnection.radioHasTrackArtwork.collectAsStateWithLifecycle()\n''',
)
replace_once(
    player,
    '''    val visualArtworkKey = "${effectiveVisualId.orEmpty()}|${effectiveArtworkUrl.orEmpty()}|${effectiveArtworkFallbackUrl.orEmpty()}"\n''',
    '''    val visualArtworkKey =\n        "${effectiveVisualId.orEmpty()}|${effectiveBackgroundArtworkUrl.orEmpty()}|${effectiveBackgroundFallbackUrl.orEmpty()}"\n''',
)
replace_once(
    player,
    '''        val artworkCandidates = listOfNotNull(effectiveArtworkUrl?.takeIf { it.isNotBlank() }, effectiveArtworkFallbackUrl).distinct()\n''',
    '''        val artworkCandidates =\n            listOfNotNull(\n                effectiveBackgroundArtworkUrl?.takeIf { it.isNotBlank() },\n                effectiveBackgroundFallbackUrl?.takeIf { it.isNotBlank() },\n            ).distinct()\n''',
)
replace_once(
    player,
    '''                            targetState = effectiveArtworkUrl to effectiveArtworkFallbackUrl,\n''',
    '''                            targetState = effectiveBackgroundArtworkUrl to effectiveBackgroundFallbackUrl,\n''',
)
replace_once(
    player,
    '''                                                    .data(fallbackUrl)\n                                                    .size(100, 100)\n                                                    .allowHardware(false)\n''',
    '''                                                    .data(fallbackUrl)\n                                                    .allowHardware(false)\n''',
)
replace_once(
    player,
    '''                                                    .data(thumbnailUrl)\n                                                    .size(100, 100)\n                                                    .allowHardware(false)\n''',
    '''                                                    .data(thumbnailUrl)\n                                                    .allowHardware(false)\n''',
)
replace_once(
    player,
    '''                    onPhysicalRadioVisualChanged = { active, identity, artworkUrl ->\n''',
    '''                    backdropArtworkUrl = effectiveBackgroundArtworkUrl,\n                    backdropFallbackUrl = effectiveBackgroundFallbackUrl,\n                    backdropUsesArtwork = playerBackground == PlayerBackgroundStyle.BLUR,\n                    backdropUsesGradient = playerBackground == PlayerBackgroundStyle.GRADIENT,\n                    backdropGradientColors = gradientColors,\n                    onPhysicalRadioVisualChanged = { active, identity, artworkUrl ->\n''',
)
replace_once(
    player,
    '''                                    isLandscape = true,\n                                    landscapeHorizontalPadding = 2.dp,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n                                )\n''',
    '''                                    isLandscape = true,\n                                    landscapeHorizontalPadding = 2.dp,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n                                    showRadioStationLogoOverlay = isWebRadio && radioHasTrackArtwork,\n                                )\n''',
)

# Vehicle layout: one real backdrop layer aligned to the Dudu7 root and visible through the glass pane.
layout = p('app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt')
text = layout.read_text()
text = text.replace('import androidx.compose.foundation.layout.height\n', 'import androidx.compose.foundation.layout.height\nimport androidx.compose.foundation.layout.offset\nimport androidx.compose.foundation.layout.requiredSize\n')
text = text.replace('import androidx.compose.ui.graphics.Color\n', 'import androidx.compose.ui.graphics.Brush\nimport androidx.compose.ui.graphics.Color\n')
text = text.replace('import androidx.compose.ui.unit.dp\n', 'import androidx.compose.ui.unit.IntOffset\nimport androidx.compose.ui.unit.IntSize\nimport androidx.compose.ui.unit.dp\n')
text = text.replace('import androidx.lifecycle.compose.collectAsStateWithLifecycle\n', 'import androidx.lifecycle.compose.collectAsStateWithLifecycle\nimport coil3.compose.AsyncImage\n')
layout.write_text(text)
replace_once(
    layout,
    '''@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout(\n''',
    '''@Composable\nprivate fun GlassBackdropLayer(\n    artworkUrl: String?,\n    fallbackUrl: String?,\n    usesArtwork: Boolean,\n    usesGradient: Boolean,\n    gradientColors: List<Color>,\n    rootSize: IntSize,\n    paneOffset: IntOffset,\n    blurRadius: androidx.compose.ui.unit.Dp,\n    shape: RoundedCornerShape,\n    baseColor: Color,\n    modifier: Modifier = Modifier,\n) {\n    if (rootSize.width <= 0 || rootSize.height <= 0 || blurRadius <= 0.dp) return\n    val density = LocalDensity.current\n    val rootWidth = with(density) { rootSize.width.toDp() }\n    val rootHeight = with(density) { rootSize.height.toDp() }\n    Box(modifier = modifier.clip(shape)) {\n        Box(\n            modifier =\n                Modifier\n                    .requiredSize(rootWidth, rootHeight)\n                    .offset { IntOffset(-paneOffset.x, -paneOffset.y) }\n                    .blur(blurRadius),\n        ) {\n            when {\n                usesArtwork -> {\n                    if (!fallbackUrl.isNullOrBlank()) {\n                        AsyncImage(\n                            model = fallbackUrl,\n                            contentDescription = null,\n                            contentScale = ContentScale.Crop,\n                            modifier = Modifier.fillMaxSize(),\n                        )\n                    }\n                    if (!artworkUrl.isNullOrBlank()) {\n                        AsyncImage(\n                            model = artworkUrl,\n                            contentDescription = null,\n                            contentScale = ContentScale.Crop,\n                            modifier = Modifier.fillMaxSize(),\n                        )\n                    }\n                    Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.30f)))\n                }\n                usesGradient && gradientColors.isNotEmpty() -> {\n                    val colors =\n                        if (gradientColors.size >= 3) gradientColors.take(3)\n                        else listOf(gradientColors.first(), gradientColors.first().copy(alpha = 0.7f), Color.Black)\n                    Box(\n                        Modifier\n                            .fillMaxSize()\n                            .background(Brush.verticalGradient(colors))\n                            .background(Color.Black.copy(alpha = 0.20f)),\n                    )\n                }\n                else -> Box(Modifier.fillMaxSize().background(baseColor))\n            }\n        }\n    }\n}\n\n@OptIn(ExperimentalMaterial3Api::class)\n@Composable\nfun VehicleLandscapeLayout(\n''',
)
replace_once(
    layout,
    '''    playerPlayButtonContentColor: Color,\n    playerSideButtonContentColor: Color,\n    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,\n''',
    '''    playerPlayButtonContentColor: Color,\n    playerSideButtonContentColor: Color,\n    backdropArtworkUrl: String?,\n    backdropFallbackUrl: String?,\n    backdropUsesArtwork: Boolean,\n    backdropUsesGradient: Boolean,\n    backdropGradientColors: List<Color>,\n    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,\n''',
)
replace_once(
    layout,
    '''    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }\n''',
    '''    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }\n    var layoutOriginInRoot by remember { mutableStateOf(Offset.Zero) }\n    var layoutSize by remember { mutableStateOf(IntSize.Zero) }\n    var glassPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }\n''',
)
replace_once(
    layout,
    '''    Box(\n        modifier = Modifier.fillMaxSize().clipToBounds(),\n    ) {\n''',
    '''    Box(\n        modifier =\n            Modifier\n                .fillMaxSize()\n                .clipToBounds()\n                .onGloballyPositioned { coordinates ->\n                    layoutOriginInRoot = coordinates.positionInRoot()\n                    layoutSize = coordinates.size\n                },\n    ) {\n''',
)
replace_once(
    layout,
    '''                color = if (frostedIceEnabled) frostedColors.surfaceContainer else baseColors.surfaceContainer,\n''',
    '''                color = if (frostedIceEnabled) Color.Transparent else baseColors.surfaceContainer,\n''',
)
replace_once(
    layout,
    '''                        .fillMaxSize()\n                        .padding(horizontal = 8.dp, vertical = 4.dp),\n''',
    '''                        .fillMaxSize()\n                        .padding(horizontal = 8.dp, vertical = 4.dp)\n                        .onGloballyPositioned { coordinates ->\n                            glassPaneOriginInRoot = coordinates.positionInRoot()\n                        },\n''',
)
replace_once(
    layout,
    '''                    if (frostedIceEnabled && frostedBlurStrength > 0 && glassAlpha > 0f) {\n                        Box(\n                            Modifier\n                                .fillMaxSize()\n                                .clip(glassShape)\n                                .background(baseColors.surface.copy(alpha = glassAlpha * 0.45f))\n                                .blur(glassBlur),\n                        )\n                    }\n''',
    '''                    if (frostedIceEnabled && frostedBlurStrength > 0) {\n                        val relativePaneOffset = glassPaneOriginInRoot - layoutOriginInRoot\n                        GlassBackdropLayer(\n                            artworkUrl = backdropArtworkUrl,\n                            fallbackUrl = backdropFallbackUrl,\n                            usesArtwork = backdropUsesArtwork,\n                            usesGradient = backdropUsesGradient,\n                            gradientColors = backdropGradientColors,\n                            rootSize = layoutSize,\n                            paneOffset =\n                                IntOffset(\n                                    relativePaneOffset.x.toInt(),\n                                    relativePaneOffset.y.toInt(),\n                                ),\n                            blurRadius = glassBlur,\n                            shape = glassShape,\n                            baseColor = baseColors.surface,\n                            modifier = Modifier.fillMaxSize(),\n                        )\n                    }\n                    if (frostedIceEnabled && glassAlpha > 0f) {\n                        Box(\n                            Modifier\n                                .fillMaxSize()\n                                .clip(glassShape)\n                                .background(frostedColors.surfaceContainer),\n                        )\n                    }\n''',
)

# WebRadio grid menu in the lower-left corner.
web = p('app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt')
replace_once(
    web,
    '''            Box(contentAlignment = Alignment.TopEnd) {\n                RadioStationArtwork(station, 88, Modifier, onLogoResolved)\n                if (isSaved) {\n                    Box(modifier = Modifier.align(Alignment.TopEnd)) {\n                        RadioStationActionMenu(onEdit = onEdit, onDelete = onDelete)\n                    }\n                } else {\n''',
    '''            Box(contentAlignment = Alignment.TopEnd) {\n                RadioStationArtwork(station, 88, Modifier, onLogoResolved)\n                if (!isSaved) {\n''',
)
replace_once(
    web,
    '''        if (isSaved) {\n            Box(\n                modifier =\n                    Modifier\n                        .align(Alignment.BottomEnd)\n                        .padding(end = 2.dp, bottom = 2.dp),\n            ) {\n                dragHandle()\n            }\n        }\n''',
    '''        if (isSaved) {\n            Box(\n                modifier =\n                    Modifier\n                        .align(Alignment.BottomStart)\n                        .padding(start = 2.dp, bottom = 2.dp),\n            ) {\n                RadioStationActionMenu(onEdit = onEdit, onDelete = onDelete)\n            }\n            Box(\n                modifier =\n                    Modifier\n                        .align(Alignment.BottomEnd)\n                        .padding(end = 2.dp, bottom = 2.dp),\n            ) {\n                dragHandle()\n            }\n        }\n''',
)

# FM adds the same list/grid preference and lower-left card action menu.
fm = p('app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt')
text = fm.read_text()
text = text.replace('import androidx.compose.foundation.layout.Arrangement\n', 'import androidx.compose.foundation.layout.Arrangement\nimport androidx.compose.foundation.layout.aspectRatio\n')
text = text.replace('import androidx.compose.foundation.lazy.rememberLazyListState\n', 'import androidx.compose.foundation.lazy.rememberLazyListState\nimport androidx.compose.foundation.lazy.grid.GridCells\nimport androidx.compose.foundation.lazy.grid.LazyVerticalGrid\nimport androidx.compose.foundation.lazy.grid.itemsIndexed as gridItemsIndexed\nimport androidx.compose.foundation.lazy.grid.rememberLazyGridState\n')
text = text.replace('import com.metrolist.music.R\n', 'import com.metrolist.music.R\nimport com.metrolist.music.constants.FmRadioViewTypeKey\nimport com.metrolist.music.constants.LibraryViewType\n')
text = text.replace('import com.metrolist.music.radio.fyt.FytPhysicalRadio\n', 'import com.metrolist.music.radio.fyt.FytPhysicalRadio\nimport com.metrolist.music.utils.rememberEnumPreference\n')
text = text.replace('import sh.calvin.reorderable.ReorderableItem\n', 'import sh.calvin.reorderable.ReorderableItem\nimport sh.calvin.reorderable.rememberReorderableLazyGridState\n')
fm.write_text(text)
replace_once(fm, '''    var section by remember { mutableStateOf(PhysicalRadioSection.FAVOURITES) }\n''', '''    var section by remember { mutableStateOf(PhysicalRadioSection.FAVOURITES) }\n    var viewType by rememberEnumPreference(FmRadioViewTypeKey, LibraryViewType.LIST)\n''')
replace_once(
    fm,
    '''    val orderedPresets = remember { mutableStateListOf<FytPhysicalRadio.Preset>() }\n    val listState = rememberLazyListState()\n    val reorderState =\n        rememberReorderableLazyListState(listState) { from, to ->\n            if (from.index in orderedPresets.indices && to.index in orderedPresets.indices) {\n                orderedPresets.move(from.index, to.index)\n            }\n        }\n    val isDragging = reorderState.isAnyItemDragging\n''',
    '''    val orderedPresets = remember { mutableStateListOf<FytPhysicalRadio.Preset>() }\n    val listState = rememberLazyListState()\n    val gridState = rememberLazyGridState()\n    val reorderState =\n        rememberReorderableLazyListState(listState) { from, to ->\n            if (from.index in orderedPresets.indices && to.index in orderedPresets.indices) {\n                orderedPresets.move(from.index, to.index)\n            }\n        }\n    val gridReorderState =\n        rememberReorderableLazyGridState(gridState) { from, to ->\n            if (from.index in orderedPresets.indices && to.index in orderedPresets.indices) {\n                orderedPresets.move(from.index, to.index)\n            }\n        }\n    val isDragging = reorderState.isAnyItemDragging || gridReorderState.isAnyItemDragging\n''',
)
replace_once(
    fm,
    '''            if (state.isBusy && !state.isScanning) {\n                item { CircularProgressIndicator(Modifier.size(28.dp)) }\n            }\n''',
    '''            if (section == PhysicalRadioSection.FAVOURITES) {\n                item {\n                    IconButton(onClick = { viewType = viewType.toggle() }) {\n                        Icon(\n                            painter =\n                                painterResource(\n                                    if (viewType == LibraryViewType.LIST) R.drawable.grid_view else R.drawable.list,\n                                ),\n                            contentDescription =\n                                if (viewType == LibraryViewType.LIST) "Kachelansicht" else "Listenansicht",\n                        )\n                    }\n                }\n            }\n            if (state.isBusy && !state.isScanning) {\n                item { CircularProgressIndicator(Modifier.size(28.dp)) }\n            }\n''',
)
old = '''                if (orderedPresets.isEmpty()) {\n                    EmptyFmFavourites(onOpenSearch = { section = PhysicalRadioSection.SCAN })\n                } else {\n                    LazyColumn(\n                        state = listState,\n                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),\n                        modifier = Modifier.fillMaxSize(),\n                    ) {\n                        itemsIndexed(\n                            items = orderedPresets,\n                            key = { _, preset -> FytPhysicalRadio.stablePresetKey(preset) },\n                        ) { _, preset ->\n                            ReorderableItem(reorderState, key = FytPhysicalRadio.stablePresetKey(preset)) {\n                                val isActive = state.isActive && state.currentPreset?.id == preset.id\n                                FmFavouriteRow(\n                                    preset = preset,\n                                    pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    activeFrequency = state.frequency,\n                                    activeEcc = state.ecc,\n                                    isActive = isActive,\n                                    onPlay = {\n                                        if (!isActive) {\n                                            playerConnection?.pause()\n                                            radio.tunePreset(preset)\n                                        }\n                                    },\n                                    onNextAf = {\n                                        if (isActive) {\n                                            radio.tuneNextAlternativeFrequency(preset)\n                                            Toast.makeText(context, "Alternative Frequenz wird geprüft", Toast.LENGTH_SHORT).show()\n                                        }\n                                    },\n                                    onEdit = { editingPreset = preset },\n                                    onDelete = { deletingPreset = preset },\n                                    dragHandle = {\n                                        IconButton(\n                                            onClick = {},\n                                            modifier =\n                                                Modifier\n                                                    .draggableHandle(\n                                                        onDragStarted = {\n                                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)\n                                                        },\n                                                    ),\n                                        ) {\n                                            Icon(\n                                                painter = painterResource(R.drawable.drag_handle),\n                                                contentDescription = "Sender verschieben",\n                                            )\n                                        }\n                                    },\n                                )\n                            }\n                        }\n                    }\n                }\n'''
new = '''                if (orderedPresets.isEmpty()) {\n                    EmptyFmFavourites(onOpenSearch = { section = PhysicalRadioSection.SCAN })\n                } else if (viewType == LibraryViewType.LIST) {\n                    LazyColumn(\n                        state = listState,\n                        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp),\n                        modifier = Modifier.fillMaxSize(),\n                    ) {\n                        itemsIndexed(\n                            items = orderedPresets,\n                            key = { _, preset -> FytPhysicalRadio.stablePresetKey(preset) },\n                        ) { _, preset ->\n                            ReorderableItem(reorderState, key = FytPhysicalRadio.stablePresetKey(preset)) {\n                                val isActive = state.isActive && state.currentPreset?.id == preset.id\n                                FmFavouriteRow(\n                                    preset = preset,\n                                    pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    activeFrequency = state.frequency,\n                                    activeEcc = state.ecc,\n                                    isActive = isActive,\n                                    onPlay = {\n                                        if (!isActive) {\n                                            playerConnection?.pause()\n                                            radio.tunePreset(preset)\n                                        }\n                                    },\n                                    onNextAf = {\n                                        if (isActive) {\n                                            radio.tuneNextAlternativeFrequency(preset)\n                                            Toast.makeText(context, "Alternative Frequenz wird geprüft", Toast.LENGTH_SHORT).show()\n                                        }\n                                    },\n                                    onEdit = { editingPreset = preset },\n                                    onDelete = { deletingPreset = preset },\n                                    dragHandle = {\n                                        IconButton(\n                                            onClick = {},\n                                            modifier =\n                                                Modifier\n                                                    .draggableHandle(\n                                                        onDragStarted = {\n                                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)\n                                                        },\n                                                    ),\n                                        ) {\n                                            Icon(\n                                                painter = painterResource(R.drawable.drag_handle),\n                                                contentDescription = "Sender verschieben",\n                                            )\n                                        }\n                                    },\n                                )\n                            }\n                        }\n                    }\n                } else {\n                    LazyVerticalGrid(\n                        state = gridState,\n                        columns = GridCells.Adaptive(142.dp),\n                        contentPadding = PaddingValues(horizontal = 10.dp, vertical = 6.dp),\n                        horizontalArrangement = Arrangement.spacedBy(8.dp),\n                        verticalArrangement = Arrangement.spacedBy(8.dp),\n                        modifier = Modifier.fillMaxSize(),\n                    ) {\n                        gridItemsIndexed(\n                            items = orderedPresets,\n                            key = { _, preset -> FytPhysicalRadio.stablePresetKey(preset) },\n                        ) { _, preset ->\n                            ReorderableItem(gridReorderState, key = FytPhysicalRadio.stablePresetKey(preset)) {\n                                val isActive = state.isActive && state.currentPreset?.id == preset.id\n                                FmFavouriteCard(\n                                    preset = preset,\n                                    pi = if (isActive && state.pi > 0) state.pi else preset.pi,\n                                    activeFrequency = state.frequency,\n                                    activeEcc = state.ecc,\n                                    isActive = isActive,\n                                    onPlay = {\n                                        if (!isActive) {\n                                            playerConnection?.pause()\n                                            radio.tunePreset(preset)\n                                        }\n                                    },\n                                    onNextAf = {\n                                        if (isActive) {\n                                            radio.tuneNextAlternativeFrequency(preset)\n                                            Toast.makeText(context, "Alternative Frequenz wird geprüft", Toast.LENGTH_SHORT).show()\n                                        }\n                                    },\n                                    onEdit = { editingPreset = preset },\n                                    onDelete = { deletingPreset = preset },\n                                    dragHandle = {\n                                        IconButton(\n                                            onClick = {},\n                                            modifier =\n                                                Modifier\n                                                    .draggableHandle(\n                                                        onDragStarted = {\n                                                            haptic.performHapticFeedback(HapticFeedbackType.LongPress)\n                                                        },\n                                                    ).size(42.dp),\n                                        ) {\n                                            Icon(\n                                                painter = painterResource(R.drawable.drag_indicator_grid),\n                                                contentDescription = "Sender verschieben",\n                                            )\n                                        }\n                                    },\n                                )\n                            }\n                        }\n                    }\n                }\n'''
replace_range(
    fm,
    """                if (orderedPresets.isEmpty()) {""",
    """            }

            PhysicalRadioSection.SCAN ->""",
    new,
)
start = '''        var menuExpanded by remember(preset.id) { mutableStateOf(false) }\n        Box {\n            IconButton(onClick = { menuExpanded = true }) {\n                Icon(painterResource(R.drawable.more_vert), contentDescription = "Senderaktionen")\n            }\n            DropdownMenu(\n                expanded = menuExpanded,\n                onDismissRequest = { menuExpanded = false },\n            ) {\n                DropdownMenuItem(\n                    text = { Text("Bearbeiten") },\n                    leadingIcon = { Icon(painterResource(R.drawable.edit), contentDescription = null) },\n                    onClick = {\n                        menuExpanded = false\n                        onEdit()\n                    },\n                )\n                DropdownMenuItem(\n                    text = { Text("Löschen", color = MaterialTheme.colorScheme.error) },\n                    leadingIcon = {\n                        Icon(\n                            painterResource(R.drawable.delete),\n                            contentDescription = null,\n                            tint = MaterialTheme.colorScheme.error,\n                        )\n                    },\n                    onClick = {\n                        menuExpanded = false\n                        onDelete()\n                    },\n                )\n            }\n        }\n'''
replace_once(fm, start, '''        FmStationActionMenu(\n            menuKey = FytPhysicalRadio.stablePresetKey(preset),\n            onEdit = onEdit,\n            onDelete = onDelete,\n        )\n''')
replace_once(
    fm,
    '''@Composable\nprivate fun FmAutoScanPanel(\n''',
    '''@OptIn(ExperimentalFoundationApi::class)\n@Composable\nprivate fun FmFavouriteCard(\n    preset: FytPhysicalRadio.Preset,\n    pi: Int,\n    activeFrequency: Float,\n    activeEcc: String,\n    isActive: Boolean,\n    onPlay: () -> Unit,\n    onNextAf: () -> Unit,\n    onEdit: () -> Unit,\n    onDelete: () -> Unit,\n    dragHandle: @Composable () -> Unit,\n) {\n    Box(\n        modifier =\n            Modifier\n                .fillMaxWidth()\n                .aspectRatio(0.86f)\n                .clip(RoundedCornerShape(14.dp))\n                .background(\n                    if (isActive) MaterialTheme.colorScheme.primaryContainer\n                    else MaterialTheme.colorScheme.surfaceContainer,\n                )\n                .combinedClickable(onClick = onPlay, onDoubleClick = onNextAf),\n    ) {\n        Column(\n            horizontalAlignment = Alignment.CenterHorizontally,\n            modifier = Modifier.fillMaxSize().padding(start = 10.dp, top = 10.dp, end = 10.dp, bottom = 44.dp),\n        ) {\n            FmStationArtwork(\n                stationName = preset.name,\n                frequency = if (isActive) activeFrequency else preset.frequency,\n                pi = pi,\n                ecc = if (isActive) activeEcc.ifBlank { preset.ecc } else preset.ecc,\n                size = 88.dp,\n                allFrequencies = listOf(if (isActive) activeFrequency else preset.frequency),\n            )\n            Spacer(Modifier.height(8.dp))\n            Text(\n                text = preset.name,\n                style = MaterialTheme.typography.titleSmall,\n                fontWeight = FontWeight.SemiBold,\n                maxLines = 2,\n                overflow = TextOverflow.Ellipsis,\n            )\n            Text(\n                text = "${FytPhysicalRadio.formatFrequency(if (isActive) activeFrequency else preset.frequency)} MHz",\n                style = MaterialTheme.typography.bodySmall,\n                color = MaterialTheme.colorScheme.onSurfaceVariant,\n                maxLines = 1,\n            )\n            if (isActive) {\n                Text(\n                    text = "● LÄUFT",\n                    style = MaterialTheme.typography.labelSmall,\n                    fontWeight = FontWeight.Bold,\n                    color = MaterialTheme.colorScheme.primary,\n                )\n            }\n        }\n        FmStationActionMenu(\n            menuKey = FytPhysicalRadio.stablePresetKey(preset),\n            onEdit = onEdit,\n            onDelete = onDelete,\n            modifier = Modifier.align(Alignment.BottomStart).padding(start = 2.dp, bottom = 2.dp),\n        )\n        Box(Modifier.align(Alignment.BottomEnd).padding(end = 2.dp, bottom = 2.dp)) { dragHandle() }\n    }\n}\n\n@Composable\nprivate fun FmStationActionMenu(\n    menuKey: String,\n    onEdit: () -> Unit,\n    onDelete: () -> Unit,\n    modifier: Modifier = Modifier,\n) {\n    var menuExpanded by remember(menuKey) { mutableStateOf(false) }\n    Box(modifier) {\n        IconButton(onClick = { menuExpanded = true }, modifier = Modifier.size(42.dp)) {\n            Icon(painterResource(R.drawable.more_vert), contentDescription = "Senderaktionen")\n        }\n        DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {\n            DropdownMenuItem(\n                text = { Text("Bearbeiten") },\n                leadingIcon = { Icon(painterResource(R.drawable.edit), contentDescription = null) },\n                onClick = {\n                    menuExpanded = false\n                    onEdit()\n                },\n            )\n            DropdownMenuItem(\n                text = { Text("Löschen", color = MaterialTheme.colorScheme.error) },\n                leadingIcon = {\n                    Icon(\n                        painterResource(R.drawable.delete),\n                        contentDescription = null,\n                        tint = MaterialTheme.colorScheme.error,\n                    )\n                },\n                onClick = {\n                    menuExpanded = false\n                    onDelete()\n                },\n            )\n        }\n    }\n}\n\n@Composable\nprivate fun FmAutoScanPanel(\n''',
)

print('patch applied')
