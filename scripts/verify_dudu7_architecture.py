#!/usr/bin/env python3
"""Fast structural checks for the maintainable Dudu7 layer."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "app/src/main/kotlin/com/metrolist/music/variant/Dudu7Layout.kt",
    "app/src/standard/kotlin/com/metrolist/music/variant/VehicleVariantConfig.kt",
    "app/src/standard/kotlin/com/metrolist/music/variant/VehicleVariantDefaults.kt",
    "app/src/standard/kotlin/com/metrolist/music/variant/VehicleEmptyPlayer.kt",
    "app/src/standard/kotlin/com/metrolist/music/variant/VehicleSettingsScreen.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleVariantConfig.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleVariantDefaults.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleEmptyPlayer.kt",
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleSettingsScreen.kt",
    "app/src/dudu7/AndroidManifest.xml",
    "app/src/test/kotlin/com/metrolist/music/variant/Dudu7LayoutTest.kt",
    "docs/DUDU7_ARCHITECTURE.md",
)

missing = [path for path in REQUIRED_FILES if not (ROOT / path).is_file()]
if missing:
    raise SystemExit("Fehlende Dudu7-Architekturdateien: " + ", ".join(missing))

build_gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
required_gradle_tokens = (
    'flavorDimensions += listOf("variant", "device")',
    'create("standard")',
    'create("dudu7")',
    'buildConfigField("Boolean", "IS_DUDU7", "false")',
    'buildConfigField("Boolean", "IS_DUDU7", "true")',
    "testImplementation(libs.junit)",
)
missing_tokens = [token for token in required_gradle_tokens if token not in build_gradle]
if missing_tokens:
    raise SystemExit("Fehlende Gradle-Konfiguration: " + ", ".join(missing_tokens))

main_activity = (ROOT / "app/src/main/kotlin/com/metrolist/music/MainActivity.kt").read_text(encoding="utf-8")
for token in (
    "VehicleVariantConfig.isDudu7 && dudu7AlwaysStartPlayer",
    'composable("vehicle_settings")',
):
    if token not in main_activity:
        raise SystemExit(f"Fehlender MainActivity-Erweiterungspunkt: {token}")

player = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt").read_text(encoding="utf-8")
for token in (
    "dudu7PlayerPaneWeight",
    "VehicleEmptyPlayer(navController = navController)",
    "moveTaskToBack(true)",
):
    if token not in player:
        raise SystemExit(f"Fehlender Player-Erweiterungspunkt: {token}")

queue = (ROOT / "app/src/main/kotlin/com/metrolist/music/ui/player/Queue.kt").read_text(encoding="utf-8")
for token in (
    "rememberReorderableLazyListState",
    "moveMediaItem",
    "dudu7SwipeToRemoveQueue",
    'navController.navigate("vehicle_settings")',
):
    if token not in queue:
        raise SystemExit(f"Fehlender Queue-Erweiterungspunkt: {token}")

obsolete = (
    "scripts/apply_dudu7_fixes.py",
    "scripts/apply_liked_playlist_fixes.py",
    "scripts/migrate_dudu7_core.py",
    "scripts/migrate_dudu7_core_v2.py",
    ".github/workflows/migrate-dudu7-layer.yml",
)
remaining = [path for path in obsolete if (ROOT / path).exists()]
if remaining:
    raise SystemExit("Einmalige Build-/Migrationsskripte sind noch vorhanden: " + ", ".join(remaining))

print("Dudu7 architecture verification passed")
