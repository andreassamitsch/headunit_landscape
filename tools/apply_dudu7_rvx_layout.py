#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one match in {path}, found {count}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def insert_after(path: str, anchor: str, addition: str) -> None:
    replace_once(path, anchor, anchor + addition)


PLAYER_QUEUE_OLD = '''    val queueSheetState =
        rememberBottomSheetState(
            dismissedBound = dismissedBound,
            expandedBound = state.expandedBound,
            collapsedBound = dismissedBound + 1.dp,
            initialAnchor = 1,
        )
'''
PLAYER_QUEUE_NEW = '''    val queueSheetState =
        rememberBottomSheetState(
            dismissedBound = dismissedBound,
            expandedBound = state.expandedBound,
            collapsedBound = dismissedBound + 1.dp,
            initialAnchor = if (VehicleVariantConfig.isDudu7) expandedAnchor else collapsedAnchor,
        )

    LaunchedEffect(state.isExpanded) {
        if (VehicleVariantConfig.isDudu7 && state.isExpanded && !queueSheetState.isExpanded) {
            queueSheetState.expandSoft()
        }
    }
'''

PLAYER_CONTROLS_OLD = '''                    controlsContent = {
                        val currentMediaMetadata = mediaMetadata
                        if (currentMediaMetadata != null) {
                            controlsContent(currentMediaMetadata)
                        } else {
                            VehicleEmptyPlayer(navController = navController)
                        }
                    },
'''
PLAYER_CONTROLS_NEW = '''                    controlsContent = {
                        val currentMediaMetadata = mediaMetadata
                        if (currentMediaMetadata != null) {
                            val isEpisode = currentSong?.song?.isEpisode == true
                            val isFavorite =
                                if (isEpisode) {
                                    currentSong?.song?.inLibrary != null
                                } else {
                                    currentSong?.song?.liked == true
                                }
                            VehiclePlayerControls(
                                title = currentMediaMetadata.title,
                                artists = currentMediaMetadata.artists.joinToString(", ") { it.name },
                                isPlaying = effectiveIsPlaying,
                                isEnded = playbackState == STATE_ENDED,
                                isGuest = isListenTogetherGuest,
                                isMuted = isMuted,
                                canSkipPrevious = canSkipPrevious && !isListenTogetherGuest,
                                canSkipNext = canSkipNext && !isListenTogetherGuest,
                                sliderValue = sliderPosition ?: effectivePosition,
                                duration = duration,
                                canSeek = !isListenTogetherGuest,
                                isFavorite = isFavorite,
                                textColor = TextBackgroundColor,
                                playButtonContainerColor = textButtonColor,
                                playButtonContentColor = iconButtonColor,
                                sideButtonContentColor = sideButtonContentColor,
                                onPrevious = playerConnection::seekToPrevious,
                                onPlayPause = {
                                    if (isListenTogetherGuest) {
                                        playerConnection.toggleMute()
                                    } else if (isCasting) {
                                        if (castIsPlaying) castHandler?.pause() else castHandler?.play()
                                    } else if (playbackState == STATE_ENDED) {
                                        playerConnection.player.seekTo(0, 0)
                                        playerConnection.player.playWhenReady = true
                                    } else {
                                        playerConnection.togglePlayPause()
                                    }
                                },
                                onNext = playerConnection::seekToNext,
                                onSliderValueChange = {
                                    if (!isListenTogetherGuest) sliderPosition = it
                                },
                                onSliderValueChangeFinished = {
                                    if (!isListenTogetherGuest) {
                                        sliderPosition?.let {
                                            if (isCasting) {
                                                castHandler?.seekTo(it)
                                                lastManualSeekTime = System.currentTimeMillis()
                                            } else {
                                                playerConnection.player.seekTo(it)
                                            }
                                            position = it
                                        }
                                        sliderPosition = null
                                    }
                                },
                                onStartRadio = {
                                    Toast.makeText(
                                        context,
                                        context.getString(R.string.starting_radio),
                                        Toast.LENGTH_SHORT,
                                    ).show()
                                    playerConnection.startRadioSeamlessly()
                                },
                                onShare = {
                                    val intent =
                                        Intent().apply {
                                            action = Intent.ACTION_SEND
                                            type = "text/plain"
                                            putExtra(
                                                Intent.EXTRA_TEXT,
                                                "https://music.youtube.com/watch?v=${currentMediaMetadata.id}",
                                            )
                                        }
                                    context.startActivity(Intent.createChooser(intent, null))
                                },
                                onToggleLike = playerConnection::toggleLike,
                                onTitleClick = {
                                    val albumId = currentMediaMetadata.album?.id
                                        ?: currentSong?.album?.id
                                        ?: currentSong?.song?.albumId
                                    if (albumId != null) {
                                        navController.navigate("album/$albumId")
                                        state.collapseSoft()
                                    }
                                },
                                onArtistClick = {
                                    currentMediaMetadata.artists.firstOrNull { !it.id.isNullOrBlank() }?.id?.let {
                                        navController.navigate("artist/$it")
                                        state.collapseSoft()
                                    }
                                },
                                fallbackContent = { controlsContent(currentMediaMetadata) },
                            )
                        } else {
                            VehicleEmptyPlayer(navController = navController)
                        }
                    },
'''

QUEUE_OLD = '''    BottomSheet(
        state = state,
        modifier = modifier,
        background = {
'''
QUEUE_NEW = '''    BottomSheet(
        state = state,
        modifier = modifier,
        isExpandable = !VehicleVariantConfig.isDudu7,
        background = {
'''


def patch_player() -> None:
    path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
    insert_after(
        path,
        "import com.metrolist.music.ui.component.rememberBottomSheetState\n",
        "import com.metrolist.music.ui.component.collapsedAnchor\nimport com.metrolist.music.ui.component.expandedAnchor\n",
    )
    insert_after(
        path,
        "import com.metrolist.music.variant.VehicleLandscapeLayout\n",
        "import com.metrolist.music.variant.VehiclePlayerControls\n",
    )
    replace_once(path, PLAYER_QUEUE_OLD, PLAYER_QUEUE_NEW)
    replace_once(
        path,
        "                    playerPaneWeight = dudu7PlayerPaneWeight,\n",
        "                    playerPaneWeight = dudu7PlayerPaneWeight,\n                    onToggleLyrics = { showInlineLyrics = !showInlineLyrics },\n",
    )
    replace_once(path, PLAYER_CONTROLS_OLD, PLAYER_CONTROLS_NEW)


def patch_queue() -> None:
    replace_once(
        "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt",
        QUEUE_OLD,
        QUEUE_NEW,
    )


def patch_defaults() -> None:
    replace_once(
        "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleVariantConfig.kt",
        "    const val defaultPlayerPaneWeight = 0.45f\n",
        "    const val defaultPlayerPaneWeight = 0.56f\n",
    )
    replace_once(
        "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleSettingsScreen.kt",
        "    val (paneWeight, setPaneWeight) = rememberPreference(Dudu7PlayerPaneWeightKey, 0.45f)\n",
        "    val (paneWeight, setPaneWeight) = rememberPreference(Dudu7PlayerPaneWeightKey, 0.56f)\n",
    )


def write_overlay_patch() -> None:
    content = f'''# RVX-inspired Dudu7 player layout, permanent queue and right-side navigation tabs.
_materialize_source_sets_before_rvx = materialize_source_sets


def materialize_source_sets(source_ref: str) -> None:
    _materialize_source_sets_before_rvx(source_ref)
    for path in (
        "app/src/standard/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
        "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
        "app/src/standard/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt",
        "app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt",
    ):
        copy_from_ref(source_ref, path)


_patch_player_before_rvx = patch_player


def patch_player() -> None:
    _patch_player_before_rvx()
    path = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
    insert_after(
        path,
        "import com.metrolist.music.ui.component.rememberBottomSheetState\\n",
        "import com.metrolist.music.ui.component.collapsedAnchor\\nimport com.metrolist.music.ui.component.expandedAnchor\\n",
    )
    insert_after(
        path,
        "import com.metrolist.music.variant.VehicleLandscapeLayout\\n",
        "import com.metrolist.music.variant.VehiclePlayerControls\\n",
    )
    replace_once(path, {PLAYER_QUEUE_OLD!r}, {PLAYER_QUEUE_NEW!r})
    replace_once(
        path,
        "                    playerPaneWeight = dudu7PlayerPaneWeight,\\n",
        "                    playerPaneWeight = dudu7PlayerPaneWeight,\\n                    onToggleLyrics = {{ showInlineLyrics = !showInlineLyrics }},\\n",
    )
    replace_once(path, {PLAYER_CONTROLS_OLD!r}, {PLAYER_CONTROLS_NEW!r})


_patch_queue_before_rvx = patch_queue


def patch_queue() -> None:
    _patch_queue_before_rvx()
    replace_once(
        "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt",
        {QUEUE_OLD!r},
        {QUEUE_NEW!r},
    )
'''
    write("scripts/dudu7_overlay/rebuild_02c.py.part", content)


def patch_verifier_and_docs() -> None:
    for path in (
        "scripts/verify_dudu7_architecture.py",
        "scripts/dudu7_overlay/rebuild_03.py.part",
    ):
        text = read(path)
        if '"VehiclePlayerControls.kt",' not in text:
            text = text.replace(
                '    "VehicleLandscapeLayout.kt",\n',
                '    "VehicleLandscapeLayout.kt",\n    "VehiclePlayerControls.kt",\n',
                1,
            )
        if '        "VehiclePlayerControls(",\n' not in text:
            text = text.replace(
                '        "VehicleLandscapeLayout(",\n',
                '        "VehicleLandscapeLayout(",\n        "VehiclePlayerControls(",\n',
                1,
            )
        if '        "isExpandable = !VehicleVariantConfig.isDudu7",\n' not in text:
            text = text.replace(
                '        "VehicleQueueActions()",\n',
                '        "VehicleQueueActions()",\n        "isExpandable = !VehicleVariantConfig.isDudu7",\n',
                1,
            )
        write(path, text)

    docs = read("docs/DUDU7_ARCHITECTURE.md")
    if "- `VehiclePlayerControls`\n" not in docs:
        docs = docs.replace(
            "- `VehicleLandscapeLayout`\n",
            "- `VehicleLandscapeLayout`\n- `VehiclePlayerControls`\n",
            1,
        )
    docs = docs.replace(
        "- Player links, Warteschlange rechts\n",
        "- RVX-inspirierter Player links, permanente Warteschlange rechts\n- rechte Tabs für Warteschlange, Playlists und Bibliothek\n",
        1,
    )
    write("docs/DUDU7_ARCHITECTURE.md", docs)

    rebuild = read("scripts/dudu7_overlay/rebuild_03.py.part")
    rebuild = rebuild.replace(
        "- `VehicleLandscapeLayout`\n",
        "- `VehicleLandscapeLayout`\n- `VehiclePlayerControls`\n",
        1,
    )
    rebuild = rebuild.replace(
        "- Player links, Warteschlange rechts\n",
        "- RVX-inspirierter Player links, permanente Warteschlange rechts\n- rechte Tabs für Warteschlange, Playlists und Bibliothek\n",
        1,
    )
    write("scripts/dudu7_overlay/rebuild_03.py.part", rebuild)


def main() -> None:
    patch_player()
    patch_queue()
    patch_defaults()
    write_overlay_patch()
    patch_verifier_and_docs()
    print("Applied Dudu7 RVX layout patch")


if __name__ == "__main__":
    main()
