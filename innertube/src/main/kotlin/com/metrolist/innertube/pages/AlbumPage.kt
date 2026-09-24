package com.metrolist.innertube.pages

import com.metrolist.innertube.models.Album
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.innertube.models.Artist
import com.metrolist.innertube.models.MusicResponsiveHeaderRenderer
import com.metrolist.innertube.models.MusicResponsiveListItemRenderer
import com.metrolist.innertube.models.MusicShelfRenderer
import com.metrolist.innertube.models.SongItem
import com.metrolist.innertube.models.getItems
import com.metrolist.innertube.models.oddElements
import com.metrolist.innertube.models.response.BrowseResponse
import com.metrolist.innertube.models.splitBySeparator
import com.metrolist.innertube.utils.parseTime

data class AlbumPage(
    val album: AlbumItem,
    val songs: List<SongItem>,
    val otherVersions: List<AlbumItem>,
) {
    companion object {
        fun getAlbum(response: BrowseResponse, browseId: String): AlbumItem? {
            val playlistId = getPlaylistId(response)?.takeIf(String::isNotBlank) ?: return null
            val title = getTitle(response)?.takeIf(String::isNotBlank) ?: return null
            val thumbnail = getThumbnail(response)?.takeIf(String::isNotBlank) ?: return null
            return AlbumItem(
                browseId = browseId,
                playlistId = playlistId,
                title = title,
                artists = getArtists(response).ifEmpty { null },
                year = getYear(response),
                thumbnail = thumbnail,
                explicit = false,
            )
        }

        fun getPlaylistId(response: BrowseResponse): String? {
            val canonicalPlaylistId =
                response.microformat
                    ?.microformatDataRenderer
                    ?.urlCanonical
                    ?.substringAfter("list=", missingDelimiterValue = "")
                    ?.substringBefore('&')
                    ?.takeIf(String::isNotBlank)
            if (canonicalPlaylistId != null) return canonicalPlaylistId

            val detailHeaderPlaylistId =
                response.header
                    ?.musicDetailHeaderRenderer
                    ?.menu
                    ?.menuRenderer
                    ?.topLevelButtons
                    .orEmpty()
                    .firstNotNullOfOrNull { button ->
                        button.buttonRenderer?.navigationEndpoint?.anyWatchEndpoint?.playlistId
                    }
            if (detailHeaderPlaylistId != null) return detailHeaderPlaylistId

            return getHeader(response)
                ?.buttons
                .orEmpty()
                .firstNotNullOfOrNull { button ->
                    button.musicPlayButtonRenderer?.playNavigationEndpoint?.anyWatchEndpoint?.playlistId
                }
        }

        fun getTitle(response: BrowseResponse): String? {
            val title = getHeader(response)?.title ?: response.header?.musicDetailHeaderRenderer?.title
            return title?.runs?.firstOrNull()?.text
        }

        fun getYear(response: BrowseResponse): Int? {
            val title = getHeader(response)?.subtitle ?: response.header?.musicDetailHeaderRenderer?.subtitle
            return title?.runs?.lastOrNull()?.text?.toIntOrNull()
        }

        fun getThumbnail(response: BrowseResponse): String? =
            response.background?.getThumbnailUrl()
                ?: getHeader(response)?.thumbnail?.getThumbnailUrl()
                ?: response.header?.musicDetailHeaderRenderer?.thumbnail?.getThumbnailUrl()

        fun getArtists(response: BrowseResponse): List<Artist> {
            val responsiveArtists =
                getHeader(response)
                    ?.straplineTextOne
                    ?.runs
                    ?.oddElements()
                    ?.map {
                        Artist(
                            name = it.text,
                            id = it.navigationEndpoint?.browseEndpoint?.browseId,
                        )
                    }
                    .orEmpty()
            if (responsiveArtists.isNotEmpty()) return responsiveArtists

            return response.header
                ?.musicDetailHeaderRenderer
                ?.subtitle
                ?.runs
                ?.filter { it.navigationEndpoint?.browseEndpoint?.browseId != null }
                ?.map {
                    Artist(
                        name = it.text,
                        id = it.navigationEndpoint?.browseEndpoint?.browseId,
                    )
                }
                .orEmpty()
        }

        private fun getHeader(response: BrowseResponse): MusicResponsiveHeaderRenderer? {
            val tabs = response.contents?.singleColumnBrowseResultsRenderer?.tabs
                ?: response.contents?.twoColumnBrowseResultsRenderer?.tabs
            val section =
                tabs?.firstOrNull()?.tabRenderer?.content?.sectionListRenderer?.contents?.firstOrNull()
            val header = section?.musicResponsiveHeaderRenderer
            return header
        }

        fun getShelfContents(response: BrowseResponse): List<MusicShelfRenderer.Content> {
            val tabSections =
                (response.contents?.singleColumnBrowseResultsRenderer?.tabs
                    ?: response.contents?.twoColumnBrowseResultsRenderer?.tabs)
                    ?.firstOrNull()
                    ?.tabRenderer
                    ?.content
                    ?.sectionListRenderer
                    ?.contents
            val secondarySections =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.secondaryContents
                    ?.sectionListRenderer
                    ?.contents

            return (tabSections ?: secondarySections)
                .orEmpty()
                .firstNotNullOfOrNull { section ->
                    section.musicPlaylistShelfRenderer?.contents?.takeIf { it.isNotEmpty() }
                        ?: section.musicShelfRenderer?.contents?.takeIf { it.isNotEmpty() }
                }.orEmpty()
        }

        fun getSongs(response: BrowseResponse, album: AlbumItem): List<SongItem> =
            getShelfContents(response)
                .getItems()
                .mapNotNull { getSong(it, album) }

        fun getSong(renderer: MusicResponsiveListItemRenderer, album: AlbumItem? = null): SongItem? {
            // Extract library tokens using the new method that properly handles multiple toggle items
            val libraryTokens = PageHelper.extractLibraryTokensFromMenuItems(renderer.menu?.menuRenderer?.items)

            return SongItem(
                id = renderer.playlistItemData?.videoId
                    ?: renderer.navigationEndpoint?.watchEndpoint?.videoId
                    ?: renderer.overlay?.musicItemThumbnailOverlayRenderer
                        ?.content?.musicPlayButtonRenderer
                        ?.playNavigationEndpoint?.watchEndpoint?.videoId
                    ?: renderer.flexColumns.firstOrNull()
                        ?.musicResponsiveListItemFlexColumnRenderer
                        ?.text?.runs?.firstOrNull()
                        ?.navigationEndpoint?.watchEndpoint?.videoId
                    ?: return null,
                title = PageHelper.extractRuns(renderer.flexColumns, "MUSIC_VIDEO").firstOrNull()?.text ?: return null,
                artists = PageHelper.extractRuns(renderer.flexColumns, "MUSIC_PAGE_TYPE_ARTIST").map{
                    Artist(
                        name = it.text,
                        id = it.navigationEndpoint?.browseEndpoint?.browseId
                    )
                }.ifEmpty {
                    // Label-uploaded albums (e.g. "OLAK5uy_…" art tracks) name the performing
                    // artist as a plain-text run with no artist link, while the album header
                    // strapline is the record label / distributor channel. Prefer that
                    // plain-text artist over inheriting the label as the track artist.
                    renderer.flexColumns.getOrNull(1)
                        ?.musicResponsiveListItemFlexColumnRenderer?.text?.runs
                        ?.splitBySeparator()?.firstOrNull()?.oddElements()
                        ?.map { Artist(name = it.text, id = it.navigationEndpoint?.browseEndpoint?.browseId) }
                        ?.filter { it.name.isNotBlank() }
                        ?.takeIf { it.isNotEmpty() }
                    // Final fallback: inherit the album artist when the row has no artist at all.
                        ?: album?.artists ?: emptyList()
                },
                album = album?.let {
                    Album(it.title, it.browseId)
                } ?: renderer.flexColumns.getOrNull(2)?.musicResponsiveListItemFlexColumnRenderer?.text?.runs?.firstOrNull()?.let {
                    Album(
                        name = it.text,
                        id = it.navigationEndpoint?.browseEndpoint?.browseId!!
                    )
                }!!,
                duration = renderer.fixedColumns?.firstOrNull()
                    ?.musicResponsiveListItemFlexColumnRenderer?.text?.runs?.firstOrNull()
                    ?.text?.parseTime() ?: return null,
                musicVideoType = renderer.musicVideoType,
                thumbnail = renderer.thumbnail?.getThumbnailUrl() ?: album?.thumbnail!!,
                explicit = renderer.badges?.find {
                    it.musicInlineBadgeRenderer?.icon?.iconType == "MUSIC_EXPLICIT_BADGE"
                } != null,
                libraryAddToken = libraryTokens.addToken,
                libraryRemoveToken = libraryTokens.removeToken
            )
        }
    }
}
