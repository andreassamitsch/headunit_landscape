from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
BUILD = ROOT / "app/build.gradle.kts"


def replace_exact(text: str, old: str, new: str, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"Expected {expected} occurrence(s) of {old!r}, found {count}")
    return text.replace(old, new)


layout = LAYOUT.read_text(encoding="utf-8")
layout = replace_exact(
    layout,
    "import androidx.compose.material3.Icon\nimport androidx.compose.material3.MaterialTheme",
    "import androidx.compose.material3.Icon\nimport androidx.compose.material3.LocalContentColor\nimport androidx.compose.material3.MaterialTheme",
)
layout = replace_exact(
    layout,
    "                color = if (frostedIceEnabled) frostedColors.surfaceContainer else baseColors.surfaceContainer,\n                border = null,",
    "                color = if (frostedIceEnabled) frostedColors.surfaceContainer else baseColors.surfaceContainer,\n                contentColor = if (frostedIceEnabled) adaptiveContentColor else baseColors.onSurface,\n                border = null,",
)
layout = replace_exact(
    layout,
    "                CompositionLocalProvider(\n                    LocalNavController provides paneNavController,",
    "                CompositionLocalProvider(\n                    LocalContentColor provides\n                        if (frostedIceEnabled) adaptiveContentColor else baseColors.onSurface,\n                    LocalNavController provides paneNavController,",
)
LAYOUT.write_text(layout, encoding="utf-8")

build = BUILD.read_text(encoding="utf-8")
build = replace_exact(build, "versionCode = 1370065", "versionCode = 1370066")
build = replace_exact(build, 'versionName = "13.7.56"', 'versionName = "13.7.57"')
BUILD.write_text(build, encoding="utf-8")

print("Issue #106 complete adaptive content-color patch applied")
