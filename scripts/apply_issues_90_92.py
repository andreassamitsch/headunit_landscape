#!/usr/bin/env python3
from pathlib import Path
import urllib.request

UPSTREAM_COMMIT = "42306e421475bcf150a4099b248f20aadfb61e24"
UPSTREAM = f"https://raw.githubusercontent.com/MetrolistGroup/Metrolist/{UPSTREAM_COMMIT}"

COPIES = {
    "app/src/main/assets/player_configs.json": "app/src/main/assets/player_configs.json",
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt":
        "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerConfigStore.kt",
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerDatesStore.kt":
        "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerDatesStore.kt",
}

for remote, local in COPIES.items():
    request = urllib.request.Request(
        f"{UPSTREAM}/{remote}",
        headers={"User-Agent": "MetrolistHU-CI"},
    )
    data = urllib.request.urlopen(request, timeout=30).read()
    path = Path(local)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

build = Path("app/build.gradle.kts")
build_text = build.read_text()
build_text = build_text.replace("versionCode = 1370056", "versionCode = 1370058")
build_text = build_text.replace('versionName = "13.7.47"', 'versionName = "13.7.49"')
build.write_text(build_text)

layout = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt")
text = layout.read_text()
if ".blur(42.dp)" not in text:
    text = text.replace(
        "import androidx.compose.foundation.BorderStroke\n",
        "import androidx.compose.foundation.BorderStroke\n"
        "import androidx.compose.foundation.background\n"
        "import androidx.compose.foundation.border\n",
        1,
    )
    text = text.replace(
        "import androidx.compose.ui.geometry.Offset\n",
        "import androidx.compose.ui.draw.blur\n"
        "import androidx.compose.ui.draw.clip\n"
        "import androidx.compose.ui.draw.clipToBounds\n"
        "import androidx.compose.ui.draw.shadow\n"
        "import androidx.compose.ui.geometry.Offset\n",
        1,
    )
    text = text.replace(
        "import androidx.compose.ui.hapticfeedback.HapticFeedbackType\n",
        "import androidx.compose.ui.graphics.Brush\n"
        "import androidx.compose.ui.graphics.Color\n"
        "import androidx.compose.ui.graphics.graphicsLayer\n"
        "import androidx.compose.ui.hapticfeedback.HapticFeedbackType\n",
        1,
    )
    text = text.replace(
        "import androidx.compose.ui.layout.onGloballyPositioned\n",
        "import androidx.compose.ui.layout.onGloballyPositioned\n"
        "import androidx.compose.ui.semantics.clearAndSetSemantics\n",
        1,
    )

    marker = "    Row(\n        modifier =\n"
    if marker not in text:
        raise RuntimeError("Vehicle Row marker not found")
    backdrop = '''    val glassShape = RoundedCornerShape(24.dp)

    Box(
        modifier =
            Modifier
                .fillMaxSize()
                .clipToBounds(),
    ) {
        Box(
            modifier =
                Modifier
                    .fillMaxSize()
                    .graphicsLayer {
                        scaleX = 1.24f
                        scaleY = 1.24f
                        alpha = 0.92f
                    }.blur(42.dp)
                    .clearAndSetSemantics {},
            contentAlignment = Alignment.Center,
        ) {
            thumbnailContent()
        }
        Box(
            modifier =
                Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            listOf(
                                Color.Black.copy(alpha = 0.22f),
                                Color.Black.copy(alpha = 0.48f),
                                Color.Black.copy(alpha = 0.68f),
                            ),
                        ),
                    ),
        )

        Row(
            modifier =
'''
    text = text.replace(marker, backdrop, 1)

    old_column = '''                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(horizontal = 12.dp, vertical = 4.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),'''
    new_column = '''                Modifier
                    .weight(safePlayerWeight)
                    .fillMaxSize()
                    .padding(start = 8.dp, end = 6.dp)
                    .shadow(10.dp, glassShape)
                    .clip(glassShape)
                    .background(MaterialTheme.colorScheme.surface.copy(alpha = 0.46f))
                    .border(
                        width = 1.dp,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.24f),
                        shape = glassShape,
                    ).padding(horizontal = 12.dp, vertical = 4.dp)
                    .nestedScroll(state.preUpPostDownNestedScrollConnection),'''
    if old_column not in text:
        raise RuntimeError("Player column marker not found")
    text = text.replace(old_column, new_column, 1)

    text = text.replace("shape = RoundedCornerShape(18.dp),", "shape = glassShape,", 1)
    text = text.replace(
        "color = MaterialTheme.colorScheme.surfaceContainer.copy(alpha = 0.78f),",
        "color = MaterialTheme.colorScheme.surface.copy(alpha = 0.52f),",
        1,
    )
    text = text.replace(
        "color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.16f),",
        "color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.24f),",
        1,
    )
    text = text.replace("tonalElevation = 2.dp,", "tonalElevation = 1.dp,", 1)
    text = text.replace("shadowElevation = 6.dp,", "shadowElevation = 10.dp,", 1)

    if not text.endswith("    }\n}\n"):
        raise RuntimeError("Unexpected VehicleLandscapeLayout ending")
    text = text[:-7] + "    }\n    }\n}\n"
    layout.write_text(text)

assert '"c954e338"' in Path("app/src/main/assets/player_configs.json").read_text()
assert "REMOTE_URL" in Path(
    "app/src/main/kotlin/com/metrolist/music/utils/cipher/PlayerDatesStore.kt"
).read_text()
assert "versionCode = 1370058" in build.read_text()
assert 'versionName = "13.7.49"' in build.read_text()
assert ".blur(42.dp)" in layout.read_text()
