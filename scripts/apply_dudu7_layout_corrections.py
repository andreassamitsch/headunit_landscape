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
        raise RuntimeError(f"Expected one anchor in {path}, found {count}: {old[:100]!r}")
    write(path, text.replace(old, new, 1))


# Do not render the queue a second time as a full-screen overlay in Dudu7 landscape.
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt",
    "            visible = !isFullScreen,\n",
    "            visible = !isFullScreen && !VehicleVariantConfig.isDudu7,\n",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt",
    "                                    isLandscape = true,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n",
    "                                    isLandscape = true,\n                                    landscapeHorizontalPadding = 8.dp,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n",
)

# A non-expandable sheet is a fixed pane: no offset, no collapsed renderer and full opacity.
bottom_sheet = "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt"
replace_once(bottom_sheet, "                translationY = y\n", "                translationY = if (isExpandable) y else 0f\n")
replace_once(
    bottom_sheet,
    "                val cornerRadius = if (!state.isExpanded) 16.dp.toPx() else 0f\n",
    "                val cornerRadius = if (isExpandable && !state.isExpanded) 16.dp.toPx() else 0f\n",
)
replace_once(
    bottom_sheet,
    "        if (!state.isCollapsed && !state.isDismissed) {\n",
    "        if (isExpandable && !state.isCollapsed && !state.isDismissed) {\n",
)
replace_once(bottom_sheet, "        if (!state.isCollapsed) {\n", "        if (!isExpandable || !state.isCollapsed) {\n")
replace_once(
    bottom_sheet,
    "                        alpha = ((state.progress - 0.15f) * 4).coerceIn(0f, 1f)\n",
    "                        alpha = if (isExpandable) ((state.progress - 0.15f) * 4).coerceIn(0f, 1f) else 1f\n",
)
replace_once(
    bottom_sheet,
    "        if (!state.isExpanded && (onDismiss == null || !state.isDismissed)) {\n",
    "        if (isExpandable && !state.isExpanded && (onDismiss == null || !state.isDismissed)) {\n",
)

# Allow a much smaller landscape inset around the artwork for the vehicle layout only.
thumbnail = "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt"
replace_once(
    thumbnail,
    "    isLandscape: Boolean = false,\n    isListenTogetherGuest: Boolean = false,\n) {\n",
    "    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n) {\n",
)
replace_once(
    thumbnail,
    "                            containerHeight = maxHeight,\n                            isLandscape = isLandscape\n",
    "                            containerHeight = maxHeight,\n                            horizontalPadding = if (isLandscape) landscapeHorizontalPadding else PlayerHorizontalPadding,\n                            isLandscape = isLandscape,\n",
)
replace_once(
    thumbnail,
    "                            Modifier.size(dimensions.thumbnailSize + (PlayerHorizontalPadding * 2))\n",
    "                            Modifier.size(dimensions.thumbnailSize + (landscapeHorizontalPadding * 2))\n",
)
replace_once(
    thumbnail,
    "                                isLandscape = isLandscape,\n                                isListenTogetherGuest = isListenTogetherGuest,\n",
    "                                isLandscape = isLandscape,\n                                landscapeHorizontalPadding = landscapeHorizontalPadding,\n                                isListenTogetherGuest = isListenTogetherGuest,\n",
)
replace_once(
    thumbnail,
    "    isLandscape: Boolean = false,\n    isListenTogetherGuest: Boolean = false,\n    currentMediaId: String? = null,\n",
    "    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n    currentMediaId: String? = null,\n",
)
replace_once(
    thumbnail,
    "                    Modifier.size(dimensions.thumbnailSize + (PlayerHorizontalPadding * 2))\n",
    "                    Modifier.size(dimensions.thumbnailSize + (landscapeHorizontalPadding * 2))\n",
)

# Remove the phone-style queue footer in the permanent Dudu7 pane and reclaim its padding.
queue = "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt"
replace_once(
    queue,
    "                                bottom = ListItemHeight + 8.dp,\n",
    "                                bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp,\n",
)
replace_once(
    queue,
    "        val shuffleModeEnabled by playerConnection.shuffleModeEnabled.collectAsStateWithLifecycle()\n\n        Box(\n",
    "        if (!VehicleVariantConfig.isDudu7) {\n            val shuffleModeEnabled by playerConnection.shuffleModeEnabled.collectAsStateWithLifecycle()\n\n            Box(\n",
)
replace_once(
    queue,
    "            }\n        }\n\n        SnackbarHost(\n            hostState = snackbarHostState,\n",
    "            }\n        }\n        }\n\n        SnackbarHost(\n            hostState = snackbarHostState,\n",
)
replace_once(
    queue,
    "                        bottom =\n                            ListItemHeight +\n                                WindowInsets.systemBars\n                                    .asPaddingValues()\n                                    .calculateBottomPadding(),\n",
    "                        bottom =\n                            if (VehicleVariantConfig.isDudu7) {\n                                0.dp\n                            } else {\n                                ListItemHeight +\n                                    WindowInsets.systemBars\n                                        .asPaddingValues()\n                                        .calculateBottomPadding()\n                            },\n",
)

# Structural checks for the regression that was visible on the head unit.
verifier = "scripts/verify_dudu7_architecture.py"
replace_once(
    verifier,
    '        "moveTaskToBack(true)",\n',
    '        "moveTaskToBack(true)",\n        "visible = !isFullScreen && !VehicleVariantConfig.isDudu7",\n        "landscapeHorizontalPadding = 8.dp",\n',
)
replace_once(
    verifier,
    '        "VehicleQueueActions()",\n',
    '        "VehicleQueueActions()",\n        "bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp",\n',
)
replace_once(
    verifier,
    '    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n',
    '    "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt": (\n        "if (!isExpandable || !state.isCollapsed)",\n    ),\n    "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt": (\n        "landscapeHorizontalPadding: Dp = PlayerHorizontalPadding",\n    ),\n    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n',
)

docs = "docs/DUDU7_ARCHITECTURE.md"
replace_once(
    docs,
    "- Player links, Warteschlange rechts\n",
    "- Player links, Warteschlange rechts\n- feste rechte Queue ohne zusätzliches Smartphone-Bottom-Sheet\n- kompakter RVX-Player mit großem Cover und reiner Icon-Aktionsleiste\n",
)

# Keep the same corrections reproducible when the overlay is rebuilt on a future upstream.
write(
    "scripts/dudu7_overlay/rebuild_05_layout_corrections.py.part",
    r'''# Dudu7 head-unit corrections after the first RVX device test.
_patch_player_before_layout_corrections = patch_player


def patch_player() -> None:
    _patch_player_before_layout_corrections()
    player = "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
    replace_once(
        player,
        "            visible = !isFullScreen,\n",
        "            visible = !isFullScreen && !VehicleVariantConfig.isDudu7,\n",
    )
    replace_once(
        player,
        "                                    isLandscape = true,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n",
        "                                    isLandscape = true,\n                                    landscapeHorizontalPadding = 8.dp,\n                                    isListenTogetherGuest = isListenTogetherGuest,\n",
    )

    bottom_sheet = "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt"
    replace_once(bottom_sheet, "                translationY = y\n", "                translationY = if (isExpandable) y else 0f\n")
    replace_once(bottom_sheet, "                val cornerRadius = if (!state.isExpanded) 16.dp.toPx() else 0f\n", "                val cornerRadius = if (isExpandable && !state.isExpanded) 16.dp.toPx() else 0f\n")
    replace_once(bottom_sheet, "        if (!state.isCollapsed && !state.isDismissed) {\n", "        if (isExpandable && !state.isCollapsed && !state.isDismissed) {\n")
    replace_once(bottom_sheet, "        if (!state.isCollapsed) {\n", "        if (!isExpandable || !state.isCollapsed) {\n")
    replace_once(bottom_sheet, "                        alpha = ((state.progress - 0.15f) * 4).coerceIn(0f, 1f)\n", "                        alpha = if (isExpandable) ((state.progress - 0.15f) * 4).coerceIn(0f, 1f) else 1f\n")
    replace_once(bottom_sheet, "        if (!state.isExpanded && (onDismiss == null || !state.isDismissed)) {\n", "        if (isExpandable && !state.isExpanded && (onDismiss == null || !state.isDismissed)) {\n")

    thumbnail = "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt"
    replace_once(thumbnail, "    isLandscape: Boolean = false,\n    isListenTogetherGuest: Boolean = false,\n) {\n", "    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n) {\n")
    replace_once(thumbnail, "                            containerHeight = maxHeight,\n                            isLandscape = isLandscape\n", "                            containerHeight = maxHeight,\n                            horizontalPadding = if (isLandscape) landscapeHorizontalPadding else PlayerHorizontalPadding,\n                            isLandscape = isLandscape,\n")
    replace_once(thumbnail, "                            Modifier.size(dimensions.thumbnailSize + (PlayerHorizontalPadding * 2))\n", "                            Modifier.size(dimensions.thumbnailSize + (landscapeHorizontalPadding * 2))\n")
    replace_once(thumbnail, "                                isLandscape = isLandscape,\n                                isListenTogetherGuest = isListenTogetherGuest,\n", "                                isLandscape = isLandscape,\n                                landscapeHorizontalPadding = landscapeHorizontalPadding,\n                                isListenTogetherGuest = isListenTogetherGuest,\n")
    replace_once(thumbnail, "    isLandscape: Boolean = false,\n    isListenTogetherGuest: Boolean = false,\n    currentMediaId: String? = null,\n", "    isLandscape: Boolean = false,\n    landscapeHorizontalPadding: Dp = PlayerHorizontalPadding,\n    isListenTogetherGuest: Boolean = false,\n    currentMediaId: String? = null,\n")
    replace_once(thumbnail, "                    Modifier.size(dimensions.thumbnailSize + (PlayerHorizontalPadding * 2))\n", "                    Modifier.size(dimensions.thumbnailSize + (landscapeHorizontalPadding * 2))\n")


_patch_queue_before_layout_corrections = patch_queue


def patch_queue() -> None:
    _patch_queue_before_layout_corrections()
    queue = "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt"
    replace_once(queue, "                                bottom = ListItemHeight + 8.dp,\n", "                                bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp,\n")
    replace_once(queue, "        val shuffleModeEnabled by playerConnection.shuffleModeEnabled.collectAsStateWithLifecycle()\n\n        Box(\n", "        if (!VehicleVariantConfig.isDudu7) {\n            val shuffleModeEnabled by playerConnection.shuffleModeEnabled.collectAsStateWithLifecycle()\n\n            Box(\n")
    replace_once(queue, "            }\n        }\n\n        SnackbarHost(\n            hostState = snackbarHostState,\n", "            }\n        }\n        }\n\n        SnackbarHost(\n            hostState = snackbarHostState,\n")
    replace_once(queue, "                        bottom =\n                            ListItemHeight +\n                                WindowInsets.systemBars\n                                    .asPaddingValues()\n                                    .calculateBottomPadding(),\n", "                        bottom =\n                            if (VehicleVariantConfig.isDudu7) {\n                                0.dp\n                            } else {\n                                ListItemHeight +\n                                    WindowInsets.systemBars\n                                        .asPaddingValues()\n                                        .calculateBottomPadding()\n                            },\n")


_write_verifier_before_layout_corrections = write_verifier_and_docs


def write_verifier_and_docs(upstream_sha: str) -> None:
    _write_verifier_before_layout_corrections(upstream_sha)
    verifier = "scripts/verify_dudu7_architecture.py"
    replace_once(verifier, '        "moveTaskToBack(true)",\n', '        "moveTaskToBack(true)",\n        "visible = !isFullScreen && !VehicleVariantConfig.isDudu7",\n        "landscapeHorizontalPadding = 8.dp",\n')
    replace_once(verifier, '        "VehicleQueueActions()",\n', '        "VehicleQueueActions()",\n        "bottom = if (VehicleVariantConfig.isDudu7) 8.dp else ListItemHeight + 8.dp",\n')
    replace_once(verifier, '    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n', '    "app/src/main/kotlin/com/metrolist/music/ui/component/BottomSheet.kt": (\n        "if (!isExpandable || !state.isCollapsed)",\n    ),\n    "app/src/main/kotlin/com/metrolist/music/ui/player/Thumbnail.kt": (\n        "landscapeHorizontalPadding: Dp = PlayerHorizontalPadding",\n    ),\n    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt": (\n')
    docs = "docs/DUDU7_ARCHITECTURE.md"
    replace_once(docs, "- Player links, Warteschlange rechts\n", "- Player links, Warteschlange rechts\n- feste rechte Queue ohne zusätzliches Smartphone-Bottom-Sheet\n- kompakter RVX-Player mit großem Cover und reiner Icon-Aktionsleiste\n")
''',
)

print("Dudu7 layout corrections applied")
