#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


bridge_path = Path("app/src/main/kotlin/com/metrolist/music/ui/component/RightPaneScrollBridge.kt")
bridge = bridge_path.read_text(encoding="utf-8")
bridge = replace_once(
    bridge,
    """        handler: (Float) -> Unit,
""",
    """        handler: ((Float) -> Unit)?,
""",
    "RightPaneScrollBridge nullable handler",
)
bridge_path.write_text(bridge, encoding="utf-8")


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")
artist = artist.replace("import androidx.compose.foundation.gestures.scrollBy\n", "")
artist = artist.replace("import kotlinx.coroutines.channels.Channel\n", "")
artist = artist.replace(
    """    val rightPaneScrollDeltas = remember { Channel<Float>(Channel.UNLIMITED) }
""",
    "",
)

collector = """    LaunchedEffect(embeddedInPlayer, lazyListState, rightPaneScrollDeltas) {
        if (embeddedInPlayer) {
            for (delta in rightPaneScrollDeltas) {
                // scrollBy uses the normal LazyList bounds calculation. The former
                // dispatchRawDelta path could move the measured content completely
                // outside the pane and leave an all-white artist page on real units.
                lazyListState.scrollBy(delta)
            }
        }
    }

"""
artist = artist.replace(collector, "")

old_handler = """                handler = { delta ->
                    // A single malformed pointer delta must never jump beyond the
                    // complete list. Normal gestures arrive as many smaller deltas.
                    rightPaneScrollDeltas.trySend(delta.coerceIn(-160f, 160f))
                },
"""
artist = replace_once(
    artist,
    old_handler,
    """                // The embedded LazyColumn must own its vertical scroll. Parent-driven
                // scrollBy/dispatchRawDelta updated semantics but produced a fully white
                // rendered pane on the Dudu7. The bridge remains registered for taps only.
                handler = null,
""",
    "ArtistScreen tap-only bridge registration",
)
artist = replace_once(
    artist,
    """            userScrollEnabled = !embeddedInPlayer,
""",
    """            userScrollEnabled = true,
""",
    "ArtistScreen native scrolling",
)

for obsolete in (
    "rightPaneScrollDeltas",
    "lazyListState.scrollBy(delta)",
    "lazyListState.dispatchRawDelta(delta)",
    "userScrollEnabled = !embeddedInPlayer",
):
    if obsolete in artist:
        raise SystemExit(f"Obsolete parent-driven artist scroll remains: {obsolete}")
if "handler = null" not in artist or "userScrollEnabled = true" not in artist:
    raise SystemExit("Native artist scroll conversion incomplete")
artist_path.write_text(artist, encoding="utf-8")
print("Converted embedded artist page to native LazyColumn scrolling with tap-only parent bridge")
