#!/usr/bin/env python3
from pathlib import Path


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

artist = artist.replace(
    "    val rightPaneTapTargets = remember { mutableStateMapOf<String, Pair<Rect, () -> Unit>>() }",
    "    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }",
    1,
)

start_marker = "                        val embeddedSectionTapModifier =\n"
end_marker = "                        if (isSongSection) {\n"
start = artist.find(start_marker)
if start >= 0:
    end = artist.find(end_marker, start)
    if end < 0:
        raise SystemExit("ArtistScreen song-section end marker missing")
    replacement = '''                        val sectionTapKey = "${index}_${section.title}"
                        if (section.items.isNotEmpty()) {
                            item(key = "section_${section.title}") {
                                DisposableEffect(sectionTapKey) {
                                    onDispose {
                                        rightPaneTapTargets.remove(sectionTapKey)
                                    }
                                }
                                NavigationTitle(
                                    title = section.title,
                                    modifier =
                                        Modifier
                                            .onGloballyPositioned { coordinates ->
                                                val sectionClick = openSection
                                                if (embeddedInPlayer && sectionClick != null) {
                                                    rightPaneTapTargets[sectionTapKey] =
                                                        coordinates.boundsInRoot() to sectionClick
                                                } else {
                                                    rightPaneTapTargets.remove(sectionTapKey)
                                                }
                                            }.animateItem(),
                                    onClick = openSection,
                                )
                            }
                        }

'''
    artist = artist[:start] + replacement + artist[end:]

required = [
    "rightPaneTapTargets[sectionTapKey]",
    "coordinates.boundsInRoot() to sectionClick",
    "Dudu7ArtistSectionTap",
]
missing = [marker for marker in required if marker not in artist]
if missing:
    raise SystemExit(f"Parent artist tap target markers missing: {missing}")
if "val embeddedSectionTapModifier" in artist:
    raise SystemExit("Obsolete child section tap handler is still present")

artist_path.write_text(artist, encoding="utf-8")
print("Registered artist section tap bounds with the right-pane parent bridge")

# Focused WebRadio fix bundled into the proven Dudu7 validation workflow.
# Media3's HLS module is already selected in libs.versions.toml; explicitly
# classify .m3u8 station URLs so redirects/content-type quirks cannot make the
# generic media source factory treat them as progressive streams.
radio_path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt")
radio = radio_path.read_text(encoding="utf-8")
if "import androidx.media3.common.MimeTypes" not in radio:
    radio = radio.replace(
        "import androidx.media3.common.MediaItem\n",
        "import androidx.media3.common.MediaItem\nimport androidx.media3.common.MimeTypes\n",
        1,
    )
radio_builder = '''        return MediaItem.Builder()
            .setMediaId(mediaId)
            .setUri(streamUrl)
            .setCustomCacheKey(mediaId)'''
radio_builder_hls = '''        return MediaItem.Builder()
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
    if radio_builder not in radio:
        raise SystemExit("RadioStation HLS insertion point missing")
    radio = radio.replace(radio_builder, radio_builder_hls, 1)
radio_path.write_text(radio, encoding="utf-8")

# Live HLS/ICY metadata can contain title/artist but no artwork. Keep accepting
# those live fields while falling back to the station MediaItem's saved favicon
# (or the previous metadata for the same station) instead of blanking the logo.
service_path = Path("app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt")
service = service_path.read_text(encoding="utf-8")
metadata_assignment = "            currentMediaMetadata.value = player.currentMetadata\n"
metadata_assignment_with_logo_fallback = '''            val resolvedMetadata = player.currentMetadata
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
    if metadata_assignment not in service:
        raise SystemExit("MusicService radio metadata insertion point missing")
    service = service.replace(metadata_assignment, metadata_assignment_with_logo_fallback, 1)
service_path.write_text(service, encoding="utf-8")

print("Applied explicit HLS classification and persistent WebRadio logo fallback")
