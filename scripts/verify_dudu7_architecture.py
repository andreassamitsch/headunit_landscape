#!/usr/bin/env python3
"""Fast structural checks for the maintainable Dudu7 overlay."""
from pathlib import Path

# Keep live history, the direct title-selection queue callback and the
# independent FYT physical-radio backend protected by the lightweight check.
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
    "app/src/dudu7/java/com/android/fmradio/FmNative.java",
    "app/src/dudu7/java/com/android/fmradio/FmService.java",
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmStationArtwork.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt",
    "app/src/dudu7/res/drawable/stop.xml",
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
        'LIBRARY("Bibliothek"',
        'WEBRADIO("WebRadio"',
        'PHYSICAL_RADIO("FM"',
        'SEARCH("Suche"',
        'HISTORY("Hörverlauf"',
        'QUEUE("Warteschlange"',
        "ScrollableTabRow(",
        "PhysicalRadioPlayerPane(",
        "PhysicalRadioScreen()",
        "embeddedInPlayer = true",
        "onUserSongSelection = returnToQueue",
        "popBackStack(VEHICLE_QUEUE_ROUTE, inclusive = false)",
        "selectedTab = VehicleRightPaneTab.QUEUE",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt": (
        'private const val SWITCH_FM = "com.syu.music.switch_fm"',
        'private const val SWITCH_NONE = "com.syu.music.switch_none"',
        "twUtil?.initRadioSequence()",
        "fm.openDev()",
        "fm.powerUp(target)",
        "fm.tune(target)",
        "fun powerOff()",
        "fun seek(up: Boolean)",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt": (
        "object FmPresetOrderStore",
        "fun ordered(",
        "fun persist(",
        "fun FytPhysicalRadio.tuneAdjacentFavourite(",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmStationArtwork.kt": (
        "object FmStationLogoResolver",
        "RadioStationStore.get(appContext)",
        "RadioBrowserClient.search(stationName)",
        "RadioStationLogoResolver.resolve(station)",
        "fun FmStationArtwork(",
    ),
    "app/src/dudu7/java/com/android/fmradio/FmNative.java": (
        'System.loadLibrary("fmjni")',
        "public native boolean openDev()",
        "public native boolean powerUp(float frequency)",
        "public native boolean tune(float frequency)",
        "public native float[] seek(float frequency, boolean isUp)",
        "public native int fmsyu_jni",
    ),
    "app/src/dudu7/java/com/android/fmradio/FmService.java": (
        "public static int Rdscallback",
        "RdsListener",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt": (
        "PhysicalRadioSection.FAVOURITES",
        "PhysicalRadioSection.SEARCH",
        'Text("Favoriten")',
        'Text("Sendersuche")',
        "rememberReorderableLazyListState",
        "FmStationArtwork(",
        "FmPresetOrderStore.persist",
        "radio.seek(false)",
        "radio.seek(true)",
        "radio.saveCurrentPreset()",
    ),
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt": (
        "FmStationArtwork(",
        "radio.tuneAdjacentFavourite(context, next = false)",
        "radio.tuneAdjacentFavourite(context, next = true)",
        "radio.saveCurrentPreset()",
    ),
    "app/src/dudu7/AndroidManifest.xml": (
        "android.permission.MODIFY_AUDIO_SETTINGS",
        'android:name="com.syu.ms"',
        'android:name="com.syu.music"',
    ),
    "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt": (
        "val effectiveExpandable =",
        "state.collapsedBound - state.dismissedBound > 2.dp",
        "if (!effectiveExpandable || !state.isCollapsed)",
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
        "database.withTransaction",
        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",
    ),
    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt": (
        "var onUserSongSelection: (() -> Unit)? = null",
        "onUserSongSelection?.invoke()",
    ),
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (
        "scheduleStartupRefresh",
        "refreshAfterStreamRejection",
    ),
}
missing_tokens = []
for path, tokens in checks.items():
    text = (ROOT / path).read_text(encoding="utf-8")
    for token in tokens:
        if token not in text:
            missing_tokens.append(f"{path}: {token}")
if missing_tokens:
    raise SystemExit("Fehlende Erweiterungspunkte:\n- " + "\n- ".join(missing_tokens))

layout_path = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
layout = (ROOT / layout_path).read_text(encoding="utf-8")
expected_tab_order = (
    'LIBRARY("Bibliothek"',
    'WEBRADIO("WebRadio"',
    'PHYSICAL_RADIO("FM"',
    'SEARCH("Suche"',
    'HISTORY("Hörverlauf"',
    'QUEUE("Warteschlange"',
)
positions = [layout.index(token) for token in expected_tab_order]
if positions != sorted(positions):
    raise SystemExit("Falsche Dudu7-Tab-Reihenfolge: Bibliothek, WebRadio, FM, Suche, Hörverlauf, Warteschlange erwartet")
if 'HOME("Startseite"' in layout:
    raise SystemExit("Der nicht mehr gewünschte Startseite-Tab ist noch vorhanden")

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
