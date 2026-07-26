#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


# Keep the normal ExoPlayer module and add HLS as an additional module.
catalog_path = "gradle/libs.versions.toml"
catalog = read(catalog_path)
if "media3-hls =" not in catalog:
    catalog = catalog.replace(
        'media3 = { module = "androidx.media3:media3-exoplayer", version.ref = "media3" }\n',
        'media3 = { module = "androidx.media3:media3-exoplayer", version.ref = "media3" }\n'
        'media3-hls = { module = "androidx.media3:media3-exoplayer-hls", version.ref = "media3" }\n',
        1,
    )
write(catalog_path, catalog)

build_path = "app/build.gradle.kts"
build = read(build_path)
if "implementation(libs.media3.hls)" not in build:
    build = build.replace(
        "    implementation(libs.media3)\n",
        "    implementation(libs.media3)\n    implementation(libs.media3.hls)\n",
        1,
    )
write(build_path, build)

# Radio MediaItems must not share one cache key across an endless stream or HLS
# playlist/segments. Also migrate the obsolete OE3 q4a URL to the current qxa
# HLS endpoint while keeping the station entry itself intact.
radio_path = "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt"
radio = read(radio_path)
if "normalizedRadioPlaybackUrl" not in radio:
    marker = '''private fun String.isHlsStreamUrl(): Boolean {
    val normalized = substringBefore('#').substringBefore('?').lowercase()
    return normalized.endsWith(".m3u8") || normalized.contains("/playlist.m3u8") || normalized.contains("/manifest.m3u8")
}
'''
    replacement = marker + '''
private fun String.normalizedRadioPlaybackUrl(): String {
    val value = trim()
    return if (
        value.contains(
            "orf-live-oe3.mdn.ors.at/out/u/oe3/q4a/manifest.m3u8",
            ignoreCase = true,
        )
    ) {
        "https://orf-live-oe3.mdn.ors.at/out/u/oe3/qxa/manifest.m3u8"
    } else {
        value
    }
}
'''
    if marker not in radio:
        raise SystemExit("RadioStation HLS helper marker missing")
    radio = radio.replace(marker, replacement, 1)

if "val playbackUrl = streamUrl.normalizedRadioPlaybackUrl()" not in radio:
    radio = radio.replace(
        "    fun toMediaItem(): MediaItem {\n        val appMetadata =",
        "    fun toMediaItem(): MediaItem {\n        val playbackUrl = streamUrl.normalizedRadioPlaybackUrl()\n        val appMetadata =",
        1,
    )

radio = radio.replace(
    '''                .setUri(streamUrl)
                .setCustomCacheKey(mediaId)
                .setTag(appMetadata)''',
    '''                .setUri(playbackUrl)
                .setTag(appMetadata)''',
    1,
)
radio = radio.replace('putString("radio_stream_url", streamUrl)', 'putString("radio_stream_url", playbackUrl)', 1)
radio = radio.replace('if (streamUrl.isHlsStreamUrl()) {', 'if (playbackUrl.isHlsStreamUrl()) {', 1)
write(radio_path, radio)

# HLS opens the manifest and media segments as separate DataSpecs. Segment
# requests can have no custom key, so inherit the active radio media id instead
# of throwing "No media id". All radio requests stay outside the song cache.
service_path = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
service = read(service_path)
old_media_id = '            val mediaId = dataSpec.key ?: error("No media id")\n\n            if (isRadioMediaId(mediaId)) {'
new_media_id = '''            val mediaId =
                dataSpec.key
                    ?: if (::player.isInitialized) {
                        player.currentMediaItem?.mediaId?.takeIf { isRadioMediaId(it) }
                    } else {
                        null
                    }
                    ?: error("No media id")

            if (isRadioMediaId(mediaId)) {'''
if old_media_id in service:
    service = service.replace(old_media_id, new_media_id, 1)
elif "player.currentMediaItem?.mediaId?.takeIf { isRadioMediaId(it) }" not in service:
    raise SystemExit("MusicService DataSpec media-id marker missing")

service = service.replace('"User-Agent" to "MetrolistHU/13.6.5",', '"User-Agent" to "MetrolistHU/13.7.2",', 1)

# Preserve the station favicon when live metadata changes title/artist but does
# not contain artwork.
old_events = '''        if (events.containsAny(EVENT_TIMELINE_CHANGED, EVENT_POSITION_DISCONTINUITY)) {
            currentMediaMetadata.value = player.currentMetadata
        }
'''
new_events = '''        if (events.containsAny(EVENT_TIMELINE_CHANGED, EVENT_POSITION_DISCONTINUITY)) {
            val resolvedMetadata = player.currentMetadata
            val radioItemMetadata =
                player.currentMediaItem?.localConfiguration?.tag as? com.metrolist.music.models.MediaMetadata
            val previousMetadata = currentMediaMetadata.value
            currentMediaMetadata.value =
                if (
                    resolvedMetadata != null &&
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
if old_events in service:
    service = service.replace(old_events, new_events, 1)
elif "val radioItemMetadata =" not in service:
    raise SystemExit("MusicService player metadata marker missing")
write(service_path, service)

checks = {
    catalog_path: ["media3-exoplayer", "media3-exoplayer-hls"],
    build_path: ["implementation(libs.media3)", "implementation(libs.media3.hls)"],
    radio_path: [
        "normalizedRadioPlaybackUrl",
        "qxa/manifest.m3u8",
        ".setUri(playbackUrl)",
        "MimeTypes.APPLICATION_M3U8",
    ],
    service_path: [
        "player.currentMediaItem?.mediaId?.takeIf { isRadioMediaId(it) }",
        '"User-Agent" to "MetrolistHU/13.7.2"',
        "val radioItemMetadata =",
    ],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

print("Dudu7 13.7.2 HLS regression patch applied successfully")
