#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "scripts/verify_dudu7_architecture.py"
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
print("Updated Dudu7 architecture checks for round 3")
