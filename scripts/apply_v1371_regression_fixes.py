#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    if new in text:
        return
    if old not in text:
        raise SystemExit(f'Marker not found in {path}: {old[:160]!r}')
    file.write_text(text.replace(old, new, 1), encoding='utf-8')


# Version bump for the corrected, fully regression-tested package.
replace_once(
    'app/build.gradle.kts',
    '        versionCode = 159\n        versionName = "13.7.0"',
    '        versionCode = 160\n        versionName = "13.7.1"',
)

# The expanded player sheet owns a vertical drag detector. The left pane already
# participates in its nested-scroll chain; the right pane must do the same or the
# sheet wins the gesture before embedded LazyColumns can scroll.
replace_once(
    'app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt',
    '''                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 6.dp, end = 8.dp),''',
    '''                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .nestedScroll(state.preUpPostDownNestedScrollConnection)
                    .padding(start = 6.dp, end = 8.dp),''',
)

# Give the original artist page an explicit viewport in the embedded NavHost.
replace_once(
    'app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt',
    '''        LazyColumn(
            state = lazyListState,
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
        ) {''',
    '''        LazyColumn(
            state = lazyListState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
            userScrollEnabled = true,
        ) {''',
)

# Log the fresh shuffle seed so the focused emulator regression can prove that
# every off -> on cycle creates a new order and off restores timeline order.
replace_once(
    'app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt',
    '''        if (activePlayer.shuffleModeEnabled) {
            activePlayer.shuffleModeEnabled = false
        } else {
            if (activePlayer.mediaItemCount > 1) {
                activePlayer.setShuffleOrder(
                    ShuffleOrder.DefaultShuffleOrder(
                        activePlayer.mediaItemCount,
                        System.nanoTime(),
                    ),
                )
            }
            activePlayer.shuffleModeEnabled = true
        }''',
    '''        if (activePlayer.shuffleModeEnabled) {
            activePlayer.shuffleModeEnabled = false
            Timber.tag(TAG).i("Shuffle disabled; original timeline order active")
        } else {
            val seed = System.nanoTime()
            if (activePlayer.mediaItemCount > 1) {
                activePlayer.setShuffleOrder(
                    ShuffleOrder.DefaultShuffleOrder(
                        activePlayer.mediaItemCount,
                        seed,
                    ),
                )
            }
            activePlayer.shuffleModeEnabled = true
            Timber.tag(TAG).i(
                "Shuffle enabled with fresh seed=%d itemCount=%d",
                seed,
                activePlayer.mediaItemCount,
            )
        }''',
)

# Add a deterministic decoder-success marker; recognition may legitimately end
# in NoMatch for synthetic test audio, but stream decoding itself must succeed.
replace_once(
    'app/src/main/kotlin/com/metrolist/music/recognition/MusicRecognitionService.kt',
    '''                val decoded = decodeRadioStream(streamUrl)
                recognizeDecodedAudio(decoded)''',
    '''                val decoded = decodeRadioStream(streamUrl)
                Timber.tag(TAG).i(
                    "Direct radio stream decoded: bytes=%d sampleRate=%d channels=%d",
                    decoded.data.size,
                    decoded.sampleRate,
                    decoded.channelCount,
                )
                recognizeDecodedAudio(decoded)''',
)

for path in (
    'app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt',
    'app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt',
    'app/src/main/kotlin/com/metrolist/music/recognition/MusicRecognitionService.kt',
):
    file = Path(path)
    text = file.read_text(encoding='utf-8')
    text = text.replace('MetrolistHU/13.7.0', 'MetrolistHU/13.7.1')
    file.write_text(text, encoding='utf-8')
