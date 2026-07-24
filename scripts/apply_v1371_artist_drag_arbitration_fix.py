#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Marker not found in {path}: {old[:220]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
replace_once(
    path,
    '''                                detectVerticalDragGestures { change, dragAmount ->
                                    change.consume()
                                    lazyListState.dispatchRawDelta(-dragAmount)
                                }''',
    '''                                detectVerticalDragGestures(
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
                                )''',
)
replace_once(
    path,
    "            userScrollEnabled = true,",
    "            userScrollEnabled = !embeddedInPlayer,",
)
