from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker missing in {path}: {old!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/build.gradle.kts",
    '        versionCode = 169\n        versionName = "13.7.10"',
    '        versionCode = 170\n        versionName = "13.7.11"',
)

replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt",
    """            frequencies
                .split(';', ',')
                .map(String::trim)
""",
    """            frequencies
                // Semicolon/newline separate entries. A comma remains part of
                // the German decimal value, e.g. 99,4; 103,2.
                .split(';', '\\n')
                .map(String::trim)
""",
)

print("Applied Dudu7 13.7.11 FM editor decimal-comma final correction")
