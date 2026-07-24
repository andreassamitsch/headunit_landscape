#!/usr/bin/env python3
from pathlib import Path


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = artist_path.read_text(encoding="utf-8")

if "import androidx.compose.ui.geometry.Offset\n" not in text:
    marker = "import androidx.compose.ui.graphics.Color\n"
    if marker not in text:
        raise SystemExit("ArtistScreen Color import marker missing")
    text = text.replace(marker, marker + "import androidx.compose.ui.geometry.Offset\n", 1)

text = text.replace("import androidx.compose.foundation.gestures.detectVerticalDragGestures\n", "")

outer_new = '''    BoxWithConstraints(
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
    ) {'''

if "awaitPointerEvent(PointerEventPass.Initial)" not in text:
    outer_old = '''    BoxWithConstraints(
        modifier = Modifier.fillMaxSize(),
    ) {'''
    if outer_old not in text:
        raise SystemExit("Current ArtistScreen BoxWithConstraints marker missing")
    text = text.replace(outer_old, outer_new, 1)

lazy_start_marker = '''        LazyColumn(
            state = lazyListState,'''
lazy_start = text.find(lazy_start_marker)
if lazy_start < 0:
    raise SystemExit("ArtistScreen primary LazyColumn marker missing")
content_padding = text.find("            contentPadding =", lazy_start)
if content_padding < 0:
    raise SystemExit("ArtistScreen LazyColumn contentPadding marker missing")
expected_header = '''        LazyColumn(
            state = lazyListState,
            modifier = Modifier.fillMaxSize(),
'''
text = text[:lazy_start] + expected_header + text[content_padding:]
text = text.replace("            userScrollEnabled = true,", "            userScrollEnabled = !embeddedInPlayer,", 1)
if "            userScrollEnabled = !embeddedInPlayer," not in text:
    raise SystemExit("ArtistScreen embedded userScrollEnabled setting missing")

artist_path.write_text(text, encoding="utf-8")

smoke_path = Path("scripts/dudu7_v1371_regression_smoke.sh")
smoke = smoke_path.read_text(encoding="utf-8")
old_assertion = '''assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"
capture "artist-after-real-scroll"'''
new_assertion = '''adb logcat -d -v threadtime > "$RESULTS_DIR/artist-scroll-log.txt" || true
if ! assert_scroll_moved "$RESULTS_DIR/artist-before-scroll.xml" "$RESULTS_DIR/artist-after-scroll.xml"; then
    grep -E "Dudu7ArtistScroll|Embedded artist drag" "$RESULTS_DIR/artist-scroll-log.txt" || true
    capture "artist-scroll-failure"
    exit 1
fi
grep -q "Embedded artist drag ended" "$RESULTS_DIR/artist-scroll-log.txt"
capture "artist-after-real-scroll"'''
if new_assertion not in smoke:
    if old_assertion not in smoke:
        raise SystemExit("Artist scroll smoke assertion marker missing")
    smoke = smoke.replace(old_assertion, new_assertion, 1)
smoke_path.write_text(smoke, encoding="utf-8")

print("Applied current embedded artist initial-pass scroll handling")
