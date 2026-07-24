#!/usr/bin/env python3
from pathlib import Path


def ensure_after(text: str, marker: str, addition: str, label: str) -> str:
    if addition in text:
        return text
    if marker not in text:
        raise SystemExit(f"Missing {label} marker")
    return text.replace(marker, marker + addition, 1)


vehicle_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
vehicle = vehicle_path.read_text(encoding="utf-8")

vehicle = ensure_after(
    vehicle,
    "import androidx.compose.ui.Alignment\n",
    "import androidx.compose.ui.geometry.Offset\n",
    "VehicleLandscapeLayout Alignment import",
)
vehicle = ensure_after(
    vehicle,
    "import androidx.compose.ui.geometry.Offset\n",
    "import androidx.compose.ui.input.pointer.PointerEventPass\nimport androidx.compose.ui.input.pointer.pointerInput\n",
    "VehicleLandscapeLayout pointer imports",
)
vehicle = ensure_after(
    vehicle,
    "import com.metrolist.music.ui.component.BottomSheetState\n",
    "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\nimport com.metrolist.music.ui.component.RightPaneScrollBridge\n",
    "VehicleLandscapeLayout component imports",
)
vehicle = ensure_after(
    vehicle,
    "import kotlin.math.max\n",
    "import kotlin.math.abs\n",
    "VehicleLandscapeLayout math import",
)

bridge_state = "    val rightPaneScrollBridge = remember { RightPaneScrollBridge() }\n"
if bridge_state not in vehicle:
    marker = "    val rightPaneScope = rememberCoroutineScope()\n"
    if marker not in vehicle:
        raise SystemExit("VehicleLandscapeLayout rightPaneScope marker missing")
    vehicle = vehicle.replace(marker, marker + bridge_state, 1)

old_box = """                    Box(Modifier.weight(1f).fillMaxWidth()) {
"""
new_box = """                    Box(
                        modifier =
                            Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .pointerInput(currentPaneRoute, rightPaneScrollBridge.handler) {
                                    val scrollHandler = rightPaneScrollBridge.handler ?: return@pointerInput
                                    awaitPointerEventScope {
                                        var lastPosition: Offset? = null
                                        var accumulatedX = 0f
                                        var accumulatedY = 0f
                                        var verticalDrag = false
                                        while (true) {
                                            val event = awaitPointerEvent(PointerEventPass.Initial)
                                            val change = event.changes.firstOrNull()
                                            if (change == null || !change.pressed) {
                                                if (verticalDrag) {
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag ended route=%s",
                                                        currentPaneRoute,
                                                    )
                                                }
                                                lastPosition = null
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                                continue
                                            }
                                            if (!change.previousPressed || lastPosition == null) {
                                                lastPosition = change.position
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                                continue
                                            }
                                            val previous = lastPosition ?: change.position
                                            val delta = change.position - previous
                                            lastPosition = change.position
                                            accumulatedX += delta.x
                                            accumulatedY += delta.y
                                            if (
                                                !verticalDrag &&
                                                abs(accumulatedY) > viewConfiguration.touchSlop &&
                                                abs(accumulatedY) > abs(accumulatedX)
                                            ) {
                                                verticalDrag = true
                                                Timber.tag("Dudu7RightPaneScroll").i(
                                                    "Right-pane vertical drag started route=%s",
                                                    currentPaneRoute,
                                                )
                                            }
                                            if (verticalDrag) {
                                                change.consume()
                                                scrollHandler(-delta.y)
                                            }
                                        }
                                    }
                                },
                    ) {
"""
if "Dudu7RightPaneScroll" not in vehicle:
    if old_box not in vehicle:
        raise SystemExit("VehicleLandscapeLayout right pane content Box marker missing")
    vehicle = vehicle.replace(old_box, new_box, 1)

provider_marker = """                    LocalNavController provides paneNavController,
"""
provider_addition = """                    LocalRightPaneScrollBridge provides rightPaneScrollBridge,
"""
if provider_addition not in vehicle:
    if provider_marker not in vehicle:
        raise SystemExit("VehicleLandscapeLayout CompositionLocalProvider marker missing")
    vehicle = vehicle.replace(provider_marker, provider_marker + provider_addition, 1)

vehicle_path.write_text(vehicle, encoding="utf-8")


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

artist = ensure_after(
    artist,
    "import androidx.compose.runtime.Composable\n",
    "import androidx.compose.runtime.DisposableEffect\n",
    "ArtistScreen Composable import",
)
artist = ensure_after(
    artist,
    "import com.metrolist.music.ui.component.LocalMenuState\n",
    "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n",
    "ArtistScreen component import",
)

bridge_vars = """    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
"""
if bridge_vars not in artist:
    marker = "    val lazyListState = rememberLazyListState()\n"
    if marker not in artist:
        raise SystemExit("ArtistScreen LazyListState marker missing")
    artist = artist.replace(marker, marker + bridge_vars, 1)

registration = """    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(rightPaneScrollOwner) { delta ->
                lazyListState.dispatchRawDelta(delta)
            }
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
        }
    }

"""
if registration not in artist:
    marker = """    LaunchedEffect(libraryArtist) {
        // always show local page for local artists. Show local page remote artist when offline
        showLocal = libraryArtist?.artist?.isLocal == true
    }

"""
    if marker not in artist:
        raise SystemExit("ArtistScreen library artist effect marker missing")
    artist = artist.replace(marker, marker + registration, 1)

# Remove the unsuccessful screen-local pointer handler. The fixed right pane now
# owns vertical gesture arbitration and forwards only vertical deltas to this list.
root_start = artist.find("    BoxWithConstraints(\n        modifier =\n            Modifier\n")
root_end_marker = "    ) {\n        val embeddedPaneWidth = maxWidth\n"
if root_start >= 0:
    root_end = artist.find(root_end_marker, root_start)
    if root_end < 0:
        raise SystemExit("ArtistScreen custom BoxWithConstraints end marker missing")
    root_end += len("    ) {\n")
    artist = artist[:root_start] + "    BoxWithConstraints(\n        modifier = Modifier.fillMaxSize(),\n    ) {\n" + artist[root_end:]

if "            userScrollEnabled = !embeddedInPlayer," not in artist:
    artist = artist.replace(
        "            userScrollEnabled = true,",
        "            userScrollEnabled = !embeddedInPlayer,",
        1,
    )
if "            userScrollEnabled = !embeddedInPlayer," not in artist:
    raise SystemExit("ArtistScreen embedded userScrollEnabled setting missing")

artist_path.write_text(artist, encoding="utf-8")

print("Applied Dudu7 right-pane scroll bridge")
