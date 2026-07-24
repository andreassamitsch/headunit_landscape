#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:240]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    path,
    "import androidx.compose.ui.graphics.Color\n",
    "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.geometry.Offset\n",
)

replace_once(
    path,
    '''    BoxWithConstraints(
        modifier = Modifier.fillMaxSize(),
    ) {''',
    '''    BoxWithConstraints(
        modifier =
            Modifier
                .fillMaxSize()
                .then(
                    if (embeddedInPlayer) {
                        Modifier.pointerInput(lazyListState) {
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
                                            timber.log.Timber.tag("Dudu7ArtistScroll").d(
                                                "Embedded artist drag ended index=%d offset=%d",
                                                lazyListState.firstVisibleItemIndex,
                                                lazyListState.firstVisibleItemScrollOffset,
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
                                        kotlin.math.abs(accumulatedY) > viewConfiguration.touchSlop &&
                                        kotlin.math.abs(accumulatedY) > kotlin.math.abs(accumulatedX)
                                    ) {
                                        verticalDrag = true
                                        timber.log.Timber.tag("Dudu7ArtistScroll").d("Embedded artist drag started")
                                    }
                                    if (verticalDrag) {
                                        change.consume()
                                        lazyListState.dispatchRawDelta(-delta.y)
                                    }
                                }
                            }
                        }
                    } else {
                        Modifier
                    },
                ),
    ) {''',
)

replace_once(
    path,
    '''            modifier =
                Modifier
                    .fillMaxSize()
                    .then(
                        if (embeddedInPlayer) {
                            Modifier.pointerInput(lazyListState) {
                                detectVerticalDragGestures(
                                    onDragStart = {
                                        timber.log.Timber.tag("Dudu7ArtistScroll").d("Embedded artist drag started")
                                    },
                                    onDragEnd = {
                                        timber.log.Timber.tag("Dudu7ArtistScroll").d(
                                            "Embedded artist drag ended index=%d offset=%d",
                                            lazyListState.firstVisibleItemIndex,
                                            lazyListState.firstVisibleItemScrollOffset,
                                        )
                                    },
                                    onVerticalDrag = { change, dragAmount ->
                                        change.consume()
                                        lazyListState.dispatchRawDelta(-dragAmount)
                                    },
                                )
                            }
                        } else {
                            Modifier
                        },
                    ),''',
    '''            modifier = Modifier.fillMaxSize(),''',
)

# The old gesture helper is no longer used after moving arbitration to the outer
# BoxWithConstraints at PointerEventPass.Initial.
file = Path(path)
text = file.read_text(encoding="utf-8")
text = text.replace("import androidx.compose.foundation.gestures.detectVerticalDragGestures\n", "")
file.write_text(text, encoding="utf-8")

# Always preserve diagnostic evidence if the coordinate assertion fails.
smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")
old = '''assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
capture "artist-after-real-scroll"'''
new = '''adb logcat -d -v threadtime > "$RESULTS_DIR/artist-scroll-log.txt" || true
if ! assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"; then
    grep -E "Dudu7ArtistScroll|Embedded artist drag" "$RESULTS_DIR/artist-scroll-log.txt" || true
    capture "artist-scroll-failure"
    exit 1
fi
grep -q "Embedded artist drag ended" "$RESULTS_DIR/artist-scroll-log.txt"
capture "artist-after-real-scroll"'''
if new not in smoke:
    if old not in smoke:
        raise SystemExit("Artist scroll assertion marker missing")
    smoke = smoke.replace(old, new, 1)
smoke_path.write_text(smoke, encoding="utf-8")
