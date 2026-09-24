#!/usr/bin/env python3
from pathlib import Path
import math
import random
import struct
import zlib

ROOT = Path('.')


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        raise RuntimeError(f'Expected text not found in {path}: {old[:100]!r}')
    path.write_text(text.replace(old, new, 1))


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)
        start = y * stride
        rows.extend(rgba[start:start + stride])
    payload = b'\x89PNG\r\n\x1a\n'
    payload += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
    payload += chunk(b'IDAT', zlib.compress(bytes(rows), 9))
    payload += chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def generate_frost_texture(path: Path, width: int = 768, height: int = 512) -> None:
    rng = random.Random(20260804)
    alpha = bytearray(width * height)

    def put(x: int, y: int, value: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            i = y * width + x
            if value > alpha[i]:
                alpha[i] = min(255, value)

    def line(x0: float, y0: float, x1: float, y1: float, value: int, thickness: int = 1) -> None:
        dx = x1 - x0
        dy = y1 - y0
        steps = max(1, int(max(abs(dx), abs(dy))))
        radius = max(0, thickness // 2)
        for n in range(steps + 1):
            t = n / steps
            x = int(round(x0 + dx * t))
            y = int(round(y0 + dy * t))
            for oy in range(-radius, radius + 1):
                for ox in range(-radius, radius + 1):
                    if ox * ox + oy * oy <= radius * radius + 1:
                        put(x + ox, y + oy, value)

    def branch(x: float, y: float, angle: float, length: float, depth: int, value: int, thickness: int) -> None:
        if depth <= 0 or length < 7:
            return
        steps = max(3, int(length / 8))
        cx, cy, current_angle = x, y, angle
        for step_index in range(steps):
            current_angle += rng.uniform(-0.09, 0.09)
            step = length / steps
            nx = cx + math.cos(current_angle) * step
            ny = cy + math.sin(current_angle) * step
            line(cx, cy, nx, ny, value, thickness)
            cx, cy = nx, ny
            if 0 < step_index < steps - 1 and rng.random() < 0.76:
                for sign in (-1, 1):
                    if rng.random() < 0.68:
                        side_angle = current_angle + sign * rng.uniform(0.52, 1.04)
                        side_length = length * rng.uniform(0.10, 0.23)
                        line(
                            cx,
                            cy,
                            cx + math.cos(side_angle) * side_length,
                            cy + math.sin(side_angle) * side_length,
                            int(value * rng.uniform(0.54, 0.82)),
                            1,
                        )
        for sign in (-1, 1):
            if rng.random() < 0.88:
                branch(
                    cx,
                    cy,
                    current_angle + sign * rng.uniform(0.24, 0.62),
                    length * rng.uniform(0.43, 0.66),
                    depth - 1,
                    int(value * 0.84),
                    max(1, thickness - 1),
                )

    coarse_w, coarse_h = 34, 24
    coarse = [[rng.random() for _ in range(coarse_w)] for _ in range(coarse_h)]
    for y in range(height):
        fy = y * (coarse_h - 1) / max(1, height - 1)
        y0 = int(fy)
        y1 = min(coarse_h - 1, y0 + 1)
        ty = fy - y0
        for x in range(width):
            fx = x * (coarse_w - 1) / max(1, width - 1)
            x0 = int(fx)
            x1 = min(coarse_w - 1, x0 + 1)
            tx = fx - x0
            v0 = coarse[y0][x0] * (1 - tx) + coarse[y0][x1] * tx
            v1 = coarse[y1][x0] * (1 - tx) + coarse[y1][x1] * tx
            cloud = v0 * (1 - ty) + v1 * ty
            edge = min(x / width, (width - 1 - x) / width, y / height, (height - 1 - y) / height)
            edge_boost = max(0.0, 0.20 - edge) * 130
            value = int(max(0.0, (cloud - 0.42) * 80 + edge_boost))
            if value > 0:
                put(x, y, min(72, value))

    for _ in range(25):
        if rng.random() < 0.62:
            edge_name = rng.choice(('left', 'right', 'top', 'bottom'))
            if edge_name == 'left':
                cx, cy = rng.uniform(-18, 90), rng.uniform(0, height)
            elif edge_name == 'right':
                cx, cy = rng.uniform(width - 90, width + 18), rng.uniform(0, height)
            elif edge_name == 'top':
                cx, cy = rng.uniform(0, width), rng.uniform(-18, 78)
            else:
                cx, cy = rng.uniform(0, width), rng.uniform(height - 78, height + 18)
        else:
            cx, cy = rng.uniform(0, width), rng.uniform(0, height)
        rays = rng.randint(6, 13)
        base_angle = rng.random() * math.tau
        for ray in range(rays):
            angle = base_angle + ray * math.tau / rays + rng.uniform(-0.18, 0.18)
            branch(
                cx,
                cy,
                angle,
                rng.uniform(55, 145),
                rng.randint(2, 4),
                rng.randint(75, 148),
                rng.choice((1, 1, 2)),
            )

    source = bytes(alpha)
    blurred = bytearray(len(alpha))
    for y in range(height):
        for x in range(width):
            total = 0
            count = 0
            for oy in (-1, 0, 1):
                yy = y + oy
                if yy < 0 or yy >= height:
                    continue
                row = yy * width
                for ox in (-1, 0, 1):
                    xx = x + ox
                    if 0 <= xx < width:
                        total += source[row + xx]
                        count += 1
            original = source[y * width + x]
            blurred[y * width + x] = max(original, int(total / count * 0.55))

    rgba = bytearray(width * height * 4)
    for i, a in enumerate(blurred):
        base = i * 4
        rgba[base:base + 4] = bytes((255, 255, 255, a))
    write_png(path, width, height, bytes(rgba))


build = ROOT / 'app/build.gradle.kts'
text = build.read_text().replace('versionCode = 1370061', 'versionCode = 1370062')
text = text.replace('versionName = "13.7.52"', 'versionName = "13.7.53"')
build.write_text(text)

webradio = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt'
replace_once(
    webradio,
    '.background(if (isActive) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.48f) else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f))',
    '.background(if (isActive) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainer)',
)
replace_once(
    webradio,
    '''                .background(\n                    if (isActive) {\n                        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f)\n                    } else {\n                        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)\n                    },\n                ).combinedClickable(onClick = onPlay, onLongClick = onLongClick),''',
    '''                .background(\n                    if (isActive) {\n                        MaterialTheme.colorScheme.primaryContainer\n                    } else {\n                        MaterialTheme.colorScheme.surfaceContainer\n                    },\n                ).combinedClickable(onClick = onPlay, onLongClick = onLongClick),''',
)

connection = ROOT / 'app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt'
replace_once(
    connection,
    '''    private fun withStoredRadioArtwork(\n        metadata: com.metrolist.music.models.MediaMetadata?,\n    ): com.metrolist.music.models.MediaMetadata? {\n        if (metadata == null || !isRadioMediaId(metadata.id) || !metadata.thumbnailUrl.isNullOrBlank()) return metadata\n        val storedArtwork =\n            radioStationStore.stations.value\n                .firstOrNull { it.mediaId == metadata.id }\n                ?.favicon\n                ?.takeIf { it.isNotBlank() }\n        return if (storedArtwork == null) metadata else metadata.copy(thumbnailUrl = storedArtwork)\n    }\n''',
    '''    private fun withStoredRadioArtwork(\n        metadata: com.metrolist.music.models.MediaMetadata?,\n    ): com.metrolist.music.models.MediaMetadata? {\n        if (metadata == null || !isRadioMediaId(metadata.id)) return metadata\n        val storedArtwork =\n            radioStationStore.stations.value\n                .firstOrNull { it.mediaId == metadata.id }\n                ?.favicon\n                ?.takeIf { it.isNotBlank() }\n                ?: return metadata\n        val itemArtwork =\n            getPlayerOrNull()\n                ?.currentMediaItem\n                ?.mediaMetadata\n                ?.extras\n                ?.getString("radio_favicon")\n                ?.takeIf { it.isNotBlank() }\n        val currentArtwork = metadata.thumbnailUrl\n        val mayFollowStationArtwork = currentArtwork.isNullOrBlank() || currentArtwork == itemArtwork\n        return if (mayFollowStationArtwork && currentArtwork != storedArtwork) {\n            metadata.copy(thumbnailUrl = storedArtwork)\n        } else {\n            metadata\n        }\n    }\n''',
)

player = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt'
text = player.read_text()
if 'import androidx.compose.ui.graphics.luminance' not in text:
    text = text.replace('import androidx.compose.ui.graphics.toArgb\n', 'import androidx.compose.ui.graphics.toArgb\nimport androidx.compose.ui.graphics.luminance\n', 1)
needle = '''                VehicleLandscapeLayout(\n                    state = state,\n                    showInlineLyrics = showInlineLyrics,\n                    playerPaneWeight = dudu7PlayerPaneWeight,\n                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },\n'''
replacement = '''                val tabContentColor = TextBackgroundColor\n                val tabScrimColor =\n                    if (tabContentColor.luminance() > 0.5f) {\n                        Color.Black.copy(alpha = 0.46f)\n                    } else {\n                        Color.White.copy(alpha = 0.62f)\n                    }\n                VehicleLandscapeLayout(\n                    state = state,\n                    showInlineLyrics = showInlineLyrics,\n                    playerPaneWeight = dudu7PlayerPaneWeight,\n                    onToggleLyrics = { if (!isWebRadio) showInlineLyrics = !showInlineLyrics },\n                    tabContentColor = tabContentColor,\n                    tabScrimColor = tabScrimColor,\n'''
if needle not in text:
    raise RuntimeError('VehicleLandscapeLayout call marker missing')
player.write_text(text.replace(needle, replacement, 1))

layout = ROOT / 'app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt'
text = layout.read_text()
text = text.replace('import androidx.compose.foundation.Canvas\n', 'import androidx.compose.foundation.Image\n', 1)
text = text.replace('import androidx.compose.ui.graphics.BlendMode\n', '', 1)
text = text.replace('import androidx.compose.ui.graphics.Color\n', 'import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.CompositingStrategy\nimport androidx.compose.ui.graphics.graphicsLayer\n', 1)
text = text.replace('import androidx.compose.ui.layout.onGloballyPositioned\n', 'import androidx.compose.ui.layout.ContentScale\nimport androidx.compose.ui.layout.onGloballyPositioned\n', 1)
start = text.index('@Composable\nprivate fun FrostTextureOverlay(')
end = text.index('\n@OptIn(ExperimentalMaterial3Api::class)', start)
text = text[:start] + '''@Composable\nprivate fun FrostTextureOverlay(\n    strength: Int,\n    modifier: Modifier = Modifier,\n) {\n    val normalized = strength.coerceIn(0, 100) / 100f\n    if (normalized <= 0f) return\n    Image(\n        painter = painterResource(R.drawable.dudu7_frost_texture),\n        contentDescription = null,\n        contentScale = ContentScale.Crop,\n        modifier =\n            modifier.graphicsLayer {\n                alpha = normalized * 0.68f\n                compositingStrategy = CompositingStrategy.Offscreen\n            },\n    )\n}\n''' + text[end:]
text = text.replace(
    '''    onToggleLyrics: () -> Unit,\n    thumbnailContent: @Composable () -> Unit,\n''',
    '''    onToggleLyrics: () -> Unit,\n    tabContentColor: Color,\n    tabScrimColor: Color,\n    thumbnailContent: @Composable () -> Unit,\n''',
    1,
)
old_tabs = '''            Column(Modifier.fillMaxSize()) {\n                LazyRow(\n                    state = tabListState,\n                    modifier =\n                        Modifier\n                            .fillMaxWidth()\n                            .height(64.dp),\n                    verticalAlignment = Alignment.CenterVertically,\n                ) {\n                    itemsIndexed(\n                        items = orderedTabs,\n                        key = { _, tab -> tab.name },\n                    ) { _, tab ->\n                        ReorderableItem(tabReorderState, key = tab.name) { isDragging ->\n                            Tab(\n                                selected = selectedTab == tab,\n'''
new_tabs = '''            Column(Modifier.fillMaxSize()) {\n                Surface(\n                    color = tabScrimColor,\n                    shape = RoundedCornerShape(topStart = 22.dp, topEnd = 22.dp, bottomStart = 14.dp, bottomEnd = 14.dp),\n                    tonalElevation = 0.dp,\n                    shadowElevation = 0.dp,\n                    modifier = Modifier.fillMaxWidth().height(64.dp),\n                ) {\n                    LazyRow(\n                        state = tabListState,\n                        modifier = Modifier.fillMaxSize().padding(horizontal = 4.dp),\n                        verticalAlignment = Alignment.CenterVertically,\n                    ) {\n                        itemsIndexed(\n                            items = orderedTabs,\n                            key = { _, tab -> tab.name },\n                        ) { _, tab ->\n                            ReorderableItem(tabReorderState, key = tab.name) { isDragging ->\n                                val isSelected = selectedTab == tab\n                                val itemColor = if (isSelected) tabContentColor else tabContentColor.copy(alpha = 0.78f)\n                                Tab(\n                                    selected = isSelected,\n'''
if old_tabs not in text:
    raise RuntimeError('Tab block start marker missing')
text = text.replace(old_tabs, new_tabs, 1)
old_tab_content = '''                                    Icon(\n                                        painter = painterResource(tab.icon),\n                                        contentDescription = tab.title,\n                                    )\n                                },\n                                text = { Text(tab.title, maxLines = 1) },\n                                modifier =\n                                    Modifier\n                                        .height(64.dp)\n                                        .longPressDraggableHandle(\n'''
new_tab_content = '''                                    Icon(\n                                        painter = painterResource(tab.icon),\n                                        contentDescription = tab.title,\n                                        tint = itemColor,\n                                    )\n                                },\n                                text = { Text(tab.title, maxLines = 1, color = itemColor) },\n                                modifier =\n                                    Modifier\n                                        .padding(horizontal = 2.dp, vertical = 5.dp)\n                                        .height(54.dp)\n                                        .clip(RoundedCornerShape(14.dp))\n                                        .background(if (isSelected) tabContentColor.copy(alpha = 0.14f) else Color.Transparent)\n                                        .longPressDraggableHandle(\n'''
if old_tab_content not in text:
    raise RuntimeError('Tab content marker missing')
text = text.replace(old_tab_content, new_tab_content, 1)
old_close = '''                        }\n                    }\n                }\n\n                CompositionLocalProvider(\n'''
new_close = '''                            }\n                        }\n                    }\n                }\n\n                CompositionLocalProvider(\n'''
if old_close not in text:
    raise RuntimeError('Tab block close marker missing')
text = text.replace(old_close, new_close, 1)
layout.write_text(text)

generate_frost_texture(ROOT / 'app/src/dudu7/res/drawable-nodpi/dudu7_frost_texture.png')

assert 'versionCode = 1370062' in build.read_text()
assert 'versionName = "13.7.53"' in build.read_text()
assert 'dudu7_frost_texture' in layout.read_text()
assert 'Canvas(' not in layout.read_text()
assert 'surfaceVariant.copy(alpha = 0.55f)' not in webradio.read_text()
assert 'mayFollowStationArtwork' in connection.read_text()
assert 'tabScrimColor' in player.read_text()
