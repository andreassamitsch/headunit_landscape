#!/usr/bin/env python3
"""One-time migration of the fork to a source-set based Dudu7 layer."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"[migrate] {path}")


def replace_once(path: str, old: str, new: str, marker: str) -> None:
    text = read(path)
    if marker in text:
        print(f"[migrate] already applied: {marker}")
        return
    if old not in text:
        raise RuntimeError(f"Anchor missing in {path}: {old[:160]!r}")
    write(path, text.replace(old, new, 1))


def ensure_import(path: str, anchor: str, import_line: str) -> None:
    text = read(path)
    if import_line in text:
        return
    if anchor not in text:
        raise RuntimeError(f"Import anchor missing in {path}: {anchor}")
    write(path, text.replace(anchor, anchor + "\n" + import_line, 1))


# Materialize the already-tested hot fixes into source before deleting build-time patching.
for script in ("scripts/apply_dudu7_fixes.py", "scripts/apply_liked_playlist_fixes.py"):
    path = ROOT / script
    if path.exists():
        subprocess.run([sys.executable, str(path)], cwd=ROOT, check=True)

# Two independent dimensions: service stack and device UI.
gradle = "app/build.gradle.kts"
replace_once(
    gradle,
    '    flavorDimensions += listOf("variant")',
    '    flavorDimensions += listOf("variant", "device")',
    'flavorDimensions += listOf("variant", "device")',
)
replace_once(
    gradle,
    dedent('''
        // IzzyOnDroid variant - no Google Cast, no built-in updater (store handles updates)
        create("izzy") {
            dimension = "variant"
            buildConfigField("Boolean", "CAST_AVAILABLE", "false")
            buildConfigField("Boolean", "UPDATER_AVAILABLE", "false")
        }
    }
    ''').rstrip(),
    dedent('''
        // IzzyOnDroid variant - no Google Cast, no built-in updater (store handles updates)
        create("izzy") {
            dimension = "variant"
            buildConfigField("Boolean", "CAST_AVAILABLE", "false")
            buildConfigField("Boolean", "UPDATER_AVAILABLE", "false")
        }

        create("standard") {
            dimension = "device"
            isDefault = true
            buildConfigField("Boolean", "IS_DUDU7", "false")
        }
        create("dudu7") {
            dimension = "device"
            applicationIdSuffix = ".dudu7"
            versionNameSuffix = "-dudu7"
            buildConfigField("Boolean", "IS_DUDU7", "true")
        }
    }
    ''').rstrip(),
    'create("dudu7")',
)
replace_once(
    gradle,
    '    implementation(libs.timber)\n}',
    '    implementation(libs.timber)\n\n    testImplementation(kotlin("test"))\n}',
    'testImplementation(kotlin("test"))',
)

# Dudu7 preferences remain stable across upstream merges.
keys = "app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt"
replace_once(
    keys,
    'val DeveloperModeKey = booleanPreferencesKey("developerMode")\n',
    dedent('''
        val DeveloperModeKey = booleanPreferencesKey("developerMode")

        val Dudu7AlwaysStartPlayerKey = booleanPreferencesKey("dudu7AlwaysStartPlayer")
        val Dudu7PlayerPaneWeightKey = floatPreferencesKey("dudu7PlayerPaneWeight")
        val Dudu7StartWithLyricsKey = booleanPreferencesKey("dudu7StartWithLyrics")
        val Dudu7SwipeToRemoveQueueKey = booleanPreferencesKey("dudu7SwipeToRemoveQueue")
        val Dudu7AutoCenterQueueKey = booleanPreferencesKey("dudu7AutoCenterQueue")
    '''),
    'Dudu7AlwaysStartPlayerKey',
)

# Apply source-set defaults after upstream initialization.
app = "app/src/main/kotlin/com/metrolist/music/App.kt"
ensure_import(app, "import com.metrolist.music.utils.reportException", "import com.metrolist.music.variant.VehicleVariantDefaults")
replace_once(
    app,
    "            initializeSettings()\n",
    "            initializeSettings()\n            VehicleVariantDefaults.apply(this@App)\n",
    "VehicleVariantDefaults.apply(this@App)",
)

# Player-first app startup and settings route.
main = "app/src/main/kotlin/com/metrolist/music/MainActivity.kt"
ensure_import(main, "import androidx.navigation.compose.NavHost", "import androidx.navigation.compose.composable")
ensure_import(main, "import com.metrolist.music.constants.DynamicThemeKey", "import com.metrolist.music.constants.Dudu7AlwaysStartPlayerKey")
ensure_import(main, "import com.metrolist.music.ui.utils.resetHeightOffset", "import com.metrolist.music.variant.VehicleSettingsScreen")
ensure_import(main, "import com.metrolist.music.variant.VehicleSettingsScreen", "import com.metrolist.music.variant.VehicleVariantConfig")
replace_once(
    main,
    dedent('''
                    val playerBottomSheetState =
                        rememberBottomSheetState(
                            dismissedBound = 0.dp,
                            collapsedBound =
                                bottomInset +
                                    (if (!showRail && shouldShowNavigationBar) navPadding else 0.dp) +
                                    (if (useNewMiniPlayerDesign) MiniPlayerBottomSpacing else 0.dp) +
                                    MiniPlayerHeight,
                            expandedBound = maxHeight,
                        )
    ''').rstrip(),
    dedent('''
                    val playerBottomSheetState =
                        rememberBottomSheetState(
                            dismissedBound = 0.dp,
                            collapsedBound =
                                bottomInset +
                                    (if (!showRail && shouldShowNavigationBar) navPadding else 0.dp) +
                                    (if (useNewMiniPlayerDesign) MiniPlayerBottomSpacing else 0.dp) +
                                    MiniPlayerHeight,
                            expandedBound = maxHeight,
                        )
                    val (dudu7AlwaysStartPlayer) =
                        rememberPreference(
                            Dudu7AlwaysStartPlayerKey,
                            defaultValue = VehicleVariantConfig.playerStartsExpanded,
                        )
    ''').rstrip(),
    "val (dudu7AlwaysStartPlayer)",
)
replace_once(
    main,
    dedent('''
                    LaunchedEffect(playerConnection) {
                        val player = playerConnection?.player ?: return@LaunchedEffect
                        if (player.currentMediaItem == null) {
                            if (!playerBottomSheetState.isDismissed) {
                                playerBottomSheetState.dismiss()
                            }
                        } else {
                            if (playerBottomSheetState.isDismissed) {
                                playerBottomSheetState.collapseSoft()
                            }
                        }
                    }
    ''').rstrip(),
    dedent('''
                    LaunchedEffect(playerConnection, dudu7AlwaysStartPlayer) {
                        val player = playerConnection?.player ?: return@LaunchedEffect
                        if (VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer) {
                            if (!playerBottomSheetState.isExpanded) playerBottomSheetState.expandSoft()
                        } else if (player.currentMediaItem == null) {
                            if (!playerBottomSheetState.isDismissed) playerBottomSheetState.dismiss()
                        } else if (playerBottomSheetState.isDismissed) {
                            playerBottomSheetState.collapseSoft()
                        }
                    }
    ''').rstrip(),
    "VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer",
)
replace_once(
    main,
    dedent('''
                                    navigationBuilder(
                                        navController = navController,
                                        scrollBehavior = topAppBarScrollBehavior,
                                        latestVersionName = latestVersionName,
                                        activity = this@MainActivity,
                                        snackbarHostState = snackbarHostState,
                                    )
    ''').rstrip(),
    dedent('''
                                    navigationBuilder(
                                        navController = navController,
                                        scrollBehavior = topAppBarScrollBehavior,
                                        latestVersionName = latestVersionName,
                                        activity = this@MainActivity,
                                        snackbarHostState = snackbarHostState,
                                    )
                                    composable("vehicle_settings") {
                                        VehicleSettingsScreen(navController)
                                    }
    ''').rstrip(),
    'composable("vehicle_settings")',
)

# Minimal, stable hooks in the upstream Player.
player = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
ensure_import(player, "import com.metrolist.music.LocalPlayerConnection", "import com.metrolist.music.BuildConfig")
ensure_import(player, "import com.metrolist.music.constants.DarkModeKey", "import com.metrolist.music.constants.Dudu7PlayerPaneWeightKey")
ensure_import(player, "import com.metrolist.music.constants.Dudu7PlayerPaneWeightKey", "import com.metrolist.music.constants.Dudu7StartWithLyricsKey")
ensure_import(player, "import com.metrolist.music.ui.utils.ShowOffsetDialog", "import com.metrolist.music.variant.Dudu7Layout")
ensure_import(player, "import com.metrolist.music.variant.Dudu7Layout", "import com.metrolist.music.variant.VehicleEmptyPlayer")
ensure_import(player, "import com.metrolist.music.variant.VehicleEmptyPlayer", "import com.metrolist.music.variant.VehicleVariantConfig")
replace_once(
    player,
    "    var showInlineLyrics by rememberSaveable {\n        mutableStateOf(false)\n    }",
    "    val (dudu7StartWithLyrics) = rememberPreference(Dudu7StartWithLyricsKey, defaultValue = false)\n    var showInlineLyrics by rememberSaveable {\n        mutableStateOf(BuildConfig.IS_DUDU7 && dudu7StartWithLyrics)\n    }",
    "dudu7StartWithLyrics",
)
replace_once(
    player,
    "    val isKeepScreenOn by rememberPreference(KeepScreenOn, false)",
    "    val isKeepScreenOn by rememberPreference(KeepScreenOn, VehicleVariantConfig.keepScreenOnDefault)",
    "VehicleVariantConfig.keepScreenOnDefault",
)
replace_once(
    player,
    "    BackHandler(enabled = state.isExpanded) {\n        state.collapseSoft()\n    }",
    "    BackHandler(enabled = state.isExpanded) {\n        if (VehicleVariantConfig.isDudu7) {\n            (context as? android.app.Activity)?.moveTaskToBack(true)\n        } else {\n            state.collapseSoft()\n        }\n    }",
    "moveTaskToBack(true)",
)
replace_once(
    player,
    "    val sliderStyle by rememberEnumPreference(SliderStyleKey, SliderStyle.DEFAULT)\n",
    "    val sliderStyle by rememberEnumPreference(SliderStyleKey, SliderStyle.DEFAULT)\n    val (storedDudu7PlayerPaneWeight) =\n        rememberPreference(Dudu7PlayerPaneWeightKey, VehicleVariantConfig.defaultPlayerPaneWeight)\n    val dudu7PlayerPaneWeight = Dudu7Layout.sanitizePlayerPaneWeight(storedDudu7PlayerPaneWeight)\n",
    "storedDudu7PlayerPaneWeight",
)
replace_once(
    player,
    ".weight(0.45f)\n                                .fillMaxSize()",
    ".weight(if (BuildConfig.IS_DUDU7) dudu7PlayerPaneWeight else 0.45f)\n                                .fillMaxSize()",
    "dudu7PlayerPaneWeight else 0.45f",
)
replace_once(
    player,
    ".weight(0.55f)\n                            .fillMaxSize()",
    ".weight(if (BuildConfig.IS_DUDU7) 1f - dudu7PlayerPaneWeight else 0.55f)\n                            .fillMaxSize()",
    "1f - dudu7PlayerPaneWeight",
)
replace_once(
    player,
    "                        mediaMetadata?.let {\n                            controlsContent(it)\n                        }",
    "                        if (mediaMetadata != null) {\n                            controlsContent(mediaMetadata)\n                        } else {\n                            VehicleEmptyPlayer(navController = navController)\n                        }",
    "VehicleEmptyPlayer(navController = navController)",
)

# Queue stays fully functional, including drag-and-drop.
queue = "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt"
ensure_import(queue, "import com.metrolist.music.LocalPlayerConnection", "import com.metrolist.music.BuildConfig")
ensure_import(queue, "import com.metrolist.music.constants.ListItemHeight", "import com.metrolist.music.constants.Dudu7AutoCenterQueueKey")
ensure_import(queue, "import com.metrolist.music.constants.Dudu7AutoCenterQueueKey", "import com.metrolist.music.constants.Dudu7SwipeToRemoveQueueKey")
ensure_import(queue, "import com.metrolist.music.utils.rememberPreference", "import com.metrolist.music.variant.VehicleVariantConfig")
replace_once(
    queue,
    "    var locked by rememberPreference(QueueEditLockKey, defaultValue = true)",
    "    var locked by rememberPreference(\n        QueueEditLockKey,\n        defaultValue = VehicleVariantConfig.queueEditLockedDefault,\n    )\n    val (dudu7SwipeToRemoveQueue) = rememberPreference(Dudu7SwipeToRemoveQueueKey, defaultValue = true)\n    val (dudu7AutoCenterQueue) = rememberPreference(Dudu7AutoCenterQueueKey, defaultValue = true)",
    "dudu7SwipeToRemoveQueue",
)
replace_once(
    queue,
    "        LaunchedEffect(mutableQueueWindows, currentWindowIndex) {\n            if (currentWindowIndex != -1) {\n                lazyListState.scrollToItem(currentWindowIndex)\n            }\n        }",
    "        LaunchedEffect(mutableQueueWindows, currentWindowIndex, dudu7AutoCenterQueue) {\n            if (currentWindowIndex != -1 && (!BuildConfig.IS_DUDU7 || dudu7AutoCenterQueue)) {\n                lazyListState.scrollToItem(currentWindowIndex)\n            }\n        }",
    "dudu7AutoCenterQueue))",
)
replace_once(
    queue,
    "                        if (locked) {\n                            content()",
    "                        if (locked || (BuildConfig.IS_DUDU7 && !dudu7SwipeToRemoveQueue)) {\n                            content()",
    "!dudu7SwipeToRemoveQueue",
)
replace_once(
    queue,
    "                    Row {\n                        IconButton(\n                            onClick = { locked = !locked },",
    "                    Row {\n                        if (BuildConfig.IS_DUDU7) {\n                            IconButton(onClick = { navController.navigate(\"vehicle_settings\") }) {\n                                Icon(\n                                    painter = painterResource(R.drawable.settings),\n                                    contentDescription = \"Dudu7 settings\",\n                                )\n                            }\n                        }\n                        IconButton(\n                            onClick = { locked = !locked },",
    'navController.navigate("vehicle_settings")',
)

print("Dudu7 core migration completed")
