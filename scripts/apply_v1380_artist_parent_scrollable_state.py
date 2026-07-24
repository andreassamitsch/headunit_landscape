#!/usr/bin/env python3
from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(old, new, 1)


# 1) Extend the owner-scoped bridge with a real Compose ScrollableState.
bridge_path = Path("app/src/main/kotlin/com/metrolist/music/ui/component/RightPaneScrollBridge.kt")
bridge = bridge_path.read_text(encoding="utf-8")
if "import androidx.compose.foundation.gestures.ScrollableState\n" not in bridge:
    bridge = bridge.replace(
        "package com.metrolist.music.ui.component\n\n",
        "package com.metrolist.music.ui.component\n\nimport androidx.compose.foundation.gestures.ScrollableState\n",
        1,
    )
bridge = replace_once(
    bridge,
    '''    var scrollEndHandler: (() -> Unit)? by mutableStateOf(null)
        private set
''',
    '''    var scrollEndHandler: (() -> Unit)? by mutableStateOf(null)
        private set

    var scrollableState: ScrollableState? by mutableStateOf(null)
        private set
''',
    "bridge scrollable state property",
)
bridge = replace_once(
    bridge,
    '''        tapHandler: ((Offset) -> Boolean)? = null,
        scrollEndHandler: (() -> Unit)? = null,
    ) {
''',
    '''        tapHandler: ((Offset) -> Boolean)? = null,
        scrollEndHandler: (() -> Unit)? = null,
        scrollableState: ScrollableState? = null,
    ) {
''',
    "bridge register scrollable argument",
)
bridge = replace_once(
    bridge,
    '''        this.tapHandler = tapHandler
        this.scrollEndHandler = scrollEndHandler
''',
    '''        this.tapHandler = tapHandler
        this.scrollEndHandler = scrollEndHandler
        this.scrollableState = scrollableState
''',
    "bridge scrollable assignment",
)
bridge = replace_once(
    bridge,
    '''            tapHandler = null
            scrollEndHandler = null
''',
    '''            tapHandler = null
            scrollEndHandler = null
            scrollableState = null
''',
    "bridge scrollable cleanup",
)
bridge_path.write_text(bridge, encoding="utf-8")


# 2) Register the original ArtistScreen LazyListState with the bridge. The
# LazyColumn itself stays non-user-scrollable only in the embedded pane, because
# the parent modifier will now own the gesture using this exact state.
artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")
artist = artist.replace("import androidx.compose.foundation.gestures.Orientation\n", "")
artist = artist.replace("import androidx.compose.foundation.gestures.scrollable\n", "")
if "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n" not in artist:
    artist = artist.replace(
        "import com.metrolist.music.ui.component.LocalMenuState\n",
        "import com.metrolist.music.ui.component.LocalMenuState\n"
        "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n",
        1,
    )
artist = replace_once(
    artist,
    '''    val lazyListState = rememberLazyListState()
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
''',
    '''    val lazyListState = rememberLazyListState()
    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }
''',
    "artist scroll bridge declarations",
)
registration = '''
    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = null,
                tapHandler = null,
                scrollEndHandler = null,
                scrollableState = lazyListState,
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
        }
    }
'''
if registration not in artist:
    marker = '''    LaunchedEffect(artistPage?.artist?.id) {
        rightPaneTapTargets.clear()
    }
'''
    if marker not in artist:
        raise SystemExit("Artist target cleanup effect marker missing")
    artist = artist.replace(marker, registration + "\n" + marker, 1)
old_root = '''    BoxWithConstraints(
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
    ) {'''
new_root = '''    BoxWithConstraints(
        modifier = Modifier.fillMaxSize(),
    ) {'''
artist = replace_once(artist, old_root, new_root, "artist root scrollable removal")
if "scrollableState = lazyListState" not in artist:
    raise SystemExit("Artist LazyListState registration missing")
if "userScrollEnabled = !embeddedInPlayer" not in artist:
    raise SystemExit("Artist embedded LazyColumn ownership setting missing")
artist_path.write_text(artist, encoding="utf-8")


# 3) For artist routes, use Compose's standard scrollable modifier on the fixed
# right-pane container. Other tabs retain their existing custom pointer bridge.
layout_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
layout = layout_path.read_text(encoding="utf-8")
if "import androidx.compose.foundation.gestures.Orientation\n" not in layout:
    layout = layout.replace(
        "import androidx.compose.foundation.clickable\n",
        "import androidx.compose.foundation.clickable\n"
        "import androidx.compose.foundation.gestures.Orientation\n"
        "import androidx.compose.foundation.gestures.scrollable\n",
        1,
    )
old_artist_branch = '''                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        // Do not attach the Dudu7 pane's custom pointer modifier at all.
                                        // A pointerInput modifier whose coroutine returns immediately still
                                        // participates in hit testing and prevented the original ArtistScreen
                                        // LazyColumn/FABs from receiving the complete gesture stream.
                                        // The player's original nested-scroll connection is on the left player
                                        // column and remains unchanged.
                                        Modifier
                                    } else {
'''
new_artist_branch = '''                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        rightPaneScrollBridge.scrollableState?.let { artistScrollState ->
                                            Modifier.scrollable(
                                                state = artistScrollState,
                                                orientation = Orientation.Vertical,
                                            )
                                        } ?: Modifier
                                    } else {
'''
layout = replace_once(layout, old_artist_branch, new_artist_branch, "artist parent scrollable branch")
if ".nestedScroll(state.preUpPostDownNestedScrollConnection)" not in layout:
    raise SystemExit("Original player nested-scroll connection was lost")
if "rightPaneScrollBridge.scrollableState" not in layout:
    raise SystemExit("Parent artist ScrollableState binding missing")
layout_path.write_text(layout, encoding="utf-8")

print("Bound embedded ArtistScreen LazyListState to a parent Compose scrollable while preserving Player nested scroll")
