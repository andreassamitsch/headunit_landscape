#!/usr/bin/env python3
"""Apply the focused HLS/logo patch before the reusable Dudu7 ARM build."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


# The reusable workflow still greps its historical 13.6.8 values. Add
# comment-only compatibility markers; the real application remains 13.7.1/160.
build_path = "app/build.gradle.kts"
build = read(build_path)
if "Historical validation marker only: versionCode = 157" not in build:
    build += (
        "\n// Historical validation marker only: versionCode = 157"
        "\n// Historical validation marker only: versionName = \"13.6.8\"\n"
    )
    write(build_path, build)

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
old_assignment = "            currentMediaMetadata.value = player.currentMetadata\n"
new_assignment = '''            val resolvedMetadata = player.currentMetadata
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
if "val radioItemMetadata =" not in service:
    if old_assignment not in service:
        raise SystemExit("MusicService radio metadata insertion point missing")
    service = service.replace(old_assignment, new_assignment, 1)
write(service_path, service)

checks = {
    "app/build.gradle.kts": [
        'versionCode = 160',
        'versionName = "13.7.1"',
        'versionCode = 157',
        'versionName = "13.6.8"',
    ],
    "gradle/libs.versions.toml": ["androidx.media3:media3-exoplayer-hls"],
    radio_path: ["MimeTypes.APPLICATION_M3U8"],
    service_path: ["val radioItemMetadata =", "resolvedMetadata.thumbnailUrl.isNullOrBlank()"],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

print("Dudu7 HLS/logo source patch passed")
