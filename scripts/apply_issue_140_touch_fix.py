from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise SystemExit(f"anchor not found in {path}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1))


browse = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/BrowseScreen.kt")
items = Path("app/src/main/kotlin/com/metrolist/music/ui/component/Items.kt")
build = Path("app/build.gradle.kts")

replace_once(
    browse,
    "    val autoRadioQueue by rememberPreference(AutoRadioQueueKey, defaultValue = true)\n\n    LazyVerticalGrid(",
    "    val autoRadioQueue by rememberPreference(AutoRadioQueueKey, defaultValue = true)\n\n"
    "    val playBrowseSong: (SongItem) -> Unit = { songItem ->\n"
    "        if (songItem.id == mediaMetadata?.id) {\n"
    "            playerConnection.togglePlayPause()\n"
    "        } else {\n"
    "            playerConnection.playQueue(\n"
    "                createBrowseSongQueue(\n"
    "                    item = songItem,\n"
    "                    autoRadioQueue = autoRadioQueue,\n"
    "                ),\n"
    "            )\n"
    "        }\n"
    "    }\n\n"
    "    LazyVerticalGrid(",
)

replace_once(
    browse,
    "                    coroutineScope = coroutineScope,\n                    modifier =",
    "                    coroutineScope = coroutineScope,\n"
    "                    onPlayClick =\n"
    "                        (item as? SongItem)?.let { songItem ->\n"
    "                            { playBrowseSong(songItem) }\n"
    "                        },\n"
    "                    modifier =",
)

replace_once(
    browse,
    "                                        is SongItem -> {\n"
    "                                            // Browse/genre pages already render a play overlay for SongItem.\n"
    "                                            // Reuse the normal search queue semantics so PlayerConnection also\n"
    "                                            // triggers Dudu7's explicit-selection/stale-restore protection.\n"
    "                                            if (item.id == mediaMetadata?.id) {\n"
    "                                                playerConnection.togglePlayPause()\n"
    "                                            } else {\n"
    "                                                playerConnection.playQueue(\n"
    "                                                    createBrowseSongQueue(\n"
    "                                                        item = item,\n"
    "                                                        autoRadioQueue = autoRadioQueue,\n"
    "                                                    ),\n"
    "                                                )\n"
    "                                            }\n"
    "                                        }",
    "                                        is SongItem -> playBrowseSong(item)",
)

replace_once(
    items,
    "    isPlaying: Boolean = false,\n    fillMaxWidth: Boolean = false,\n) = GridItem(",
    "    isPlaying: Boolean = false,\n"
    "    onPlayClick: (() -> Unit)? = null,\n"
    "    fillMaxWidth: Boolean = false,\n"
    ") = GridItem(",
)

replace_once(
    items,
    "            OverlayPlayButton(\n                visible = true\n            )",
    "            OverlayPlayButton(\n"
    "                visible = true,\n"
    "                onClick = onPlayClick,\n"
    "            )",
)

replace_once(
    items,
    "fun BoxScope.OverlayPlayButton(\n    visible: Boolean\n) {",
    "fun BoxScope.OverlayPlayButton(\n"
    "    visible: Boolean,\n"
    "    onClick: (() -> Unit)? = null,\n"
    ") {",
)

replace_once(
    items,
    "                .size(36.dp)\n                .clip(CircleShape)\n                .background(Color.Black.copy(alpha = ActiveBoxAlpha))",
    "                .size(36.dp)\n"
    "                .clip(CircleShape)\n"
    "                .background(Color.Black.copy(alpha = ActiveBoxAlpha))\n"
    "                .then(\n"
    "                    if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier,\n"
    "                )",
)

text = build.read_text()
text = text.replace('versionCode = 1370078', 'versionCode = 1370079', 1)
text = text.replace('versionName = "13.7.69"', 'versionName = "13.7.70"', 1)
if 'versionCode = 1370079' not in text or 'versionName = "13.7.70"' not in text:
    raise SystemExit('version anchors not found')
build.write_text(text)
