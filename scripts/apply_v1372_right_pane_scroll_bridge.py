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
    "import androidx.compose.ui.input.pointer.pointerInput\n",
    "import androidx.compose.ui.layout.onGloballyPositioned\nimport androidx.compose.ui.layout.positionInRoot\n",
    "VehicleLandscapeLayout layout coordinate imports",
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
origin_state = "    var rightPaneOriginInRoot by remember { mutableStateOf(Offset.Zero) }\n"
if origin_state not in vehicle:
    vehicle = vehicle.replace(bridge_state, bridge_state + origin_state, 1)

old_box = '''                    Box(Modifier.weight(1f).fillMaxWidth()) {
'''
previous_box = '''                    Box(
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
'''
final_box = '''                    Box(
                        modifier =
                            Modifier
                                .weight(1f)
                                .fillMaxWidth()
                                .onGloballyPositioned { coordinates ->
                                    rightPaneOriginInRoot = coordinates.positionInRoot()
                                }
                                .pointerInput(
                                    currentPaneRoute,
                                    rightPaneScrollBridge.handler,
                                    rightPaneScrollBridge.tapHandler,
                                ) {
                                    val scrollHandler = rightPaneScrollBridge.handler
                                    awaitPointerEventScope {
                                        var downPosition: Offset? = null
                                        var lastPosition: Offset? = null
                                        var accumulatedX = 0f
                                        var accumulatedY = 0f
                                        var verticalDrag = false
                                        while (true) {
                                            val event = awaitPointerEvent(PointerEventPass.Initial)
                                            val change = event.changes.firstOrNull() ?: continue
                                            if (change.pressed && !change.previousPressed) {
                                                downPosition = change.position
                                                lastPosition = change.position
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                                continue
                                            }
                                            if (change.pressed) {
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
                                                if (verticalDrag && scrollHandler != null) {
                                                    change.consume()
                                                    scrollHandler(-delta.y)
                                                }
                                                continue
                                            }
                                            if (change.previousPressed) {
                                                if (verticalDrag) {
                                                    Timber.tag("Dudu7RightPaneScroll").i(
                                                        "Right-pane vertical drag ended route=%s",
                                                        currentPaneRoute,
                                                    )
                                                } else {
                                                    val start = downPosition
                                                    val moved =
                                                        start == null ||
                                                            (change.position - start).getDistance() > viewConfiguration.touchSlop
                                                    if (!moved) {
                                                        val positionInRoot = rightPaneOriginInRoot + change.position
                                                        val handled = rightPaneScrollBridge.dispatchTap(positionInRoot)
                                                        Timber.tag("Dudu7RightPaneTap").i(
                                                            "Right-pane tap route=%s x=%.1f y=%.1f handled=%s",
                                                            currentPaneRoute,
                                                            positionInRoot.x,
                                                            positionInRoot.y,
                                                            handled,
                                                        )
                                                        if (handled) change.consume()
                                                    }
                                                }
                                                downPosition = null
                                                lastPosition = null
                                                accumulatedX = 0f
                                                accumulatedY = 0f
                                                verticalDrag = false
                                            }
                                        }
                                    }
                                },
                    ) {
'''
if final_box not in vehicle:
    if previous_box in vehicle:
        vehicle = vehicle.replace(previous_box, final_box, 1)
    elif old_box in vehicle:
        vehicle = vehicle.replace(old_box, final_box, 1)
    else:
        raise SystemExit("VehicleLandscapeLayout right pane content Box marker missing")

provider_marker = '''                    LocalNavController provides paneNavController,
'''
provider_addition = '''                    LocalRightPaneScrollBridge provides rightPaneScrollBridge,
'''
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
    "import androidx.compose.runtime.mutableStateOf\n",
    "import androidx.compose.runtime.mutableStateMapOf\n",
    "ArtistScreen state map import",
)
artist = ensure_after(
    artist,
    "import androidx.compose.ui.geometry.Offset\n",
    "import androidx.compose.ui.geometry.Rect\n",
    "ArtistScreen Rect import",
)
artist = ensure_after(
    artist,
    "import androidx.compose.ui.input.pointer.pointerInput\n",
    "import androidx.compose.ui.layout.boundsInRoot\nimport androidx.compose.ui.layout.onGloballyPositioned\n",
    "ArtistScreen bounds imports",
)
artist = ensure_after(
    artist,
    "import com.metrolist.music.ui.component.LocalMenuState\n",
    "import com.metrolist.music.ui.component.LocalRightPaneScrollBridge\n",
    "ArtistScreen component import",
)

bridge_vars = '''    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
'''
final_bridge_vars = '''    val rightPaneScrollBridge = LocalRightPaneScrollBridge.current
    val rightPaneScrollOwner = remember { Any() }
    val rightPaneTapTargets = remember { mutableStateMapOf<String, Pair<Rect, () -> Unit>>() }
'''
if final_bridge_vars not in artist:
    if bridge_vars in artist:
        artist = artist.replace(bridge_vars, final_bridge_vars, 1)
    else:
        marker = "    val lazyListState = rememberLazyListState()\n"
        if marker not in artist:
            raise SystemExit("ArtistScreen LazyListState marker missing")
        artist = artist.replace(marker, marker + final_bridge_vars, 1)

previous_registration = '''    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(rightPaneScrollOwner) { delta ->
                lazyListState.dispatchRawDelta(delta)
            }
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
        }
    }

'''
final_registration = '''    DisposableEffect(embeddedInPlayer, rightPaneScrollBridge, lazyListState) {
        if (embeddedInPlayer && rightPaneScrollBridge != null) {
            rightPaneScrollBridge.register(
                owner = rightPaneScrollOwner,
                handler = { delta -> lazyListState.dispatchRawDelta(delta) },
                tapHandler = { positionInRoot ->
                    val target =
                        rightPaneTapTargets.values.lastOrNull { (bounds, _) ->
                            bounds.contains(positionInRoot)
                        }
                    if (target != null) {
                        timber.log.Timber.tag("Dudu7ArtistSectionTap").i(
                            "Bridged artist section tap x=%.1f y=%.1f",
                            positionInRoot.x,
                            positionInRoot.y,
                        )
                        target.second.invoke()
                        true
                    } else {
                        false
                    }
                },
            )
        }
        onDispose {
            rightPaneScrollBridge?.unregister(rightPaneScrollOwner)
            rightPaneTapTargets.clear()
        }
    }

    LaunchedEffect(artistPage?.artist?.id) {
        rightPaneTapTargets.clear()
    }

'''
if final_registration not in artist:
    if previous_registration not in artist:
        raise SystemExit("ArtistScreen bridge registration marker missing")
    artist = artist.replace(previous_registration, final_registration, 1)

# Remove the unsuccessful screen-local root pointer handler if it is still present.
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

print("Applied Dudu7 right-pane scroll and tap bridge")
