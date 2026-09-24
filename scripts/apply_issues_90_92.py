#!/usr/bin/env python3
from pathlib import Path

build = Path("app/build.gradle.kts")
text = build.read_text()
text = text.replace("versionCode = 1370058", "versionCode = 1370059")
text = text.replace('versionName = "13.7.49"', 'versionName = "13.7.50"')
build.write_text(text)

prefs = Path("app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt")
text = prefs.read_text()
needle = 'val Dudu7AutoCenterQueueKey = booleanPreferencesKey("dudu7AutoCenterQueue")\n'
if 'Dudu7FrostedIceKey' not in text:
    text = text.replace(needle, needle + 'val Dudu7FrostedIceKey = booleanPreferencesKey("dudu7FrostedIce")\n')
prefs.write_text(text)

appearance = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt")
text = appearance.read_text()
if 'Dudu7FrostedIceKey' not in text:
    text = text.replace(
        'import com.metrolist.music.constants.DynamicThemeKey\n',
        'import com.metrolist.music.constants.DynamicThemeKey\nimport com.metrolist.music.constants.Dudu7FrostedIceKey\n',
        1,
    )
    marker = '''    val (enableLandscapeScaling, onEnableLandscapeScalingChange) =
        rememberPreference(
            EnableLandscapeScalingKey,
            defaultValue = false,
        )
'''
    replacement = marker + '''    val (dudu7FrostedIce, onDudu7FrostedIceChange) =
        rememberPreference(
            Dudu7FrostedIceKey,
            defaultValue = false,
        )
'''
    text = text.replace(marker, replacement, 1)
    item_marker = '''                    // Only show dynamic theme option when using the default/dynamic color
'''
    item = '''                    add(
                        Material3SettingsItem(
                            icon = painterResource(R.drawable.palette),
                            title = { Text("Frosted Ice (Dudu7)") },
                            description = { Text("Cover-Hintergrund und transparente Oberfläche; standardmäßig aus") },
                            trailingContent = {
                                Switch(
                                    checked = dudu7FrostedIce,
                                    onCheckedChange = onDudu7FrostedIceChange,
                                    thumbContent = {
                                        Icon(
                                            painter = painterResource(
                                                id = if (dudu7FrostedIce) R.drawable.check else R.drawable.close,
                                            ),
                                            contentDescription = null,
                                            modifier = Modifier.size(SwitchDefaults.IconSize),
                                        )
                                    },
                                )
                            },
                            onClick = { onDudu7FrostedIceChange(!dudu7FrostedIce) },
                        ),
                    )
'''
    text = text.replace(item_marker, item + item_marker, 1)
appearance.write_text(text)

layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
text = layout.read_text()
if 'Dudu7FrostedIceKey' not in text:
    text = text.replace(
        'import com.metrolist.music.R\n',
        'import com.metrolist.music.R\nimport com.metrolist.music.constants.Dudu7FrostedIceKey\n',
        1,
    )
    text = text.replace(
        'import com.metrolist.music.utils.SearchRoutes\n',
        'import com.metrolist.music.utils.SearchRoutes\nimport com.metrolist.music.utils.rememberPreference\n',
        1,
    )

preference_block = '''    val (frostedIceEnabled) = rememberPreference(
        Dudu7FrostedIceKey,
        defaultValue = false,
    )
'''
# The script is run repeatedly by CI. Remove any existing generated declaration first,
# then insert exactly one declaration with the generated layout block.
text = text.replace(preference_block, '')
start = text.index('    val glassShape = RoundedCornerShape(24.dp)\n')
row_start = text.index('        Row(\n            modifier =\n', start)
column_start = text.index('        Column(\n', row_start)
new_prefix = preference_block + '''    val glassShape = RoundedCornerShape(24.dp)

    Box(
        modifier = Modifier.fillMaxSize().clipToBounds(),
    ) {
        if (frostedIceEnabled) {
            // Full artwork remains visible without distortion. Blur and the gradient extend it
            // naturally into the widescreen side areas without stretching the cover itself.
            Box(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .blur(34.dp)
                        .graphicsLayer { alpha = 0.88f }
                        .clearAndSetSemantics {},
                contentAlignment = Alignment.Center,
            ) {
                thumbnailContent()
            }
            Box(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .background(
                            Brush.horizontalGradient(
                                listOf(
                                    MaterialTheme.colorScheme.surface.copy(alpha = 0.62f),
                                    Color.Transparent,
                                    Color.Transparent,
                                    MaterialTheme.colorScheme.surface.copy(alpha = 0.62f),
                                ),
                            ),
                        ).background(
                            Brush.verticalGradient(
                                listOf(
                                    Color.Black.copy(alpha = 0.16f),
                                    Color.Black.copy(alpha = 0.38f),
                                    Color.Black.copy(alpha = 0.58f),
                                ),
                            ),
                        ),
            )
        }

        Row(
            modifier =
                Modifier
                    .windowInsetsPadding(
                        WindowInsets.systemBars.only(WindowInsetsSides.Horizontal).add(verticalWindowInsets),
                    ).padding(bottom = 8.dp)
                    .fillMaxSize(),
        ) {
'''
text = text[:start] + new_prefix + text[column_start:]

old_column_modifier = '''                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 8.dp, end = 6.dp)
                    .shadow(10.dp, glassShape)
                    .clip(glassShape)
                    .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.46f))
                    .border(
                        width = 1.dp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.24f),
                        shape = glassShape,
                    ).padding(horizontal = 12.dp, vertical = 4.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),'''
new_column_modifier = '''                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(horizontal = 12.dp, vertical = 4.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),'''
text = text.replace(old_column_modifier, new_column_modifier, 1)

old_surface = '''        Surface(
            shape = glassShape,
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.52f),
            border = BorderStroke(
                width = 1.dp,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.24f),
            ),
            tonalElevation = 1.dp,
            shadowElevation = 10.dp,'''
new_surface = '''        Surface(
            shape = if (frostedIceEnabled) RoundedCornerShape(0.dp) else RoundedCornerShape(12.dp),
            color =
                if (frostedIceEnabled) {
                    MaterialTheme.colorScheme.surface.copy(alpha = 0.18f)
                } else {
                    MaterialTheme.colorScheme.surfaceContainer
                },
            border = null,
            tonalElevation = if (frostedIceEnabled) 0.dp else 2.dp,
            shadowElevation = 0.dp,'''
text = text.replace(old_surface, new_surface, 1)
text = text.replace('.padding(start = 6.dp, end = 8.dp),', '.padding(horizontal = 8.dp, vertical = 4.dp),', 1)
layout.write_text(text)

assert layout.read_text().count(preference_block) == 1
assert 'Dudu7FrostedIceKey' in prefs.read_text()
assert 'defaultValue = false' in appearance.read_text()
assert 'scaleX = 1.24f' not in layout.read_text()
assert 'versionCode = 1370059' in build.read_text()
