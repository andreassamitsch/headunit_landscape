from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))


# 1) Dudu7 manifest: allow portrait/freeform and let Compose handle size/orientation
# changes without recreating the Activity/service binding on every resize.
replace_once(
    "app/src/dudu7/AndroidManifest.xml",
    '''        <activity\n            android:name=".MainActivity"\n            android:screenOrientation="landscape" />''',
    '''        <activity\n            android:name=".MainActivity"\n            android:configChanges="orientation|screenSize|smallestScreenSize|screenLayout" />''',
)

# 2) Dudu7 adaptive layout: use actual window/container geometry. This also works
# for portrait-shaped floating/freeform windows where physical device orientation
# can still be landscape.
layout = "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(layout, "import android.content.res.Configuration\n", "")
replace_once(layout, "import androidx.compose.ui.platform.LocalConfiguration\n", "")
replace_once(
    layout,
    "import androidx.compose.ui.platform.LocalHapticFeedback\n",
    "import androidx.compose.ui.platform.LocalHapticFeedback\nimport androidx.compose.ui.platform.LocalWindowInfo\n",
)
replace_once(
    layout,
    "    val isPortrait = LocalConfiguration.current.orientation == Configuration.ORIENTATION_PORTRAIT\n",
    "    val windowSize = LocalWindowInfo.current.containerDpSize\n"
    "    val isPortrait = windowSize.height > windowSize.width\n",
)

# 3) PlayerConnection: do not start the RadioStationStore collector before the
# StateFlows it reads/writes have been initialized. StateFlow.collect can emit
# synchronously on Main.immediate during a fast service reconnect.
player = "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt"
early_collector = '''        scope.launch {\n            radioStationStore.stations.collect {\n                if (isRadioMediaId(getPlayerOrNull()?.currentMediaItem?.mediaId)) {\n                    val stableMetadata = withStoredRadioArtwork(mediaMetadata.value)\n                    if (stableMetadata != mediaMetadata.value) mediaMetadata.value = stableMetadata\n                    updateCanSkipPreviousAndNext()\n                }\n            }\n        }\n'''
replace_once(player, early_collector, "")
late_init = '''    init {\n        scope.launch {\n            service.playerFlow.collect { newPlayer ->\n'''
late_init_replacement = '''    init {\n        // All StateFlows used by this collector are initialized above this point.\n        // Keep it here so an immediate StateFlow emission during service reconnect\n        // cannot observe a partially constructed PlayerConnection.\n        scope.launch {\n            radioStationStore.stations.collect {\n                if (isRadioMediaId(getPlayerOrNull()?.currentMediaItem?.mediaId)) {\n                    val stableMetadata = withStoredRadioArtwork(mediaMetadata.value)\n                    if (stableMetadata != mediaMetadata.value) mediaMetadata.value = stableMetadata\n                    updateCanSkipPreviousAndNext()\n                }\n            }\n        }\n        scope.launch {\n            service.playerFlow.collect { newPlayer ->\n'''
replace_once(player, late_init, late_init_replacement)

# 4) Version bump.
replace_once("app/build.gradle.kts", "versionCode = 1370073", "versionCode = 1370074")
replace_once("app/build.gradle.kts", 'versionName = "13.7.64"', 'versionName = "13.7.65"')

print("Applied Issues #124/#126 portrait + resize/reconnect fixes")
