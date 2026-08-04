#!/usr/bin/env python3
from pathlib import Path

build = Path("app/build.gradle.kts")
text = build.read_text()
text = text.replace("versionCode = 1370059", "versionCode = 1370060")
text = text.replace('versionName = "13.7.50"', 'versionName = "13.7.51"')
build.write_text(text)

prefs = Path("app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt")
text = prefs.read_text()
needle = 'val Dudu7FrostedIceKey = booleanPreferencesKey("dudu7FrostedIce")\n'
addition = (
    needle
    + 'val Dudu7FrostedGlassStrengthKey = intPreferencesKey("dudu7FrostedGlassStrength")\n'
    + 'val Dudu7FrostedBlurStrengthKey = intPreferencesKey("dudu7FrostedBlurStrength")\n'
)
if 'Dudu7FrostedGlassStrengthKey' not in text:
    text = text.replace(needle, addition, 1)
prefs.write_text(text)

appearance = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AppearanceSettings.kt")
text = appearance.read_text()
if 'Dudu7FrostedGlassStrengthKey' not in text:
    text = text.replace(
        'import com.metrolist.music.constants.Dudu7FrostedIceKey\n',
        'import com.metrolist.music.constants.Dudu7FrostedIceKey\n'
        'import com.metrolist.music.constants.Dudu7FrostedGlassStrengthKey\n'
        'import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n',
        1,
    )
    pref_marker = '''    val (dudu7FrostedIce, onDudu7FrostedIceChange) =
        rememberPreference(
            Dudu7FrostedIceKey,
            defaultValue = false,
        )
'''
    pref_addition = pref_marker + '''    val (dudu7FrostedGlassStrength, onDudu7FrostedGlassStrengthChange) =
        rememberPreference(
            Dudu7FrostedGlassStrengthKey,
            defaultValue = 55,
        )
    val (dudu7FrostedBlurStrength, onDudu7FrostedBlurStrengthChange) =
        rememberPreference(
            Dudu7FrostedBlurStrengthKey,
            defaultValue = 12,
        )
'''
    text = text.replace(pref_marker, pref_addition, 1)

    item_end = '''                            onClick = { onDudu7FrostedIceChange(!dudu7FrostedIce) },
                        ),
                    )
'''
    sliders = item_end + '''                    if (dudu7FrostedIce) {
                        add(
                            Material3SettingsItem(
                                icon = painterResource(R.drawable.palette),
                                title = { Text("Glasstärke") },
                                description = { Text("${dudu7FrostedGlassStrength}% Deckkraft") },
                                trailingContent = {
                                    Slider(
                                        value = dudu7FrostedGlassStrength.toFloat(),
                                        onValueChange = { onDudu7FrostedGlassStrengthChange(it.roundToInt()) },
                                        valueRange = 15f..90f,
                                        steps = 14,
                                        modifier = Modifier.fillMaxWidth(0.42f),
                                    )
                                },
                                onClick = {},
                            ),
                        )
                        add(
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
                    }
'''
    text = text.replace(item_end, sliders, 1)
# Repair already-applied revisions that referenced drawables not present in MetroList.
text = text.replace('R.drawable.opacity', 'R.drawable.palette')
text = text.replace('R.drawable.blur_on', 'R.drawable.palette')
appearance.write_text(text)

layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
text = layout.read_text()
text = text.replace('import androidx.compose.ui.graphics.Brush\n', '')
text = text.replace('import androidx.compose.ui.graphics.Color\n', '')
text = text.replace('import androidx.compose.ui.graphics.graphicsLayer\n', '')
text = text.replace('import androidx.compose.ui.semantics.clearAndSetSemantics\n', '')
if 'Dudu7FrostedGlassStrengthKey' not in text:
    text = text.replace(
        'import com.metrolist.music.constants.Dudu7FrostedIceKey\n',
        'import com.metrolist.music.constants.Dudu7FrostedIceKey\n'
        'import com.metrolist.music.constants.Dudu7FrostedGlassStrengthKey\n'
        'import com.metrolist.music.constants.Dudu7FrostedBlurStrengthKey\n',
        1,
    )

prefs_marker = '''    val (frostedIceEnabled) = rememberPreference(
        Dudu7FrostedIceKey,
        defaultValue = false,
    )
    val glassShape = RoundedCornerShape(24.dp)
'''
prefs_replacement = '''    val (frostedIceEnabled) = rememberPreference(
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
    val glassAlpha = (frostedGlassStrength.coerceIn(15, 90) / 100f)
    val glassBlur = frostedBlurStrength.coerceIn(0, 24).dp
    val baseColors = MaterialTheme.colorScheme
    val frostedColors =
        if (frostedIceEnabled) {
            baseColors.copy(
                surface = baseColors.surface.copy(alpha = glassAlpha),
                surfaceVariant = baseColors.surfaceVariant.copy(alpha = glassAlpha),
                surfaceContainerLowest = baseColors.surfaceContainerLowest.copy(alpha = glassAlpha * 0.72f),
                surfaceContainerLow = baseColors.surfaceContainerLow.copy(alpha = glassAlpha * 0.78f),
                surfaceContainer = baseColors.surfaceContainer.copy(alpha = glassAlpha * 0.84f),
                surfaceContainerHigh = baseColors.surfaceContainerHigh.copy(alpha = glassAlpha * 0.90f),
                surfaceContainerHighest = baseColors.surfaceContainerHighest.copy(alpha = glassAlpha),
            )
        } else {
            baseColors
        }
    val glassShape = RoundedCornerShape(24.dp)
'''
text = text.replace(prefs_marker, prefs_replacement, 1)

start = text.find('        if (frostedIceEnabled) {\n            // Full artwork remains visible')
if start >= 0:
    row = text.find('        Row(\n', start)
    text = text[:start] + text[row:]

text = text.replace(
    '''        Surface(
            shape = if (frostedIceEnabled) RoundedCornerShape(0.dp) else RoundedCornerShape(12.dp),
            color =
                if (frostedIceEnabled) {
                    MaterialTheme.colorScheme.surface.copy(alpha = 0.18f)
                } else {
                    MaterialTheme.colorScheme.surfaceContainer
                },''',
    '''        Surface(
            shape = if (frostedIceEnabled) glassShape else RoundedCornerShape(12.dp),
            color = if (frostedIceEnabled) frostedColors.surfaceContainer else baseColors.surfaceContainer,''',
    1,
)

surface_pos = text.find('        Surface(\n', text.find('val frostedColors'))
brace_pos = text.find(') {\n', surface_pos)
if surface_pos >= 0 and brace_pos >= 0 and 'MaterialTheme(colorScheme = frostedColors)' not in text[brace_pos:brace_pos+200]:
    insert_at = brace_pos + 4
    text = text[:insert_at] + '''            if (frostedIceEnabled && frostedBlurStrength > 0) {
                Box(
                    Modifier
                        .fillMaxSize()
                        .clip(glassShape)
                        .background(frostedColors.surface.copy(alpha = glassAlpha * 0.45f))
                        .blur(glassBlur),
                )
            }
            MaterialTheme(colorScheme = frostedColors) {
''' + text[insert_at:]
    depth = 1
    i = insert_at
    while i < len(text):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                text = text[:i] + '            }\n' + text[i:]
                break
        i += 1

layout.write_text(text)

assert 'Full artwork remains visible' not in layout.read_text()
assert 'thumbnailContent()\n            }\n            Box(' not in layout.read_text()
assert 'Dudu7FrostedGlassStrengthKey' in prefs.read_text()
assert 'Glasstärke' in appearance.read_text()
assert 'R.drawable.opacity' not in appearance.read_text()
assert 'R.drawable.blur_on' not in appearance.read_text()
assert 'MaterialTheme(colorScheme = frostedColors)' in layout.read_text()
assert 'versionCode = 1370060' in build.read_text()
