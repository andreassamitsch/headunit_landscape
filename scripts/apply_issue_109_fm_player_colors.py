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
old = '''            if (physicalRadioState.isActive) {
                PhysicalRadioPlayerPane(
                    radio = physicalRadio,
                    playerConnection = playerConnection,
                )
            } else {
'''
new = '''            if (physicalRadioState.isActive) {
                MaterialTheme(colorScheme = frostedColors) {
                    CompositionLocalProvider(
                        LocalContentColor provides
                            if (frostedIceEnabled) adaptiveContentColor else baseColors.onSurface,
                    ) {
                        PhysicalRadioPlayerPane(
                            radio = physicalRadio,
                            playerConnection = playerConnection,
                        )
                    }
                }
            } else {
'''
layout = replace_exact(layout, old, new)
LAYOUT.write_text(layout, encoding="utf-8")

build = BUILD.read_text(encoding="utf-8")
build = replace_exact(build, "versionCode = 1370066", "versionCode = 1370067")
build = replace_exact(build, 'versionName = "13.7.57"', 'versionName = "13.7.58"')
BUILD.write_text(build, encoding="utf-8")

print("Issue #109 FM player adaptive color patch applied")
