/**
 * Web radio integration inspired by Transistor (MIT License)
 * https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import android.os.Bundle
import androidx.core.net.toUri
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata.MEDIA_TYPE_RADIO_STATION
import com.metrolist.music.models.MediaMetadata

const val RADIO_MEDIA_ID_PREFIX = "radio:"

fun isRadioMediaId(mediaId: String?): Boolean = mediaId?.startsWith(RADIO_MEDIA_ID_PREFIX) == true

data class RadioStation(
    val uuid: String,
    val name: String,
    val streamUrl: String,
    val homepage: String = "",
    val favicon: String = "",
    val country: String = "",
    val language: String = "",
    val tags: String = "",
    val codec: String = "",
    val bitrate: Int = 0,
) {
    val mediaId: String get() = "$RADIO_MEDIA_ID_PREFIX$uuid"

    fun toMediaItem(): MediaItem {
        val appMetadata =
            MediaMetadata(
                id = mediaId,
                title = name,
                artists = listOf(MediaMetadata.Artist(id = null, name = "WebRadio")),
                duration = -1,
                thumbnailUrl = favicon.takeIf { it.isNotBlank() },
                album = MediaMetadata.Album(id = mediaId, title = country.ifBlank { "Live Radio" }),
            )

        return MediaItem.Builder()
            .setMediaId(mediaId)
            .setUri(streamUrl)
            .setCustomCacheKey(mediaId)
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
                            putString("radio_country", country)
                        },
                    ).build(),
            ).build()
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
        country = extras?.getString("radio_country").orEmpty(),
    )
}
