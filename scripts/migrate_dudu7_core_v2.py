#!/usr/bin/env python3
"""Robust one-time migration to the source-set based Dudu7 architecture."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text.rstrip() + "\n", encoding="utf-8")
    print(f"[migrate-v2] {path}")


def replace_once(path: str, old: str, new: str, marker: str) -> None:
    text = read(path)
    if marker in text:
        print(f"[migrate-v2] already applied: {marker}")
        return
    if old not in text:
        raise RuntimeError(f"Anchor missing in {path}: {old[:180]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, marker: str) -> None:
    text = read(path)
    if marker in text:
        print(f"[migrate-v2] already applied: {marker}")
        return
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"Regex anchor missing in {path}: {pattern}")
    write(path, updated)


def ensure_import(path: str, anchor: str, import_line: str) -> None:
    text = read(path)
    if import_line in text:
        return
    if anchor not in text:
        raise RuntimeError(f"Import anchor missing in {path}: {anchor}")
    write(path, text.replace(anchor, anchor + "\n" + import_line, 1))


for script in ("scripts/apply_dudu7_fixes.py", "scripts/apply_liked_playlist_fixes.py"):
    candidate = ROOT / script
    if candidate.exists():
        subprocess.run([sys.executable, str(candidate)], cwd=ROOT, check=True)

# Gradle device layer.
gradle = "app/build.gradle.kts"
replace_once(
    gradle,
    '    flavorDimensions += listOf("variant")',
    '    flavorDimensions += listOf("variant", "device")',
    'flavorDimensions += listOf("variant", "device")',
)
regex_once(
    gradle,
    r'(        create\("izzy"\) \{.*?        \}\n)    \}',
    r'''\1
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
    }''',
    'create("dudu7")',
)
replace_once(
    gradle,
    '    implementation(libs.timber)\n}',
    '    implementation(libs.timber)\n\n    testImplementation(kotlin("test"))\n}',
    'testImplementation(kotlin("test"))',
)

# Stable preference keys.
keys = "app/src/main/kotlin/com/metrolist/music/constants/PreferenceKeys.kt"
replace_once(
    keys,
    'val DeveloperModeKey = booleanPreferencesKey("developerMode")\n',
    'val DeveloperModeKey = booleanPreferencesKey("developerMode")\n\n'
    'val Dudu7AlwaysStartPlayerKey = booleanPreferencesKey("dudu7AlwaysStartPlayer")\n'
    'val Dudu7PlayerPaneWeightKey = floatPreferencesKey("dudu7PlayerPaneWeight")\n'
    'val Dudu7StartWithLyricsKey = booleanPreferencesKey("dudu7StartWithLyrics")\n'
    'val Dudu7SwipeToRemoveQueueKey = booleanPreferencesKey("dudu7SwipeToRemoveQueue")\n'
    'val Dudu7AutoCenterQueueKey = booleanPreferencesKey("dudu7AutoCenterQueue")\n',
    'Dudu7AlwaysStartPlayerKey',
)

app = "app/src/main/kotlin/com/metrolist/music/App.kt"
ensure_import(app, "import com.metrolist.music.utils.reportException", "import com.metrolist.music.variant.VehicleVariantDefaults")
replace_once(
    app,
    "            initializeSettings()\n",
    "            initializeSettings()\n            VehicleVariantDefaults.apply(this@App)\n",
    "VehicleVariantDefaults.apply(this@App)",
)

# Main activity: register the variant screen and expand the player on Dudu7 startup.
main = "app/src/main/kotlin/com/metrolist/music/MainActivity.kt"
ensure_import(main, "import androidx.navigation.compose.NavHost", "import androidx.navigation.compose.composable")
ensure_import(main, "import com.metrolist.music.constants.DynamicThemeKey", "import com.metrolist.music.constants.Dudu7AlwaysStartPlayerKey")
ensure_import(main, "import com.metrolist.music.ui.utils.resetHeightOffset", "import com.metrolist.music.variant.VehicleSettingsScreen")
ensure_import(main, "import com.metrolist.music.variant.VehicleSettingsScreen", "import com.metrolist.music.variant.VehicleVariantConfig")
replace_once(
    main,
    "                            expandedBound = maxHeight,\n                        )\n\n                    val playerAwareWindowInsets =",
    "                            expandedBound = maxHeight,\n                        )\n"
    "                    val (dudu7AlwaysStartPlayer) =\n"
    "                        rememberPreference(\n"
    "                            Dudu7AlwaysStartPlayerKey,\n"
    "                            defaultValue = VehicleVariantConfig.playerStartsExpanded,\n"
    "                        )\n\n"
    "                    val playerAwareWindowInsets =",
    "val (dudu7AlwaysStartPlayer)",
)
regex_once(
    main,
    r'                    LaunchedEffect\(playerConnection\) \{.*?\n                    \}\n\n                    DisposableEffect',
    '''                    LaunchedEffect(playerConnection, dudu7AlwaysStartPlayer) {
                        val player = playerConnection?.player ?: return@LaunchedEffect
                        if (VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer) {
                            if (!playerBottomSheetState.isExpanded) playerBottomSheetState.expandSoft()
                        } else if (player.currentMediaItem == null) {
                            if (!playerBottomSheetState.isDismissed) playerBottomSheetState.dismiss()
                        } else if (playerBottomSheetState.isDismissed) {
                            playerBottomSheetState.collapseSoft()
                        }
                    }

                    DisposableEffect''',
    "VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer",
)
replace_once(
    main,
    '''                                    navigationBuilder(
                                        navController = navController,
                                        scrollBehavior = topAppBarScrollBehavior,
                                        latestVersionName = latestVersionName,
                                        activity = this@MainActivity,
                                        snackbarHostState = snackbarHostState,
                                    )''',
    '''                                    navigationBuilder(
                                        navController = navController,
                                        scrollBehavior = topAppBarScrollBehavior,
                                        latestVersionName = latestVersionName,
                                        activity = this@MainActivity,
                                        snackbarHostState = snackbarHostState,
                                    )
                                    composable("vehicle_settings") {
                                        VehicleSettingsScreen(navController)
                                    }''',
    'composable("vehicle_settings")',
)

# Small bridge hooks in Player.kt.
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
    "    val (dudu7StartWithLyrics) = rememberPreference(Dudu7StartWithLyricsKey, defaultValue = false)\n"
    "    var showInlineLyrics by rememberSaveable {\n"
    "        mutableStateOf(BuildConfig.IS_DUDU7 && dudu7StartWithLyrics)\n"
    "    }",
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
    "    BackHandler(enabled = state.isExpanded) {\n"
    "        if (VehicleVariantConfig.isDudu7) {\n"
    "            (context as? android.app.Activity)?.moveTaskToBack(true)\n"
    "        } else {\n"
    "            state.collapseSoft()\n"
    "        }\n"
    "    }",
    "moveTaskToBack(true)",
)
replace_once(
    player,
    "    val sliderStyle by rememberEnumPreference(SliderStyleKey, SliderStyle.DEFAULT)\n",
    "    val sliderStyle by rememberEnumPreference(SliderStyleKey, SliderStyle.DEFAULT)\n"
    "    val (storedDudu7PlayerPaneWeight) =\n"
    "        rememberPreference(Dudu7PlayerPaneWeightKey, VehicleVariantConfig.defaultPlayerPaneWeight)\n"
    "    val dudu7PlayerPaneWeight = Dudu7Layout.sanitizePlayerPaneWeight(storedDudu7PlayerPaneWeight)\n",
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
    "                        if (mediaMetadata != null) {\n"
    "                            controlsContent(mediaMetadata)\n"
    "                        } else {\n"
    "                            VehicleEmptyPlayer(navController = navController)\n"
    "                        }",
    "VehicleEmptyPlayer(navController = navController)",
)

# Queue options; drag-and-drop remains enabled and uses the existing player move logic.
queue = "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt"
ensure_import(queue, "import com.metrolist.music.LocalPlayerConnection", "import com.metrolist.music.BuildConfig")
ensure_import(queue, "import com.metrolist.music.constants.ListItemHeight", "import com.metrolist.music.constants.Dudu7AutoCenterQueueKey")
ensure_import(queue, "import com.metrolist.music.constants.Dudu7AutoCenterQueueKey", "import com.metrolist.music.constants.Dudu7SwipeToRemoveQueueKey")
ensure_import(queue, "import com.metrolist.music.utils.rememberPreference", "import com.metrolist.music.variant.VehicleVariantConfig")
replace_once(
    queue,
    "    var locked by rememberPreference(QueueEditLockKey, defaultValue = true)",
    "    var locked by rememberPreference(\n"
    "        QueueEditLockKey,\n"
    "        defaultValue = VehicleVariantConfig.queueEditLockedDefault,\n"
    "    )\n"
    "    val (dudu7SwipeToRemoveQueue) = rememberPreference(Dudu7SwipeToRemoveQueueKey, defaultValue = true)\n"
    "    val (dudu7AutoCenterQueue) = rememberPreference(Dudu7AutoCenterQueueKey, defaultValue = true)",
    "dudu7SwipeToRemoveQueue",
)
replace_once(
    queue,
    "        LaunchedEffect(mutableQueueWindows, currentWindowIndex) {\n"
    "            if (currentWindowIndex != -1) {\n"
    "                lazyListState.scrollToItem(currentWindowIndex)\n"
    "            }\n"
    "        }",
    "        LaunchedEffect(mutableQueueWindows, currentWindowIndex, dudu7AutoCenterQueue) {\n"
    "            if (currentWindowIndex != -1 && (!BuildConfig.IS_DUDU7 || dudu7AutoCenterQueue)) {\n"
    "                lazyListState.scrollToItem(currentWindowIndex)\n"
    "            }\n"
    "        }",
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
    "                    Row {\n"
    "                        if (BuildConfig.IS_DUDU7) {\n"
    "                            IconButton(onClick = { navController.navigate(\"vehicle_settings\") }) {\n"
    "                                Icon(\n"
    "                                    painter = painterResource(R.drawable.settings),\n"
    "                                    contentDescription = \"Dudu7 settings\",\n"
    "                                )\n"
    "                            }\n"
    "                        }\n"
    "                        IconButton(\n"
    "                            onClick = { locked = !locked },",
    'navController.navigate("vehicle_settings")',
)

print("Dudu7 core migration v2 completed")
