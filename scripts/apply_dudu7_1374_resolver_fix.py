#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


# New update version, based only on the existing 13.7.3 feature state.
build_path = "app/build.gradle.kts"
build = read(build_path)
build = build.replace("versionCode = 162", "versionCode = 163", 1)
build = build.replace('versionName = "13.7.3"', 'versionName = "13.7.4"', 1)
write(build_path, build)

service_path = "app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt"
service = read(service_path)

# ResolvingDataSource callbacks execute on Media3 loading/playback threads. The
# 13.7.3 implementation queried ExoPlayer.currentMediaItem from inside this
# callback for every request. That violates the player's application-thread
# contract and can abort MP3, AAC and HLS loads before audio reaches the sink.
#
# Restore the original direct-radio path verbatim for keyed radio requests. HLS
# manifests and media segments are intentionally keyless, so they can be passed
# through without touching the player or the finite-song cache.
pattern = re.compile(
    r'''            val activeHlsRadioId =\n'''
    r'''(?:.*\n)*?'''
    r'''            val mediaId = activeHlsRadioId \?: dataSpec\.key \?: error\("No media id"\)\n''',
)
replacement = '''            if (dataSpec.key == null) {
                // HLS manifests and media segments are keyless. Keep this path
                // independent from ExoPlayer state so it is safe on loader threads.
                return@Factory dataSpec
                    .withRequestHeaders(
                        dataSpec.httpRequestHeaders +
                            mapOf(
                                "User-Agent" to "MetrolistHU/13.7.4",
                                "Cache-Control" to "no-cache",
                            ),
                    ).buildUpon()
                    .setFlags(dataSpec.flags or DataSpec.FLAG_DONT_CACHE_IF_LENGTH_UNKNOWN)
                    .build()
            }

            // Existing MP3/AAC WebRadio and YouTube path: the custom key remains
            // the sole discriminator, exactly as before HLS support was added.
            val mediaId = dataSpec.key ?: error("No media id")
'''
service, replacements = pattern.subn(replacement, service, count=1)
if replacements != 1:
    if "HLS manifests and media segments are keyless" not in service:
        raise SystemExit(f"Expected one resolver block replacement, got {replacements}")

service = service.replace('"User-Agent" to "MetrolistHU/13.7.3",', '"User-Agent" to "MetrolistHU/13.7.4",')
write(service_path, service)

checks = {
    build_path: ["versionCode = 163", 'versionName = "13.7.4"'],
    service_path: [
        "if (dataSpec.key == null)",
        "HLS manifests and media segments are keyless",
        '"User-Agent" to "MetrolistHU/13.7.4"',
        'val mediaId = dataSpec.key ?: error("No media id")',
        "if (isRadioMediaId(mediaId))",
    ],
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt": [
        "if (!playbackUrl.isHlsStreamUrl())",
        "builder.setCustomCacheKey(mediaId)",
        "MimeTypes.APPLICATION_M3U8",
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt": [
        "rememberReorderableLazyListState",
        "VehicleTabOrderStore.persist",
        "VEHICLE_PHYSICAL_RADIO_ROUTE",
    ],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

resolver_start = service.index("private fun createDataSourceFactory")
resolver_end = service.index("private fun createMediaSourceFactory", resolver_start)
resolver = service[resolver_start:resolver_end]
for forbidden in ("activeHlsRadioId", "player.currentMediaItem", "player.currentMediaItemIndex"):
    if forbidden in resolver:
        raise SystemExit(f"Unsafe player access remains in resolver: {forbidden}")

print("Dudu7 13.7.4 thread-safe radio resolver patch applied successfully")
