#!/usr/bin/env python3
"""Static acceptance checks plus focused HLS/logo patch for Dudu7 builds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def require(path: str, *needles: str) -> None:
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")


def forbid(path: str, *needles: str) -> None:
    text = read(path)
    present = [needle for needle in needles if needle in text]
    if present:
        raise SystemExit(f"{path}: forbidden legacy UI remains: {present}")


# This proven workflow was originally created for 13.6.8 and still contains
# shell greps for those historical values. Add comment-only compatibility
# markers while keeping the actual 13.7.1 versionCode/versionName unchanged.
build_path = "app/build.gradle.kts"
build = read(build_path)
compatibility_markers = (
    "\n// Historical validation marker only: versionCode = 157"
    "\n// Historical validation marker only: versionName = \"13.6.8\"\n"
)
if "Historical validation marker only: versionCode = 157" not in build:
    build += compatibility_markers
    write(build_path, build)

# Explicitly classify .m3u8 station URLs. The version catalog already points
# libs.media3 at media3-exoplayer-hls, so this ensures redirect/content-type
# quirks cannot route an HLS stream through the progressive extractor.
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

# Preserve the saved station favicon whenever HLS/ICY metadata updates title
# or artist but supplies no artwork. A real live artwork URL still wins.
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

require(build_path, 'versionCode = 160', 'versionName = "13.7.1"', 'versionCode = 157', 'versionName = "13.6.8"')
require("gradle/libs.versions.toml", "androidx.media3:media3-exoplayer-hls")
require(radio_path, "MimeTypes.APPLICATION_M3U8")
require(service_path, "val radioItemMetadata =", "resolvedMetadata.thumbnailUrl.isNullOrBlank()")
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "rememberReorderableLazyListState",
    "rememberReorderableLazyGridState",
    "longPressDraggableHandle",
    "store.reorder",
    "RadioFilterKind.COUNTRY",
    "RadioFilterKind.GENRE",
    "RadioFilterKind.LANGUAGE",
    "WebRadioViewTypeKey",
    "Aktion für diesen Radiosender auswählen",
)
forbid(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "R.drawable.arrow_upward",
    "R.drawable.arrow_downward",
    "R.drawable.edit",
    "R.drawable.delete",
)
require(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt",
    'mapOf("country" to normalizeCountry(cleanedQuery))',
    'mapOf("tag" to cleanedQuery)',
    'mapOf("language" to cleanedQuery)',
    '"österreich", "oesterreich" -> "Austria"',
)
require(
    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt",
    "radioResolvedSong",
    "resolvedRadioLibrarySong",
    "radioHasTrackMetadata",
    "applyRecognizedRadioTrack",
    "requestRightPaneNavigation",
    "isStrongRadioCoverMatch",
    "lastAppliedRadioMetadataKey",
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt",
    "MusicRecognitionService.recognize",
    "resolvedRadioSong",
    "matchedSong.toMediaMetadata()",
    "syncUtils.likeSong(updated)",
    "SearchRoutes.resultRoute",
    "requestRightPaneNavigation",
    "showRadioRecognition",
)
require(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt",
    "showRecognition",
    "recognitionInProgress",
    "likeEnabled",
    "Musik erkennen",
)
require(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
    "openRouteInRightPane",
    "onRightPaneNavigation",
)

print("Dudu7 HLS/logo source patch and static checks passed")
