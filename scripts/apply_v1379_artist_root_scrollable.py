#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

# Use Compose's gesture/scroll machinery directly on the artist root. This keeps
# the Player's own nested-scroll behavior untouched and avoids manually feeding
# pointer deltas into LazyListState, which updated semantics but left the rendered
# artist body blank on the Dudu7.
artist = artist.replace("import androidx.compose.foundation.gestures.scrollBy\n", "")
if "import androidx.compose.foundation.gestures.Orientation\n" not in artist:
    artist = artist.replace(
        "import androidx.compose.foundation.combinedClickable\n",
        "import androidx.compose.foundation.combinedClickable\n"
        "import androidx.compose.foundation.gestures.Orientation\n"
        "import androidx.compose.foundation.gestures.scrollable\n",
        1,
    )
for obsolete in (
    "import androidx.compose.runtime.key\n",
    "import androidx.compose.runtime.mutableIntStateOf\n",
    "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n",
    "import kotlinx.coroutines.channels.Channel\n",
):
    artist = artist.replace(obsolete, "")

old_declarations = '''    val lazyListState = rememberLazyListState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneScrollDeltas = remember { Channel<Float>(Channel.UNLIMITED) }
    var artistRenderRevision by remember { mutableIntStateOf(0) }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
'''
new_declarations = '''    val lazyListState = rememberLazyListState()
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
'''
artist = replace_once(artist, old_declarations, new_declarations, "artist bridge declarations")

bridge_start = artist.find("    LaunchedEffect(embeddedInPlayer, lazyListState, rightPaneScrollDeltas) {")
bridge_end_marker = '''    LaunchedEffect(artistPage?.artist?.id) {
        rightPaneTapTargets.clear()
    }
'''
bridge_end = artist.find(bridge_end_marker, bridge_start)
if bridge_start < 0 or bridge_end < 0:
    raise SystemExit("Artist manual scroll bridge block missing")
# Keep the target cleanup effect; normal Compose clicks now handle the actions.
artist = artist[:bridge_start] + bridge_end_marker + artist[bridge_end + len(bridge_end_marker):]

old_root = '''    BoxWithConstraints(
        modifier = Modifier.fillMaxSize(),
    ) {
        val embeddedPaneWidth = maxWidth
        key(artistRenderRevision) {
            LazyColumn(
            state = lazyListState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
            userScrollEnabled = true,
        ) {'''
new_root = '''    BoxWithConstraints(
        modifier =
            Modifier
                .fillMaxSize()
                .then(
                    if (embeddedInPlayer) {
                        Modifier.scrollable(
                            state = lazyListState,
                            orientation = Orientation.Vertical,
                        )
                    } else {
                        Modifier
                    },
                ),
    ) {
        val embeddedPaneWidth = maxWidth
        LazyColumn(
            state = lazyListState,
            modifier = Modifier.fillMaxSize(),
            contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
            userScrollEnabled = !embeddedInPlayer,
        ) {'''
artist = replace_once(artist, old_root, new_root, "artist root scrollable")

# Remove the extra brace that belonged to key(artistRenderRevision).
old_close = '''            }
        }
        }

        val isScrollingUp = lazyListState.isScrollingUp()'''
new_close = '''            }
        }

        val isScrollingUp = lazyListState.isScrollingUp()'''
artist = replace_once(artist, old_close, new_close, "artist render key closing brace")

for forbidden in (
    "rightPaneScrollDeltas",
    "artistRenderRevision",
    "LocalRightPaneScrollBridge",
    "lazyListState.scrollBy(",
    "key(artistRenderRevision)",
):
    if forbidden in artist:
        raise SystemExit(f"Obsolete artist scroll workaround remains: {forbidden}")
if "Modifier.scrollable(" not in artist or "userScrollEnabled = !embeddedInPlayer" not in artist:
    raise SystemExit("Artist root scrollable configuration missing")

artist_path.write_text(artist, encoding="utf-8")

smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")
# Swipe in the left/center part of the right pane, away from the Play All FAB and
# horizontal carousels. The old 82% coordinate could land on interactive children.
smoke = smoke.replace(
    "adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*24/100)) 500",
    "adb shell input swipe $((DUDU_WIDTH*70/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*70/100)) $((DUDU_HEIGHT*24/100)) 500",
    1,
)
smoke = smoke.replace(
    "adb shell input swipe $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*82/100)) $((DUDU_HEIGHT*20/100)) 350",
    "adb shell input swipe $((DUDU_WIDTH*70/100)) $((DUDU_HEIGHT*86/100)) $((DUDU_WIDTH*70/100)) $((DUDU_HEIGHT*20/100)) 350",
    1,
)
smoke_path.write_text(smoke, encoding="utf-8")

print("Applied root-level Compose scrollable to embedded ArtistScreen and moved test swipes away from child controls")
