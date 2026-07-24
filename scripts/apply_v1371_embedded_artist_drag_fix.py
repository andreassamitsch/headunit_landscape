#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:200]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


artist = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    artist,
    "import androidx.compose.foundation.combinedClickable\n",
    "import androidx.compose.foundation.combinedClickable\nimport androidx.compose.foundation.gestures.detectVerticalDragGestures\n",
)
replace_once(
    artist,
    '''            modifier = Modifier.fillMaxSize(),
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
            userScrollEnabled = true,''',
    '''            modifier =
                Modifier
                    .fillMaxSize()
                    .then(
                        if (embeddedInPlayer) {
                            Modifier.pointerInput(lazyListState) {
                                detectVerticalDragGestures { change, dragAmount ->
                                    change.consume()
                                    lazyListState.dispatchRawDelta(-dragAmount)
                                }
                            }
                        } else {
                            Modifier
                        },
                    ),
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
            userScrollEnabled = true,''',
)

# The embedded artist now owns its vertical drag sequence, so the obsolete
# outer sheet nested-scroll bridge must not take part in gesture arbitration.
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
    '''                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .nestedScroll(state.preUpPostDownNestedScrollConnection)
                    .padding(start = 6.dp, end = 8.dp),''',
    '''                    .weight(1f - safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 6.dp, end = 8.dp),''',
)
