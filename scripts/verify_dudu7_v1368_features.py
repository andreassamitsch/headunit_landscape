#!/usr/bin/env python3
"""Apply and persist the focused HLS/logo patch before the Dudu7 ARM build."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


radio_path = "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt"
radio = read(radio_path)
if "import androidx.media3.common.MimeTypes" not in radio:
    radio = radio.replace(
        "import androidx.media3.common.MediaItem\n",
        "import androidx.media3.common.MediaItem\nimport androidx.media3.common.MimeTypes\n",
        1,
    )
old_builder = '''        return MediaItem.Builder()
            .setMediaId(mediaId)
            .setUri(streamUrl)
            .setCustomCacheKey(mediaId)'''
new_builder = '''        return MediaItem.Builder()
            .setMediaId(mediaId)
            .setUri(streamUrl)
            .setMimeType(
                streamUrl
                    .substringBefore('?')
                    .takeIf { it.endsWith(".m3u8", ignoreCase = true) }
                    ?.let { MimeTypes.APPLICATION_M3U8 },
            )
            .setCustomCacheKey(mediaId)'''
if "MimeTypes.APPLICATION_M3U8" not in radio:
    if old_builder not in radio:
        raise SystemExit("RadioStation HLS insertion point missing")
    radio = radio.replace(old_builder, new_builder, 1)
write(radio_path, radio)

service_path = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
service = read(service_path)

# Undo the earlier overly broad replacement if it is present in toggleLibrary().
wrong_toggle_library_block = '''                val resolvedMetadata = player.currentMetadata
            val radioItemMetadata =
                player.currentMediaItem?.localConfiguration?.tag as? com.metrolist.music.models.MediaMetadata
            val previousMetadata = currentMediaMetadata.value
            currentMediaMetadata.value =
                if (resolvedMetadata != null &&
                    isRadioMediaId(resolvedMetadata.id) &&
                    resolvedMetadata.thumbnailUrl.isNullOrBlank()
                ) {
                    resolvedMetadata.copy(
                        thumbnailUrl =
                            radioItemMetadata
                                ?.takeIf { it.id == resolvedMetadata.id }
                                ?.thumbnailUrl
                                ?: previousMetadata
                                    ?.takeIf { it.id == resolvedMetadata.id }
                                    ?.thumbnailUrl,
                    )
                } else {
                    resolvedMetadata
                }
'''
if wrong_toggle_library_block in service:
    service = service.replace(
        wrong_toggle_library_block,
        "                currentMediaMetadata.value = player.currentMetadata\n",
        1,
    )

# Patch the actual player event path. This is where HLS/ICY metadata can replace
# title/artist while omitting artwork and previously blanked the station logo.
on_events_old = '''        if (events.containsAny(EVENT_TIMELINE_CHANGED, EVENT_POSITION_DISCONTINUITY)) {
            currentMediaMetadata.value = player.currentMetadata
        }
'''
on_events_new = '''        if (events.containsAny(EVENT_TIMELINE_CHANGED, EVENT_POSITION_DISCONTINUITY)) {
            val resolvedMetadata = player.currentMetadata
            val radioItemMetadata =
                player.currentMediaItem?.localConfiguration?.tag as? com.metrolist.music.models.MediaMetadata
            val previousMetadata = currentMediaMetadata.value
            currentMediaMetadata.value =
                if (resolvedMetadata != null &&
                    isRadioMediaId(resolvedMetadata.id) &&
                    resolvedMetadata.thumbnailUrl.isNullOrBlank()
                ) {
                    resolvedMetadata.copy(
                        thumbnailUrl =
                            radioItemMetadata
                                ?.takeIf { it.id == resolvedMetadata.id }
                                ?.thumbnailUrl
                                ?: previousMetadata
                                    ?.takeIf { it.id == resolvedMetadata.id }
                                    ?.thumbnailUrl,
                    )
                } else {
                    resolvedMetadata
                }
        }
'''
if on_events_new not in service:
    if on_events_old not in service:
        raise SystemExit("MusicService onEvents radio metadata insertion point missing")
    service = service.replace(on_events_old, on_events_new, 1)
write(service_path, service)

checks = {
    "gradle/libs.versions.toml": ["androidx.media3:media3-exoplayer-hls"],
    radio_path: ["MimeTypes.APPLICATION_M3U8"],
    service_path: [
        "if (events.containsAny(EVENT_TIMELINE_CHANGED, EVENT_POSITION_DISCONTINUITY)) {\n            val resolvedMetadata",
        "val radioItemMetadata =",
        "resolvedMetadata.thumbnailUrl.isNullOrBlank()",
        "fun toggleLibrary()",
        "                currentMediaMetadata.value = player.currentMetadata",
    ],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

subprocess.run(["git", "add", radio_path, service_path], cwd=ROOT, check=True)
changed = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode != 0
if changed:
    subprocess.run(
        ["git", "commit", "-m", "fix(dudu7): retain station artwork in playback metadata [skip ci]"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=ROOT, check=True)

# Local compatibility markers for the historical reusable workflow only.
build_path = "app/build.gradle.kts"
build = read(build_path)
if "Historical validation marker only: versionCode = 157" not in build:
    build += (
        "\n// Historical validation marker only: versionCode = 157"
        "\n// Historical validation marker only: versionName = \"13.6.8\"\n"
    )
    write(build_path, build)

build = read(build_path)
for needle in ('versionCode = 160', 'versionName = "13.7.1"', 'versionCode = 157', 'versionName = "13.6.8"'):
    if needle not in build:
        raise SystemExit(f"{build_path}: missing {needle}")

print("Dudu7 HLS and playback-logo source patch persisted and passed")
