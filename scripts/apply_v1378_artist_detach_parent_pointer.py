#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
text = path.read_text(encoding="utf-8")

start_marker = '''                                .pointerInput(
                                    currentPaneRoute,
                                    rightPaneScrollBridge.handler,
                                    rightPaneScrollBridge.tapHandler,
                                    rightPaneScrollBridge.scrollEndHandler,
                                ) {
                                    // Artist screens must receive their pointer stream directly.
                                    // Merely observing the stream here on PointerEventPass.Initial
                                    // prevented the embedded LazyColumn and its buttons from handling
                                    // native gestures reliably on the Dudu7.
                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        Timber.tag("Dudu7ArtistInput").i(
                                            "Using native artist pointer handling route=%s",
                                            currentPaneRoute,
                                        )
                                        return@pointerInput
                                    }
                                    val scrollHandler = rightPaneScrollBridge.handler
'''
replacement_start = '''                                .then(
                                    if (currentPaneRoute?.startsWith("artist/") == true) {
                                        // Do not attach the Dudu7 pane's custom pointer modifier at all.
                                        // A pointerInput modifier whose coroutine returns immediately still
                                        // participates in hit testing and prevented the original ArtistScreen
                                        // LazyColumn/FABs from receiving the complete gesture stream.
                                        // The player's original nested-scroll connection is on the left player
                                        // column and remains unchanged.
                                        Modifier
                                    } else {
                                        Modifier.pointerInput(
                                            currentPaneRoute,
                                            rightPaneScrollBridge.handler,
                                            rightPaneScrollBridge.tapHandler,
                                            rightPaneScrollBridge.scrollEndHandler,
                                        ) {
                                            val scrollHandler = rightPaneScrollBridge.handler
'''

if replacement_start not in text:
    if start_marker not in text:
        raise SystemExit("Current Dudu7 right-pane pointer start marker missing")
    text = text.replace(start_marker, replacement_start, 1)

end_marker = '''                                    }
                                },
                    ) {'''
replacement_end = '''                                            }
                                        }
                                    },
                                )
                    ) {'''

if replacement_end not in text:
    # Only replace the pointer block ending after the conditional start was inserted.
    start = text.find(replacement_start)
    if start < 0:
        raise SystemExit("Conditional pointer start missing after replacement")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit("Current Dudu7 right-pane pointer end marker missing")
    text = text[:end] + replacement_end + text[end + len(end_marker):]

if 'return@pointerInput' in text:
    raise SystemExit("Artist pointerInput early-return workaround remains")
if 'if (currentPaneRoute?.startsWith("artist/") == true) {' not in text:
    raise SystemExit("Artist route conditional modifier missing")
if '.nestedScroll(state.preUpPostDownNestedScrollConnection)' not in text:
    raise SystemExit("Original player nested-scroll connection was lost")

path.write_text(text, encoding="utf-8")
print("Detached artist routes from the custom right-pane pointer modifier while preserving player nested scroll")
