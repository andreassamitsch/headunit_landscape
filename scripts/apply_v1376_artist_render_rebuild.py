#!/usr/bin/env python3
from pathlib import Path


def ensure_after(text: str, marker: str, addition: str, label: str) -> str:
    if addition in text:
        return text
    if marker not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(marker, marker + addition, 1)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


bridge_path = Path("app/src/main/kotlin/com/metrolist/music/ui/component/RightPaneScrollBridge.kt")
bridge = bridge_path.read_text(encoding="utf-8")
bridge = ensure_after(
    bridge,
    """    var tapHandler: ((Offset) -> Boolean)? by mutableStateOf(null)
        private set
""",
    """
    var scrollEndHandler: (() -> Unit)? by mutableStateOf(null)
        private set
""",
    "RightPaneScrollBridge scroll end property",
)
bridge = replace_once(
    bridge,
    """        handler: ((Float) -> Unit)?,
        tapHandler: ((Offset) -> Boolean)? = null,
    ) {
        this.owner = owner
        this.handler = handler
        this.tapHandler = tapHandler
""",
    """        handler: ((Float) -> Unit)?,
        tapHandler: ((Offset) -> Boolean)? = null,
        scrollEndHandler: (() -> Unit)? = null,
    ) {
        this.owner = owner
        this.handler = handler
        this.tapHandler = tapHandler
        this.scrollEndHandler = scrollEndHandler
""",
    "RightPaneScrollBridge register end handler",
)
bridge = ensure_after(
    bridge,
    """    fun dispatchTap(positionInRoot: Offset): Boolean = tapHandler?.invoke(positionInRoot) == true
""",
    """
    fun dispatchScrollEnd() {
        scrollEndHandler?.invoke()
    }
""",
    "RightPaneScrollBridge dispatch scroll end",
)
bridge = replace_once(
    bridge,
    """            handler = null
            tapHandler = null
""",
    """            handler = null
            tapHandler = null
            scrollEndHandler = null
""",
    "RightPaneScrollBridge unregister end handler",
)
bridge_path.write_text(bridge, encoding="utf-8")


vehicle_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
vehicle = vehicle_path.read_text(encoding="utf-8")
vehicle = replace_once(
    vehicle,
    """                                    rightPaneScrollBridge.handler,
                                    rightPaneScrollBridge.tapHandler,
""",
    """                                    rightPaneScrollBridge.handler,
                                    rightPaneScrollBridge.tapHandler,
                                    rightPaneScrollBridge.scrollEndHandler,
""",
    "VehicleLandscapeLayout pointer key end handler",
)
vehicle = replace_once(
    vehicle,
    """                                                if (verticalDrag) {
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag ended route=%s",
                                                        currentPaneRoute,
                                                    )
""",
    """                                                if (verticalDrag) {
                                                    rightPaneScrollBridge.dispatchScrollEnd()
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag ended route=%s",
                                                        currentPaneRoute,
                                                    )
""",
    "VehicleLandscapeLayout dispatch scroll end",
)
vehicle_path.write_text(vehicle, encoding="utf-8")


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")
artist = ensure_after(
    artist,
    "import androidx.compose.foundation.combinedClickable\n",
    "import androidx.compose.foundation.gestures.scrollBy\n",
    "ArtistScreen scrollBy import",
)
artist = ensure_after(
    artist,
    "import androidx.compose.runtime.getValue\n",
    "import androidx.compose.runtime.key\nimport androidx.compose.runtime.mutableIntStateOf\n",
    "ArtistScreen render revision imports",
)
artist = ensure_after(
    artist,
    "import kotlinx.coroutines.launch\n",
    "import kotlinx.coroutines.channels.Channel\n",
    "ArtistScreen Channel import",
)
artist = replace_once(
    artist,
    """    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
""",
    """    val rightPaneScrollOwner = remember { Any() }
    val rightPaneScrollDeltas = remember { Channel<Float>(Channel.UNLIMITED) }
    var artistRenderRevision by remember { mutableIntStateOf(0) }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
""",
    "ArtistScreen render revision state",
)
artist = replace_once(
    artist,
    """    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
""",
    """    LaunchedEffect(embeddedInPlayer, lazyListState, rightPaneScrollDeltas) {
        if (embeddedInPlayer) {
            for (delta in rightPaneScrollDeltas) {
                lazyListState.scrollBy(delta)
            }
        }
    }

    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
""",
    "ArtistScreen parent scroll collector",
)
artist = replace_once(
    artist,
    """                // The embedded LazyColumn must own its vertical scroll. Parent-driven
                // scrollBy/dispatchRawDelta updated semantics but produced a fully white
                // rendered pane on the Dudu7. The bridge remains registered for taps only.
                handler = null,
                tapHandler = { positionInRoot ->
""",
    """                handler = { delta ->
                    rightPaneScrollDeltas.trySend(delta.coerceIn(-160f, 160f))
                },
                tapHandler = { positionInRoot ->
""",
    "ArtistScreen restore parent scroll handler",
)
artist = replace_once(
    artist,
    """                    } else {
                        false
                    }
                },
            )
""",
    """                    } else {
                        false
                    }
                },
                scrollEndHandler = {
                    // The Dudu7 could update LazyList semantics while leaving its old
                    // graphics tree empty. Re-keying recreates only the LazyColumn draw
                    // tree; the remembered LazyListState keeps the exact scroll position.
                    artistRenderRevision += 1
                    timber.log.Timber.tag("Dudu7ArtistRender").i(
                        "Rebuilding artist list after drag revision=%d index=%d offset=%d",
                        artistRenderRevision,
                        lazyListState.firstVisibleItemIndex,
                        lazyListState.firstVisibleItemScrollOffset,
                    )
                },
            )
""",
    "ArtistScreen scroll end rebuild callback",
)
artist = replace_once(
    artist,
    """        val embeddedPaneWidth = maxWidth
        LazyColumn(
""",
    """        val embeddedPaneWidth = maxWidth
        key(artistRenderRevision) {
            LazyColumn(
""",
    "ArtistScreen keyed LazyColumn start",
)
artist = replace_once(
    artist,
    """            userScrollEnabled = true,
""",
    """            userScrollEnabled = !embeddedInPlayer,
""",
    "ArtistScreen parent controlled embedded scroll",
)
artist = replace_once(
    artist,
    """        }

        val isScrollingUp = lazyListState.isScrollingUp()
""",
    """        }
        }

        val isScrollingUp = lazyListState.isScrollingUp()
""",
    "ArtistScreen keyed LazyColumn end",
)

required = (
    "key(artistRenderRevision)",
    "scrollEndHandler = {",
    "artistRenderRevision += 1",
    "lazyListState.scrollBy(delta)",
    "userScrollEnabled = !embeddedInPlayer",
)
for marker in required:
    if marker not in artist:
        raise SystemExit(f"Artist render rebuild marker missing: {marker}")
artist_path.write_text(artist, encoding="utf-8")
print("Added parent scroll completion rebuild for the embedded artist LazyColumn")
