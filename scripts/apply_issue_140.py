from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

build = ROOT / "app/build.gradle.kts"
browse = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/BrowseScreen.kt"
factory = ROOT / "app/src/main/kotlin/com/metrolist/music/ui/screens/BrowsePlayback.kt"
test = ROOT / "app/src/test/kotlin/com/metrolist/music/ui/screens/BrowsePlaybackTest.kt"

text = build.read_text(encoding="utf-8")
if 'versionCode = 1370078' not in text:
    if 'versionCode = 1370077' not in text or 'versionName = "13.7.68"' not in text:
        raise RuntimeError("Unexpected base version; expected 13.7.68 / 1370077")
    text = text.replace('versionCode = 1370077', 'versionCode = 1370078', 1)
    text = text.replace('versionName = "13.7.68"', 'versionName = "13.7.69"', 1)
    build.write_text(text, encoding="utf-8")

browse_text = browse.read_text(encoding="utf-8")
factory_text = factory.read_text(encoding="utf-8")
test_text = test.read_text(encoding="utf-8")

assert 'is SongItem -> {' in browse_text
assert 'playerConnection.playQueue(' in browse_text
assert 'createBrowseSongQueue(' in browse_text
assert 'YouTubeQueue(' in factory_text
assert 'ListQueue(' in factory_text
assert 'browse song uses YouTube radio queue when auto radio is enabled' in test_text
assert 'browse song uses single item queue when auto radio is disabled' in test_text
assert 'versionCode = 1370078' in build.read_text(encoding="utf-8")
assert 'versionName = "13.7.69"' in build.read_text(encoding="utf-8")

print("Issue #140 guardrails and 13.7.69 version applied")
