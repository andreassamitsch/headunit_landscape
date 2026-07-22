#!/usr/bin/env python3
"""Fast structural checks for the maintainable Dudu7 overlay."""
from pathlib import Path

# Keep the live-history transaction and explicit user-selection queue return
# protected by the lightweight Dudu7 architecture check.
ROOT = Path(__file__).resolve().parents[1]
HOOKS = (
    "VehicleVariantConfig.kt",
    "VehicleVariantDefaults.kt",
    "VehicleEmptyPlayer.kt",
    "VehicleSettingsScreen.kt",
    "VehicleLandscapeLayout.kt",
    "VehiclePlayerControls.kt",
    "VehicleNavigation.kt",
    "VehicleQueueActions.kt",
    "VehicleVoiceSearch.kt",
)
required = [
    "app/src/main/kotlin/com/metrolist/music/variant/Dudu7Layout.kt",
    "app/src/test/kotlin/com/metrolist/music/variant/Dudu7LayoutTest.kt",
    "app/src/dudu7/AndroidManifest.xml",
    "app/keystore/dudu7-debug.keystore",
    "docs/DUDU7_ARCHITECTURE.md",
]
for source_set in ("standard", "dudu7"):
    required.extend(
        f"app/src/{source_set}/kotlin/com/metrolist/music/variant/{name}" for name in HOOKS
    )
missing = [path for path in required if not (ROOT / path).is_file()]
if missing:
    raise SystemExit("Fehlende Dudu7-Dateien: " + ", ".join(missing))

build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
for token in (
    'flavorDimensions += listOf("variant", "device")',
    'create("standard")',
    'create("dudu7")',
    'buildConfigField("Boolean", "IS_DUDU7", "false")',
    'buildConfigField("Boolean", "IS_DUDU7", "true")',
):
    if token not in build:
        raise SystemExit(f"Fehlende Gradle-Konfiguration: {token}")

checks = {
    "app/src/main/kotlin/com/metrolist/music/App.kt": ("VehicleVariantDefaults.apply",),
    "app/src/main/kotlin/com/metrolist/music/MainActivity.kt": (
        "VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer",
        "vehicleNavigation(navController)",
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt": (
        "VehicleLandscapeLayout(",
        "VehiclePlayerControls(",
        "VehicleEmptyPlayer(navController = navController)",
        "moveTaskToBack(true)",
        "visible = !isFullScreen && !VehicleVariantConfig.isDudu7",
        "landscapeHorizontalPadding = 2.dp",
        "shuffleModeEnabled = shuffleModeEnabled",
        "onToggleRepeat = playerConnection.player::toggleRepeatMode",
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt": (
        "rememberReorderableLazyListState",
        "moveMediaItem",
        "VehicleQueueActions()",
        "top = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp",
        "bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp",
        "isExpandable = !VehicleVariantConfig.isDudu7",
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/screens/search/SearchScreen.kt": (
        "rememberVehicleVoiceSearch(",
        "onClick = vehicleVoiceSearch",
        "embeddedInPlayer: Boolean = false",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt": (
        "QUEUE(\"Warteschlange\"",
        "LIBRARY(\"Bibliothek\"",
        "SEARCH(\"Suche\"",
        "HISTORY(\"Hörverlauf\"",
        "HOME(\"Startseite\"",
        "ScrollableTabRow(",
        "embeddedInPlayer = true",
        "userSongSelections?.collect",
        "selectedTab = VehicleRightPaneTab.QUEUE",
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt": (
        "if (!isExpandable || !state.isCollapsed)",
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt": (
        "landscapeHorizontalPadding: Dp = PlayerHorizontalPadding",
        ".padding(horizontal = if (isLandscape) landscapeHorizontalPadding else PlayerHorizontalPadding)",
        "if (!VehicleVariantConfig.isDudu7) {",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt": (
        "shuffleModeEnabled: Boolean",
        "repeatMode: Int",
        "R.drawable.shuffle",
        "R.drawable.repeat",
        "R.drawable.radio",
        "R.drawable.favorite_border",
        "modifier = Modifier.weight(1f)",
    ),
    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt": (
        "activeHistoryMonitorJob",
        "Recorded active history item",
        "database.withTransaction",
        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",
    ),
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (
        "scheduleStartupRefresh",
        "refreshAfterStreamRejection",
    ),
}
for path, tokens in checks.items():
    text = (ROOT / path).read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            raise SystemExit(f"Fehlender Erweiterungspunkt in {path}: {token}")

forbidden_dudu_controls = (
    "R.drawable.share",
    "onShare:",
)
dudu_controls = (
    ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt"
).read_text(encoding="utf-8")
for token in forbidden_dudu_controls:
    if token in dudu_controls:
        raise SystemExit(f"Unerwünschtes Dudu7-Steuerelement vorhanden: {token}")

print("Dudu7 architecture verification passed")
