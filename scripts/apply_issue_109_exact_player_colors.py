from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
LAYOUT = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
FM_PANE = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt"
BUILD = ROOT / "app/build.gradle.kts"


def replace_exact(text: str, old: str, new: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"Expected {expected} occurrence(s), found {count}: {old!r}")
    return text.replace(old, new)


player = PLAYER.read_text(encoding="utf-8")
player = replace_exact(
    player,
    """                    tabContentColor = tabContentColor,
                    tabGlassColor = tabGlassColor,
                    onPhysicalRadioVisualChanged = { active, identity, artworkUrl ->""",
    """                    tabContentColor = tabContentColor,
                    tabGlassColor = tabGlassColor,
                    playerTextColor = TextBackgroundColor,
                    playerSecondaryTextColor = TextBackgroundColor.copy(alpha = 0.76f),
                    playerPlayButtonContainerColor = textButtonColor,
                    playerPlayButtonContentColor = iconButtonColor,
                    playerSideButtonContentColor = sideButtonContentColor,
                    onPhysicalRadioVisualChanged = { active, identity, artworkUrl ->""",
)
PLAYER.write_text(player, encoding="utf-8")

layout = LAYOUT.read_text(encoding="utf-8")
layout = replace_exact(
    layout,
    """    tabContentColor: Color,
    tabGlassColor: Color,
    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,""",
    """    tabContentColor: Color,
    tabGlassColor: Color,
    playerTextColor: Color,
    playerSecondaryTextColor: Color,
    playerPlayButtonContainerColor: Color,
    playerPlayButtonContentColor: Color,
    playerSideButtonContentColor: Color,
    onPhysicalRadioVisualChanged: (Boolean, String, String?) -> Unit,""",
)
layout = replace_exact(
    layout,
    """                        PhysicalRadioPlayerPane(
                            radio = physicalRadio,
                            playerConnection = playerConnection,
                        )""",
    """                        PhysicalRadioPlayerPane(
                            radio = physicalRadio,
                            playerConnection = playerConnection,
                            titleColor = if (frostedIceEnabled) playerTextColor else baseColors.onSurface,
                            secondaryTextColor =
                                if (frostedIceEnabled) playerSecondaryTextColor else baseColors.onSurfaceVariant,
                            playButtonContainerColor =
                                if (frostedIceEnabled) playerPlayButtonContainerColor else baseColors.primary,
                            playButtonContentColor =
                                if (frostedIceEnabled) playerPlayButtonContentColor else baseColors.onPrimary,
                            sideButtonContentColor =
                                if (frostedIceEnabled) playerSideButtonContentColor else baseColors.onSurfaceVariant,
                            actionColor = if (frostedIceEnabled) playerTextColor else baseColors.primary,
                        )""",
)
LAYOUT.write_text(layout, encoding="utf-8")

pane = FM_PANE.read_text(encoding="utf-8")
pane = replace_exact(
    pane,
    "import androidx.compose.ui.Modifier\n",
    "import androidx.compose.ui.Modifier\nimport androidx.compose.ui.graphics.Color\n",
)
pane = replace_exact(
    pane,
    """fun PhysicalRadioPlayerPane(
    radio: FytPhysicalRadio,
    playerConnection: PlayerConnection?,
) {""",
    """fun PhysicalRadioPlayerPane(
    radio: FytPhysicalRadio,
    playerConnection: PlayerConnection?,
    titleColor: Color,
    secondaryTextColor: Color,
    playButtonContainerColor: Color,
    playButtonContentColor: Color,
    sideButtonContentColor: Color,
    actionColor: Color,
) {""",
)
pane = replace_exact(
    pane,
    """            textAlign = TextAlign.Center,
            maxLines = 2,""",
    """            textAlign = TextAlign.Center,
            color = titleColor,
            maxLines = 2,""",
    1,
)
pane = replace_exact(
    pane,
    """            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 2,""",
    """            color = secondaryTextColor,
            maxLines = 2,""",
    1,
)
pane = replace_exact(
    pane,
    """                    painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger FM-Favorit",
                    modifier = Modifier.size(34.dp),""",
    """                    painterResource(R.drawable.skip_previous),
                    contentDescription = "Vorheriger FM-Favorit",
                    tint = sideButtonContentColor,
                    modifier = Modifier.size(34.dp),""",
)
pane = replace_exact(
    pane,
    """                        containerColor = MaterialTheme.colorScheme.primary,
                        contentColor = MaterialTheme.colorScheme.onPrimary,""",
    """                        containerColor = playButtonContainerColor,
                        contentColor = playButtonContentColor,""",
)
pane = replace_exact(
    pane,
    """                    painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster FM-Favorit",
                    modifier = Modifier.size(34.dp),""",
    """                    painterResource(R.drawable.skip_next),
                    contentDescription = "Nächster FM-Favorit",
                    tint = sideButtonContentColor,
                    modifier = Modifier.size(34.dp),""",
)
pane = replace_exact(
    pane,
    """            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,""",
    """            style = MaterialTheme.typography.labelLarge,
            color = secondaryTextColor,
            maxLines = 1,""",
)
pane = replace_exact(
    pane,
    "MaterialTheme.colorScheme.onSurfaceVariant",
    "sideButtonContentColor",
    2,
)
pane = replace_exact(
    pane,
    "MaterialTheme.colorScheme.primary",
    "actionColor",
    3,
)
pane = replace_exact(
    pane,
    """                    Icon(
                        painter = painterResource(R.drawable.search),
                        contentDescription = "FM-Musik erkennen",
                    )""",
    """                    Icon(
                        painter = painterResource(R.drawable.search),
                        contentDescription = "FM-Musik erkennen",
                        tint = sideButtonContentColor,
                    )""",
)
pane = replace_exact(
    pane,
    """                CircularProgressIndicator(
                    strokeWidth = 2.dp,
                    modifier = Modifier.align(Alignment.BottomEnd).size(24.dp),
                )""",
    """                CircularProgressIndicator(
                    color = actionColor,
                    strokeWidth = 2.dp,
                    modifier = Modifier.align(Alignment.BottomEnd).size(24.dp),
                )""",
)
pane = replace_exact(
    pane,
    "CircularProgressIndicator(strokeWidth = 2.dp, modifier = Modifier.size(24.dp))",
    "CircularProgressIndicator(color = actionColor, strokeWidth = 2.dp, modifier = Modifier.size(24.dp))",
)
FM_PANE.write_text(pane, encoding="utf-8")

build = BUILD.read_text(encoding="utf-8")
build = replace_exact(build, "versionCode = 1370067", "versionCode = 1370068")
build = replace_exact(build, 'versionName = "13.7.58"', 'versionName = "13.7.59"')
BUILD.write_text(build, encoding="utf-8")

print("Issue #109 exact player color patch applied")
