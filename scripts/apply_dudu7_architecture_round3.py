#!/usr/bin/env python3
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
path = root / "scripts/verify_dudu7_architecture.py"
text = path.read_text(encoding="utf-8")
replacements = [
    (
        '    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/EmbeddedArtistScreen.kt",\n',
        '    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/EmbeddedArtistScreen.kt",\n'
        '    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/EmbeddedArtistItemsScreen.kt",\n',
    ),
    (
        '        "coverUrl = song.thumbnail.resize(1200, 1200)",\n',
        '        "preferredCover ?: song.thumbnail.resize(1200, 1200)",\n'
        '        "fun applyRecognized(",\n',
    ),
    (
        '        "EmbeddedArtistScreen(navController)",\n'
        '        "if (embeddedInPlayer)",\n',
        '        "EmbeddedArtistScreen(navController)",\n'
        '        "EmbeddedArtistItemsScreen(navController)",\n'
        '        "if (embeddedInPlayer)",\n',
    ),
    (
        '        "syncUtils.likeSong(updated)",\n'
        '        "radio.saveCurrentPreset()",\n',
        '        "syncUtils.likeSong(updated)",\n'
        '        "radio.saveCurrentPreset()",\n'
        '        "FM-Musik erkennen",\n'
        '        "MusicRecognitionService.recognize(context)",\n',
    ),
    (
        '    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt": (\n'
        '        "database.withTransaction",\n'
        '        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",\n'
        '    ),\n',
        '    "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt": (\n'
        '        "database.withTransaction",\n'
        '        "incrementTotalPlayTime(mediaItem.mediaId, playbackStats.totalPlayTimeMs)",\n'
        '        "explicitQueueRequestGate.isCurrent",\n'
        '    ),\n'
        '    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt": (\n'
        '        "RadioBrowserClient.refreshStation",\n'
        '        "mergeSavedStationUpdates",\n'
        '        "replaceFavoriteStation",\n'
        '    ),\n',
    ),
]
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected architecture token not found: {old[:120]!r}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# The app test source set uses JUnit directly rather than kotlin.test.
test_import_fixes = {
    root / "app/src/test/kotlin/com/metrolist/music/radio/RadioFavoriteQueueTest.kt": (
        "import kotlin.test.Test\nimport kotlin.test.assertEquals",
        "import org.junit.Assert.assertEquals\nimport org.junit.Test",
    ),
    root / "app/src/test/kotlin/com/metrolist/music/playback/LatestRequestGateTest.kt": (
        "import kotlin.test.Test\nimport kotlin.test.assertFalse\nimport kotlin.test.assertTrue",
        "import org.junit.Assert.assertFalse\nimport org.junit.Assert.assertTrue\nimport org.junit.Test",
    ),
}
for test_path, (old, new) in test_import_fixes.items():
    test_text = test_path.read_text(encoding="utf-8")
    if old not in test_text:
        raise SystemExit(f"Expected test imports not found in {test_path}")
    test_path.write_text(test_text.replace(old, new, 1), encoding="utf-8")

# Android Gradle resolves a relative workflow keystore path from the app module.
# Mirror the already committed Dudu7 key into that expected temporary location.
source_key = root / "app/keystore/dudu7-debug.keystore"
module_relative_key = root / "app/app/keystore/dudu7-debug.keystore"
module_relative_key.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(source_key, module_relative_key)

print("Updated Dudu7 architecture, JUnit imports and signing path for round 3")
