#!/usr/bin/env python3
from pathlib import Path
import math
import random

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Expected source block missing in {path}")
    path.write_text(text.replace(old, new, 1))


build = ROOT / "app/build.gradle.kts"
replace_once(build, "versionCode = 1370062", "versionCode = 1370063")
replace_once(build, 'versionName = "13.7.53"', 'versionName = "13.7.54"')

vehicle = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(
    vehicle,
    "import androidx.compose.foundation.layout.windowInsetsPadding\n",
    "import androidx.compose.foundation.layout.windowInsetsPadding\nimport androidx.compose.foundation.layout.width\n",
)
replace_once(vehicle, "alpha = normalized * 0.68f", "alpha = normalized * 0.46f")
replace_once(
    vehicle,
    """    onToggleLyrics: () -> Unit,
    tabContentColor: Color,
    tabScrimColor: Color,
    thumbnailContent: @Composable () -> Unit,""",
    """    onToggleLyrics: () -> Unit,
    tabContentColor: Color,
    tabGlassColor: Color,
    thumbnailContent: @Composable () -> Unit,""",
)

old_tab_block = '''                Surface(
                    color = tabScrimColor,
                    shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp, bottomStart = 14.dp, bottomEnd = 14.dp),
                    tonalElevation = 0.dp,
                    shadowElevation = 0.dp,
                    modifier = Modifier.fillMaxWidth().height(64.dp),
                ) {
                    LazyRow(
                        state = tabListState,
                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        itemsIndexed(
                            items = orderedTabs,
                            key = { _, tab -> tab.name },
                        ) { _, tab ->
                            ReorderableItem(tabReorderState, key = tab.name) { isDragging ->
                                val isSelected = selectedTab == tab
                                val itemColor = if (isSelected) tabContentColor else tabContentColor.copy(alpha = 0.78f)
                                Tab(
                                    selected = isSelected,
                                onClick = {
                                    if (!isDragging) {
                                        if (selectedTab != tab || currentPaneRoute != tab.route) {
                                            selectedTab = tab
                                            val restoredExistingTab =
                                                paneNavController.popBackStack(tab.route, inclusive = false)
                                            if (!restoredExistingTab) {
                                                paneNavController.popBackStack(VEHICLE_QUEUE_ROUTE, inclusive = false)
                                                if (tab != VehicleRightPaneTab.QUEUE) {
                                                    paneNavController.navigate(tab.route) {
                                                        launchSingleTop = true
                                                    }
                                                }
                                            }
                                        }
                                    }
                                },
                                icon = {
                                    Icon(
                                        painter = painterResource(tab.icon),
                                        contentDescription = tab.title,
                                        tint = itemColor,
                                    )
                                },
                                text = { Text(tab.title, maxLines = 1, color = itemColor) },
                                modifier =
                                    Modifier
                                        .padding(horizontal = 2.dp, vertical = 5.dp)
                                        .height(54.dp)
                                        .clip(RoundedCornerShape(14.dp))
                                        .background(if (isSelected) tabContentColor.copy(alpha = 0.14f) else Color.Transparent)
                                        .longPressDraggableHandle(
                                            onDragStarted = {
                                                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                            },
                                        ),
                            )
                            }
                        }
                    }
                }
'''

new_tab_block = '''                val effectiveTabContentColor =
                    if (frostedIceEnabled) tabContentColor else baseColors.onSurface
                val effectiveTabGlassColor =
                    if (frostedIceEnabled) tabGlassColor else baseColors.surfaceContainerHigh
                Box(
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .height(64.dp)
                            .background(effectiveTabGlassColor),
                ) {
                    LazyRow(
                        state = tabListState,
                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        itemsIndexed(
                            items = orderedTabs,
                            key = { _, tab -> tab.name },
                        ) { _, tab ->
                            ReorderableItem(tabReorderState, key = tab.name) { isDragging ->
                                val isSelected = selectedTab == tab
                                val itemColor =
                                    if (isSelected) {
                                        effectiveTabContentColor
                                    } else {
                                        effectiveTabContentColor.copy(alpha = 0.76f)
                                    }
                                Box(
                                    modifier =
                                        Modifier
                                            .height(64.dp)
                                            .longPressDraggableHandle(
                                                onDragStarted = {
                                                    haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                                                },
                                            ),
                                ) {
                                    Tab(
                                        selected = isSelected,
                                        selectedContentColor = itemColor,
                                        unselectedContentColor = itemColor,
                                        onClick = {
                                            if (!isDragging && (selectedTab != tab || currentPaneRoute != tab.route)) {
                                                selectedTab = tab
                                                val restoredExistingTab =
                                                    paneNavController.popBackStack(tab.route, inclusive = false)
                                                if (!restoredExistingTab) {
                                                    paneNavController.navigate(tab.route) {
                                                        launchSingleTop = true
                                                        restoreState = false
                                                    }
                                                }
                                            }
                                        },
                                        icon = {
                                            Icon(
                                                painter = painterResource(tab.icon),
                                                contentDescription = tab.title,
                                                tint = itemColor,
                                            )
                                        },
                                        text = {
                                            Text(
                                                text = tab.title,
                                                maxLines = 1,
                                                color = itemColor,
                                            )
                                        },
                                        modifier = Modifier.fillMaxSize(),
                                    )
                                    if (isSelected) {
                                        Box(
                                            modifier =
                                                Modifier
                                                    .align(Alignment.BottomCenter)
                                                    .padding(bottom = 4.dp)
                                                    .width(30.dp)
                                                    .height(3.dp)
                                                    .clip(RoundedCornerShape(50))
                                                    .background(effectiveTabContentColor.copy(alpha = 0.88f)),
                                        )
                                    }
                                }
                            }
                        }
                    }
                    Box(
                        modifier =
                            Modifier
                                .align(Alignment.BottomCenter)
                                .fillMaxWidth()
                                .height(1.dp)
                                .background(effectiveTabContentColor.copy(alpha = 0.10f)),
                    )
                }
'''
replace_once(vehicle, old_tab_block, new_tab_block)

player = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt"
old_player = '''                val tabContentColor = TextBackgroundColor
                val tabScrimColor =
                    if (tabContentColor.luminance() > 0.5f) {
                        Color.Black.copy(alpha = 0.46f)
                    } else {
                        Color.White.copy(alpha = 0.62f)
                    }
                VehicleLandscapeLayout(
                    state = state,
                    showInlineLyrics = showInlineLyrics,
                    playerPaneWeight = dudu7PlayerPaneWeight,
                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },
                    tabContentColor = tabContentColor,
                    tabScrimColor = tabScrimColor,'''
new_player = '''                val tabBackdropColor =
                    when {
                        playerBackground == PlayerBackgroundStyle.GRADIENT && gradientColors.isNotEmpty() ->
                            gradientColors.first()
                        playerBackground == PlayerBackgroundStyle.DEFAULT ->
                            MaterialTheme.colorScheme.surfaceContainer
                        else ->
                            MaterialTheme.colorScheme.surface
                    }
                val tabBackdropIsLight = tabBackdropColor.luminance() >= 0.52f
                val tabContentColor =
                    if (tabBackdropIsLight) {
                        Color.Black.copy(alpha = 0.88f)
                    } else {
                        Color.White.copy(alpha = 0.94f)
                    }
                val tabGlassColor =
                    Color.White.copy(
                        alpha = if (tabBackdropIsLight) 0.24f else 0.13f,
                    )
                VehicleLandscapeLayout(
                    state = state,
                    showInlineLyrics = showInlineLyrics,
                    playerPaneWeight = dudu7PlayerPaneWeight,
                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },
                    tabContentColor = tabContentColor,
                    tabGlassColor = tabGlassColor,'''
replace_once(player, old_player, new_player)

# Replace the scratch-like PNG with a deterministic vector frost field.
# Many short fern-like dendrites and fine needles are used, avoiding long
# through-going lines. The asset is generated once during the build and then
# stored as a normal Android vector drawable.
png = ROOT / "app/src/dudu7/res/drawable-nodpi/dudu7_frost_texture.png"
if png.exists():
    png.unlink()
xml_path = ROOT / "app/src/dudu7/res/drawable/dudu7_frost_texture.xml"
xml_path.parent.mkdir(parents=True, exist_ok=True)

W, H = 1024, 683
rng = random.Random(681015)
layers = {0: [], 1: [], 2: []}
patches = [(rng.uniform(0, W), rng.uniform(0, H), rng.uniform(100, 240)) for _ in range(14)]


def add_segment(layer, x1, y1, x2, y2):
    if max(x1, x2) < -20 or min(x1, x2) > W + 20:
        return
    if max(y1, y2) < -20 or min(y1, y2) > H + 20:
        return
    layers[layer].append((x1, y1, x2, y2))


for _ in range(260):
    pcx, pcy, radius = rng.choice(patches)
    radial_angle = rng.uniform(0, math.tau)
    radial_distance = radius * math.sqrt(rng.random())
    x = pcx + math.cos(radial_angle) * radial_distance
    y = pcy + math.sin(radial_angle) * radial_distance
    direction = rng.uniform(0, math.tau)
    length = rng.uniform(18, 72)
    segments = max(4, int(length / 7))
    points = [(x, y)]
    current_angle = direction
    px, py = x, y
    for _segment in range(1, segments + 1):
        current_angle += rng.uniform(-0.055, 0.055)
        step = length / segments
        px += math.cos(current_angle) * step
        py += math.sin(current_angle) * step
        points.append((px, py))
    stem_layer = 2 if length > 45 and rng.random() < 0.45 else 1
    for start, end in zip(points[:-1], points[1:]):
        add_segment(stem_layer, *start, *end)
    for index in range(1, segments):
        progress = index / segments
        bx, by = points[index]
        for side in (-1, 1):
            if rng.random() >= 0.88:
                continue
            branch_length = length * (0.22 * (1 - progress) + 0.045) * rng.uniform(0.7, 1.25)
            branch_angle = current_angle + side * rng.uniform(0.58, 0.95)
            ex = bx + math.cos(branch_angle) * branch_length
            ey = by + math.sin(branch_angle) * branch_length
            add_segment(1 if branch_length > 7 else 0, bx, by, ex, ey)
            if branch_length > 7:
                for fraction in (0.38, 0.68):
                    if rng.random() >= 0.75:
                        continue
                    mx = bx + (ex - bx) * fraction
                    my = by + (ey - by) * fraction
                    micro_length = branch_length * (0.22 if fraction < 0.5 else 0.14) * rng.uniform(0.7, 1.2)
                    micro_angle = branch_angle + side * rng.uniform(0.65, 1.0)
                    add_segment(
                        0,
                        mx,
                        my,
                        mx + math.cos(micro_angle) * micro_length,
                        my + math.sin(micro_angle) * micro_length,
                    )

for _ in range(55):
    pcx, pcy, radius = rng.choice(patches)
    x = pcx + rng.uniform(-radius, radius)
    y = pcy + rng.uniform(-radius, radius)
    arms = rng.randint(4, 7)
    base_angle = rng.uniform(0, math.tau)
    arm_radius = rng.uniform(16, 48)
    for arm in range(arms):
        angle = base_angle + arm * math.tau / arms + rng.uniform(-0.12, 0.12)
        ex = x + math.cos(angle) * arm_radius
        ey = y + math.sin(angle) * arm_radius
        add_segment(1, x, y, ex, ey)
        for fraction in (0.35, 0.58, 0.78):
            bx = x + (ex - x) * fraction
            by = y + (ey - y) * fraction
            needle = arm_radius * (0.18 * (1 - fraction) + 0.05)
            for side in (-1, 1):
                needle_angle = angle + side * rng.uniform(0.7, 1.0)
                add_segment(
                    0,
                    bx,
                    by,
                    bx + math.cos(needle_angle) * needle,
                    by + math.sin(needle_angle) * needle,
                )

for _ in range(1000):
    x = rng.uniform(0, W)
    y = rng.uniform(0, H)
    length = rng.uniform(2.5, 11)
    angle = rng.uniform(0, math.tau)
    add_segment(0, x, y, x + math.cos(angle) * length, y + math.sin(angle) * length)


def number(value):
    return f"{value:.1f}".rstrip("0").rstrip(".")


lines = [
    '<?xml version="1.0" encoding="utf-8"?>',
    '<vector xmlns:android="http://schemas.android.com/apk/res/android"',
    '    android:width="1024dp"',
    '    android:height="683dp"',
    '    android:viewportWidth="1024"',
    '    android:viewportHeight="683">',
]
ellipse_k = 0.5522847498
for cx, cy, radius in patches:
    rx = radius
    ry = radius * 0.65
    left = cx - rx
    right = cx + rx
    top = cy - ry
    bottom = cy + ry
    path_data = (
        f"M {number(cx)} {number(top)} "
        f"C {number(cx + ellipse_k * rx)} {number(top)} {number(right)} {number(cy - ellipse_k * ry)} {number(right)} {number(cy)} "
        f"C {number(right)} {number(cy + ellipse_k * ry)} {number(cx + ellipse_k * rx)} {number(bottom)} {number(cx)} {number(bottom)} "
        f"C {number(cx - ellipse_k * rx)} {number(bottom)} {number(left)} {number(cy + ellipse_k * ry)} {number(left)} {number(cy)} "
        f"C {number(left)} {number(cy - ellipse_k * ry)} {number(cx - ellipse_k * rx)} {number(top)} {number(cx)} {number(top)} Z"
    )
    lines.append(
        f'    <path android:fillColor="#F4FBFF" android:fillAlpha="0.035" android:pathData="{path_data}" />'
    )

styles = [
    (0, "#F2FAFF", "0.34", "0.65"),
    (1, "#F5FBFF", "0.50", "0.95"),
    (2, "#F8FDFF", "0.68", "1.35"),
]
for layer, color, alpha, width in styles:
    segments = layers[layer]
    for start in range(0, len(segments), 550):
        chunk = segments[start : start + 550]
        path_data = " ".join(
            f"M {number(x1)} {number(y1)} L {number(x2)} {number(y2)}"
            for x1, y1, x2, y2 in chunk
        )
        lines.extend(
            [
                "    <path",
                '        android:fillColor="@android:color/transparent"',
                f'        android:strokeColor="{color}"',
                f'        android:strokeAlpha="{alpha}"',
                f'        android:strokeWidth="{width}"',
                '        android:strokeLineCap="round"',
                '        android:strokeLineJoin="round"',
                f'        android:pathData="{path_data}" />',
            ]
        )
lines.append("</vector>")
xml_path.write_text("\n".join(lines))

vehicle_text = vehicle.read_text()
player_text = player.read_text()
assert "tabScrimColor" not in vehicle_text
assert "tabGlassColor" in vehicle_text and "tabGlassColor" in player_text
assert "if (tab != VehicleRightPaneTab.QUEUE)" not in vehicle_text
assert "paneNavController.navigate(tab.route)" in vehicle_text
assert "alpha = normalized * 0.46f" in vehicle_text
assert xml_path.stat().st_size > 150_000
print("Applied issues #68, #96 and #101")
