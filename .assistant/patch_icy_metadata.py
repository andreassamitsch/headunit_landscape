from pathlib import Path

player_path = Path('app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt')
text = player_path.read_text(encoding='utf-8')

text = text.replace(
    'import androidx.media3.common.MediaItem\n',
    'import androidx.media3.common.MediaItem\nimport androidx.media3.common.Metadata\n',
    1,
)
text = text.replace(
    'import androidx.media3.exoplayer.ExoPlayer\n',
    'import androidx.media3.exoplayer.ExoPlayer\nimport androidx.media3.extractor.metadata.icy.IcyInfo\n',
    1,
)
text = text.replace(
    'class PlayerConnection(\n',
    '@androidx.media3.common.util.UnstableApi\nclass PlayerConnection(\n',
    1,
)

old = '''    override fun onMediaMetadataChanged(newMetadata: androidx.media3.common.MediaMetadata) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) {
            mediaMetadata.value = base
            return
        }

        val stationName =
            currentItem.mediaMetadata.extras?.getString("radio_name")
                ?.takeIf { it.isNotBlank() }
                ?: base.title
        val rawTitle =
            (newMetadata.title ?: newMetadata.displayTitle)
                ?.toString()
                ?.trim()
                .orEmpty()
                .takeUnless { it.equals(stationName, ignoreCase = true) || it.equals("WebRadio", ignoreCase = true) }
                .orEmpty()

        if (rawTitle.isBlank()) {
            mediaMetadata.value = base
            return
        }

        val parsed = parseRadioStreamTitle(rawTitle)
        val dynamic =
            base.copy(
                title = parsed.second,
                artists =
                    listOf(
                        com.metrolist.music.models.MediaMetadata.Artist(
                            id = null,
                            name = parsed.first ?: stationName,
                        ),
                    ),
            )
        mediaMetadata.value = dynamic

        parsed.first?.takeIf { it.isNotBlank() }?.let { artist ->
            lookupRadioCover(base, artist, parsed.second)
        }
    }
'''

new = '''    override fun onMediaMetadataChanged(newMetadata: androidx.media3.common.MediaMetadata) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) {
            mediaMetadata.value = base
            return
        }

        val stationName =
            currentItem.mediaMetadata.extras?.getString("radio_name")
                ?.takeIf { it.isNotBlank() }
                ?: base.title
        val rawTitle =
            (newMetadata.title ?: newMetadata.displayTitle)
                ?.toString()
                ?.trim()
                .orEmpty()
                .takeUnless { it.equals(stationName, ignoreCase = true) || it.equals("WebRadio", ignoreCase = true) }
                .orEmpty()
        if (rawTitle.isNotBlank()) {
            applyRadioStreamTitle(rawTitle)
        }
    }

    override fun onMetadata(metadata: Metadata) {
        val streamTitle =
            metadata.getFirstEntryOfType(IcyInfo::class.java)
                ?.title
                ?.trim()
                .orEmpty()
        if (streamTitle.isNotBlank()) {
            applyRadioStreamTitle(streamTitle)
        }
    }

    private fun applyRadioStreamTitle(rawTitle: String) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) return

        val stationName =
            currentItem.mediaMetadata.extras?.getString("radio_name")
                ?.takeIf { it.isNotBlank() }
                ?: base.title
        val parsed = parseRadioStreamTitle(rawTitle)
        val dynamic =
            base.copy(
                title = parsed.second,
                artists =
                    listOf(
                        com.metrolist.music.models.MediaMetadata.Artist(
                            id = null,
                            name = parsed.first ?: stationName,
                        ),
                    ),
            )
        mediaMetadata.value = dynamic

        parsed.first?.takeIf { it.isNotBlank() }?.let { artist ->
            lookupRadioCover(base, artist, parsed.second)
        }
    }
'''

if old not in text:
    raise SystemExit('Expected radio metadata method was not found')
text = text.replace(old, new, 1)

required = [
    'override fun onMetadata(metadata: Metadata)',
    'getFirstEntryOfType(IcyInfo::class.java)',
    'private fun applyRadioStreamTitle(rawTitle: String)',
]
for needle in required:
    if needle not in text:
        raise SystemExit(f'Missing expected patch result: {needle}')
for forbidden in ['MetadataOutput', 'addMetadataOutput', 'removeMetadataOutput']:
    if forbidden in text:
        raise SystemExit(f'Unsupported metadata callback API remained: {forbidden}')

player_path.write_text(text, encoding='utf-8')

build_path = Path('app/build.gradle.kts')
build = build_path.read_text(encoding='utf-8')
if 'versionCode = 151' not in build or 'versionName = "13.6.2"' not in build:
    raise SystemExit('Expected current version was not found')
build = build.replace('versionCode = 151', 'versionCode = 152', 1)
build = build.replace('versionName = "13.6.2"', 'versionName = "13.6.3"', 1)
build_path.write_text(build, encoding='utf-8')
