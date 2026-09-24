#!/usr/bin/env python3
"""Apply the small TV-only Compose focus changes on the confirmed Dudu7 release source."""
from pathlib import Path

path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
source = path.read_text(encoding="utf-8")


def change(old: str, new: str) -> None:
    global source
    if source.count(old) != 1:
        raise RuntimeError(f"Expected exactly one integration anchor, found {source.count(old)}: {old!r}")
    source = source.replace(old, new, 1)


change(
    "    val context = LocalContext.current\n",
    "    val context = LocalContext.current\n"
    "    val tvDpadEnabled = remember(context) { TvDpadNavigation.isEnabled(context) }\n",
)
change(
    "                    .padding(horizontal = 12.dp, vertical = 4.dp)\n"
    "                    .nestedScroll(state.preUpPostDownNestedScrollConnection),",
    "                    .padding(horizontal = 12.dp, vertical = 4.dp)\n"
    "                    .tvDpadFocusGroup(tvDpadEnabled)\n"
    "                    .nestedScroll(state.preUpPostDownNestedScrollConnection),",
)
change(
    "                        .padding(horizontal = 8.dp, vertical = 4.dp)\n"
    "                        .clip(if (frostedIceEnabled) glassShape else RoundedCornerShape(12.dp))",
    "                        .padding(horizontal = 8.dp, vertical = 4.dp)\n"
    "                        .tvDpadFocusGroup(tvDpadEnabled)\n"
    "                        .clip(if (frostedIceEnabled) glassShape else RoundedCornerShape(12.dp))",
)
change(
    "                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp),\n"
    "                        verticalAlignment = Alignment.CenterVertically,",
    "                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp)\n"
    "                            .tvDpadFocusGroup(tvDpadEnabled),\n"
    "                        verticalAlignment = Alignment.CenterVertically,",
)
change(
    "                                        modifier = Modifier.fillMaxSize(),\n"
    "                                    )\n"
    "                                    if (isSelected)",
    "                                        modifier = Modifier.fillMaxSize()\n"
    "                                            .tvDpadFocusIndicator(tvDpadEnabled),\n"
    "                                    )\n"
    "                                    if (isSelected)",
)
change(
    "                                .weight(1f)\n"
    "                                .fillMaxWidth()\n"
    "                                .onGloballyPositioned { coordinates ->",
    "                                .weight(1f)\n"
    "                                .fillMaxWidth()\n"
    "                                .tvDpadFocusGroup(tvDpadEnabled)\n"
    "                                .onGloballyPositioned { coordinates ->",
)
path.write_text(source, encoding="utf-8")
print("TV-only focus grouping applied to vehicle layout; all original event handlers unchanged.")
