#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


# Build 13.7.3 over the confirmed 13.7.2 Dudu7 feature baseline.
build_path = "app/build.gradle.kts"
build = read(build_path)
build = build.replace("versionCode = 161", "versionCode = 162", 1)
build = build.replace('versionName = "13.7.2"', 'versionName = "13.7.3"', 1)

# Keep the existing ExoPlayer dependency untouched and add HLS separately.
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

if "implementation(libs.media3.hls)" not in build:
    build = build.replace(
        "    implementation(libs.media3)\n",
        "    implementation(libs.media3)\n    implementation(libs.media3.hls)\n",
        1,
    )
write(build_path, build)

# Preserve the exact legacy MediaItem/cache-key path for ordinary MP3/AAC
# WebRadio streams. Only HLS MediaItems omit the custom cache key, because an
# HLS playlist consists of many independent manifest/segment requests.
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

radio = radio.replace(".setUri(streamUrl)", ".setUri(playbackUrl)", 1)

# Remove the unconditional cache key and re-add it only for non-HLS streams.
radio = radio.replace(
    '''                .setUri(playbackUrl)
                .setCustomCacheKey(mediaId)
                .setTag(appMetadata)''',
    '''                .setUri(playbackUrl)
                .setTag(appMetadata)''',
    1,
)

hls_marker = '''
        // Explicitly mark HLS playlists. This also covers signed/query-string URLs where
        // automatic content-type inference is unreliable on some head-unit firmwares.
        if (streamUrl.isHlsStreamUrl()) {
            builder.setMimeType(MimeTypes.APPLICATION_M3U8)
        }
'''
hls_replacement = '''
        // Normal MP3/AAC streams retain the original radio cache key. The playback
        // resolver depends on it to recognize the request as WebRadio.
        if (!playbackUrl.isHlsStreamUrl()) {
            builder.setCustomCacheKey(mediaId)
        }

        // HLS has a separate Media3 module and a separate request path. Do not give
        // every manifest/segment the same custom cache key.
        if (playbackUrl.isHlsStreamUrl()) {
            builder.setMimeType(MimeTypes.APPLICATION_M3U8)
        }
'''
if hls_marker in radio:
    radio = radio.replace(hls_marker, hls_replacement, 1)
elif "if (!playbackUrl.isHlsStreamUrl())" not in radio:
    raise SystemExit("RadioStation conditional cache-key insertion point missing")

# Keep the original configured stream URL in station metadata/editor state. Only
# the URI actually handed to the player is normalized.
radio = radio.replace('putString("radio_stream_url", playbackUrl)', 'putString("radio_stream_url", streamUrl)', 1)
write(radio_path, radio)

# The old direct-stream path remains: dataSpec.key must contain radio:<uuid>.
# Only while the active item is explicitly HLS may keyless manifest/segment
# requests inherit the active radio id.
service_path = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
service = read(service_path)
old_media_id = '            val mediaId = dataSpec.key ?: error("No media id")\n\n            if (isRadioMediaId(mediaId)) {'
new_media_id = '''            val activeHlsRadioId =
                if (::player.isInitialized) {
                    player.currentMediaItem
                        ?.takeIf { item ->
                            isRadioMediaId(item.mediaId) &&
                                (
                                    item.localConfiguration?.mimeType ==
                                        androidx.media3.common.MimeTypes.APPLICATION_M3U8 ||
                                        item.localConfiguration
                                            ?.uri
                                            ?.toString()
                                            ?.substringBefore('#')
                                            ?.substringBefore('?')
                                            ?.endsWith(".m3u8", ignoreCase = true) == true
                                )
                        }?.mediaId
                } else {
                    null
                }
            val mediaId = activeHlsRadioId ?: dataSpec.key ?: error("No media id")

            if (isRadioMediaId(mediaId)) {'''
if old_media_id in service:
    service = service.replace(old_media_id, new_media_id, 1)
elif "val activeHlsRadioId =" not in service:
    raise SystemExit("MusicService DataSpec media-id marker missing")

service = service.replace('"User-Agent" to "MetrolistHU/13.6.5",', '"User-Agent" to "MetrolistHU/13.7.3",', 1)
service = service.replace('"User-Agent" to "MetrolistHU/13.7.2",', '"User-Agent" to "MetrolistHU/13.7.3",', 1)

# Preserve the station favicon when live ICY/HLS metadata updates title/artist
# without providing artwork.
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
    build_path: [
        "versionCode = 162",
        'versionName = "13.7.3"',
        "implementation(libs.media3)",
        "implementation(libs.media3.hls)",
    ],
    catalog_path: ["media3-exoplayer", "media3-exoplayer-hls"],
    radio_path: [
        "normalizedRadioPlaybackUrl",
        "qxa/manifest.m3u8",
        ".setUri(playbackUrl)",
        "if (!playbackUrl.isHlsStreamUrl())",
        "builder.setCustomCacheKey(mediaId)",
        "MimeTypes.APPLICATION_M3U8",
        'putString("radio_stream_url", streamUrl)',
    ],
    service_path: [
        "val activeHlsRadioId =",
        "val mediaId = activeHlsRadioId ?: dataSpec.key",
        '"User-Agent" to "MetrolistHU/13.7.3"',
        "val radioItemMetadata =",
    ],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

# Regression guard: the direct-stream discriminator must still exist, and it
# must be conditional rather than removed globally as in the broken 13.7.2 APK.
radio_text = read(radio_path)
if radio_text.count("builder.setCustomCacheKey(mediaId)") != 1:
    raise SystemExit("Direct WebRadio cache-key regression guard failed")
if "if (!playbackUrl.isHlsStreamUrl())" not in radio_text:
    raise SystemExit("Normal WebRadio path is not isolated from HLS")

print("Dudu7 13.7.3 WebRadio-safe HLS patch applied successfully")
