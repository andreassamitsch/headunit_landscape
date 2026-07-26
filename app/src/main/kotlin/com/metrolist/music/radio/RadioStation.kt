/**
 * Web radio integration inspired by Transistor (MIT License)
 * https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import android.os.Bundle
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata.MEDIA_TYPE_RADIO_STATION
import androidx.media3.common.MimeTypes
import com.metrolist.music.models.MediaMetadata

const val RADIO_MEDIA_ID_PREFIX = "radio:"

fun isRadioMediaId(mediaId: String?): Boolean = mediaId?.startsWith(RADIO_MEDIA_ID_PREFIX) == true

private fun String.isHlsStreamUrl(): Boolean {
    val normalized = substringBefore('#').substringBefore('?').lowercase()
    return normalized.endsWith(".m3u8") || normalized.contains("/playlist.m3u8") || normalized.contains("/manifest.m3u8")
}

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

data class RadioStation(
    val uuid: String,
    val name: String,
    val streamUrl: String,
    val homepage: String = "",
    val favicon: String = "",
    val manualFavicon: Boolean = false,
    val country: String = "",
    val language: String = "",
    val tags: String = "",
    val codec: String = "",
    val bitrate: Int = 0,
) {
    val mediaId: String get() = "$RADIO_MEDIA_ID_PREFIX$uuid"

    fun toMediaItem(): MediaItem {
        val playbackUrl = streamUrl.normalizedRadioPlaybackUrl()
        val appMetadata =
            MediaMetadata(
                id = mediaId,
                title = name,
                artists = listOf(MediaMetadata.Artist(id = null, name = "WebRadio")),
                duration = -1,
                thumbnailUrl = favicon.takeIf { it.isNotBlank() },
                album = MediaMetadata.Album(id = mediaId, title = country.ifBlank { "Live Radio" }),
            )

        val builder =
            MediaItem.Builder()
                .setMediaId(mediaId)
                .setUri(playbackUrl)
                .setTag(appMetadata)
                .setMediaMetadata(
                    androidx.media3.common.MediaMetadata.Builder()
                        .setTitle(name)
                        .setDisplayTitle(name)
                        .setArtist("WebRadio")
                        .setAlbumTitle(country.ifBlank { "Live Radio" })
                        .setArtworkUri(favicon.takeIf { it.isNotBlank() }?.toUri())
                        .setMediaType(MEDIA_TYPE_RADIO_STATION)
                        .setIsBrowsable(false)
                        .setIsPlayable(true)
                        .setExtras(
                            Bundle().apply {
                                putString("radio_uuid", uuid)
                                putString("radio_name", name)
                                putString("radio_stream_url", streamUrl)
                                putString("radio_favicon", favicon)
                                putBoolean("radio_manual_favicon", manualFavicon)
                                putString("radio_country", country)
                            },
                        ).build(),
                )

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

        return builder.build()
    }
}

fun MediaItem.toRadioStationOrNull(): RadioStation? {
    if (!isRadioMediaId(mediaId)) return null
    val extras = mediaMetadata.extras
    return RadioStation(
        uuid = extras?.getString("radio_uuid") ?: mediaId.removePrefix(RADIO_MEDIA_ID_PREFIX),
        name = extras?.getString("radio_name") ?: mediaMetadata.title?.toString().orEmpty(),
        streamUrl = extras?.getString("radio_stream_url") ?: localConfiguration?.uri?.toString().orEmpty(),
        favicon = extras?.getString("radio_favicon").orEmpty(),
        manualFavicon = extras?.getBoolean("radio_manual_favicon", false) == true,
        country = extras?.getString("radio_country").orEmpty(),
    )
}
