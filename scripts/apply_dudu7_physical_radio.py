#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
MANIFEST = ROOT / "app/src/dudu7/AndroidManifest.xml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Marker not found for {label}")
    return text.replace(old, new, 1)


def patch_layout() -> None:
    text = LAYOUT.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "import androidx.compose.ui.unit.dp\nimport androidx.navigation.compose.NavHost",
        "import androidx.compose.ui.unit.dp\nimport androidx.lifecycle.compose.collectAsStateWithLifecycle\nimport androidx.navigation.compose.NavHost",
        "lifecycle import",
    )
    text = replace_once(
        text,
        "import com.metrolist.music.R\nimport com.metrolist.music.ui.component.BottomSheetState",
        "import com.metrolist.music.R\nimport com.metrolist.music.radio.fyt.FytPhysicalRadio\nimport com.metrolist.music.ui.component.BottomSheetState",
        "physical radio import",
    )
    text = replace_once(
        text,
        "import com.metrolist.music.ui.screens.radio.WebRadioScreen",
        "import com.metrolist.music.ui.screens.radio.PhysicalRadioScreen\nimport com.metrolist.music.ui.screens.radio.WebRadioScreen",
        "physical radio screen import",
    )
    text = replace_once(
        text,
        'private const val VEHICLE_WEBRADIO_ROUTE = "vehicle_webradio"',
        'private const val VEHICLE_WEBRADIO_ROUTE = "vehicle_webradio"\nprivate const val VEHICLE_PHYSICAL_RADIO_ROUTE = "vehicle_physical_radio"',
        "physical radio route",
    )
    text = replace_once(
        text,
        '    HISTORY("Hörverlauf", R.drawable.history, "history"),\n    WEBRADIO("WebRadio", R.drawable.radio, VEHICLE_WEBRADIO_ROUTE),',
        '    HISTORY("Hörverlauf", R.drawable.history, "history"),\n    PHYSICAL_RADIO("FM", R.drawable.radio, VEHICLE_PHYSICAL_RADIO_ROUTE),\n    WEBRADIO("WebRadio", R.drawable.radio, VEHICLE_WEBRADIO_ROUTE),',
        "physical radio tab",
    )
    text = replace_once(
        text,
        "    val activity = LocalContext.current.findActivity()\n    val snackbarHostState = remember { SnackbarHostState() }\n    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()\n    val playerConnection = LocalPlayerConnection.current\n    val rightPaneScope = rememberCoroutineScope()",
        "    val context = LocalContext.current\n    val activity = context.findActivity()\n    val snackbarHostState = remember { SnackbarHostState() }\n    val scrollBehavior = TopAppBarDefaults.pinnedScrollBehavior()\n    val playerConnection = LocalPlayerConnection.current\n    val physicalRadio = remember(context) { FytPhysicalRadio.get(context) }\n    val physicalRadioState by physicalRadio.state.collectAsStateWithLifecycle()\n    val androidIsPlayingState =\n        playerConnection?.isEffectivelyPlaying?.collectAsStateWithLifecycle()\n            ?: remember { mutableStateOf(false) }\n    val androidIsPlaying by androidIsPlayingState\n    val rightPaneScope = rememberCoroutineScope()",
        "physical radio state",
    )
    text = replace_once(
        text,
        "    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {\n        paneNavController.popBackStack()\n    }",
        "    LaunchedEffect(androidIsPlaying, physicalRadioState.isActive) {\n        if (androidIsPlaying && physicalRadioState.isActive) {\n            physicalRadio.powerOff()\n        }\n    }\n\n    BackHandler(enabled = paneNavController.previousBackStackEntry != null) {\n        paneNavController.popBackStack()\n    }",
        "android source handover",
    )
    text = replace_once(
        text,
        "        val returnToQueue: () -> Unit = {\n            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {",
        "        val returnToQueue: () -> Unit = {\n            if (physicalRadio.state.value.isActive) physicalRadio.powerOff()\n            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {",
        "song selection handover",
    )
    text = replace_once(
        text,
        "        Column(\n            horizontalAlignment = Alignment.CenterHorizontally,\n            modifier =\n                Modifier\n                    .weight(safePlayerWeight)\n                    .fillMaxSize()\n                    .padding(horizontal = 12.dp, vertical = 4.dp)\n                    .nestedScroll(state.preUpPostDownNestedScrollConnection),\n        ) {\n            Box(\n                contentAlignment = Alignment.Center,\n                modifier =\n                    Modifier\n                        .weight(1f)\n                        .fillMaxWidth()\n                        .padding(top = 2.dp, bottom = 2.dp)\n                        .clickable(onClick = onToggleLyrics),\n            ) {\n                thumbnailContent()\n            }\n            controlsContent()\n            Spacer(Modifier.height(2.dp))\n        }",
        "        Column(\n            horizontalAlignment = Alignment.CenterHorizontally,\n            modifier =\n                Modifier\n                    .weight(safePlayerWeight)\n                    .fillMaxSize()\n                    .padding(horizontal = 12.dp, vertical = 4.dp)\n                    .nestedScroll(state.preUpPostDownNestedScrollConnection),\n        ) {\n            if (physicalRadioState.isActive) {\n                PhysicalRadioPlayerPane(\n                    radio = physicalRadio,\n                    playerConnection = playerConnection,\n                )\n            } else {\n                Box(\n                    contentAlignment = Alignment.Center,\n                    modifier =\n                        Modifier\n                            .weight(1f)\n                            .fillMaxWidth()\n                            .padding(top = 2.dp, bottom = 2.dp)\n                            .clickable(onClick = onToggleLyrics),\n                ) {\n                    thumbnailContent()\n                }\n                controlsContent()\n                Spacer(Modifier.height(2.dp))\n            }\n        }",
        "unified physical radio player",
    )
    text = replace_once(
        text,
        "                                composable(VEHICLE_WEBRADIO_ROUTE) {\n                                    WebRadioScreen()\n                                }",
        "                                composable(VEHICLE_PHYSICAL_RADIO_ROUTE) {\n                                    PhysicalRadioScreen()\n                                }\n                                composable(VEHICLE_WEBRADIO_ROUTE) {\n                                    WebRadioScreen()\n                                }",
        "physical radio nav destination",
    )

    LAYOUT.write_text(text, encoding="utf-8")


def patch_manifest() -> None:
    text = MANIFEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />',
        "audio permission",
    )
    text = replace_once(
        text,
        "    <queries>\n        <intent>",
        "    <queries>\n        <package android:name=\"com.syu.ms\" />\n        <package android:name=\"com.syu.music\" />\n        <package android:name=\"com.syu.ss\" />\n        <intent>",
        "FYT package visibility",
    )
    MANIFEST.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_layout()
    patch_manifest()
    print("Dudu7 physical radio integration applied")
