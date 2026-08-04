from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FM_SCREEN = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
BUILD_GRADLE = ROOT / "app/build.gradle.kts"


def replace_exact(text: str, old: str, new: str, expected: int) -> str:
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"Expected {expected} occurrence(s) of {old!r}, found {count}")
    return text.replace(old, new)


screen = FM_SCREEN.read_text(encoding="utf-8")
screen = replace_exact(
    screen,
    "MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)",
    "MaterialTheme.colorScheme.primaryContainer",
    1,
)
screen = replace_exact(
    screen,
    "MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)",
    "MaterialTheme.colorScheme.surfaceContainer",
    2,
)
screen = replace_exact(
    screen,
    "MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f)",
    "MaterialTheme.colorScheme.surfaceContainer",
    2,
)
FM_SCREEN.write_text(screen, encoding="utf-8")

build = BUILD_GRADLE.read_text(encoding="utf-8")
build = replace_exact(build, "versionCode = 1370063", "versionCode = 1370064", 1)
build = replace_exact(build, 'versionName = "13.7.54"', 'versionName = "13.7.55"', 1)
BUILD_GRADLE.write_text(build, encoding="utf-8")

print("Issue #104 FM glass consistency patch applied")
