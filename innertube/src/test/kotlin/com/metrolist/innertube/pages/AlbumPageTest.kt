package com.metrolist.innertube.pages

import com.metrolist.innertube.models.BrowseEndpoint
import com.metrolist.innertube.models.MusicResponsiveHeaderRenderer
import com.metrolist.innertube.models.NavigationEndpoint
import com.metrolist.innertube.models.ResponseContext
import com.metrolist.innertube.models.Run
import com.metrolist.innertube.models.Runs
import com.metrolist.innertube.models.SectionListRenderer
import com.metrolist.innertube.models.Tabs
import com.metrolist.innertube.models.Thumbnail
import com.metrolist.innertube.models.ThumbnailRenderer
import com.metrolist.innertube.models.Thumbnails
import com.metrolist.innertube.models.response.BrowseResponse
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class AlbumPageTest {
    @Test
    fun parsesSingleColumnResponsiveAlbumResponse() {
        val albumBrowseId = "MPREb_single_column"
        val playlistId = "OLAK5uy_single_column"
        val thumbnailUrl = "https://example.invalid/album.jpg"
        val response =
            BrowseResponse(
                contents =
                    BrowseResponse.Contents(
                        singleColumnBrowseResultsRenderer =
                            Tabs(
                                tabs =
                                    listOf(
                                        Tabs.Tab(
                                            tabRenderer =
                                                Tabs.Tab.TabRenderer(
                                                    title = null,
                                                    content =
                                                        Tabs.Tab.TabRenderer.Content(
                                                            sectionListRenderer =
                                                                SectionListRenderer(
                                                                    header = null,
                                                                    contents =
                                                                        listOf(
                                                                            SectionListRenderer.Content(
                                                                                musicCarouselShelfRenderer = null,
                                                                                musicShelfRenderer = null,
                                                                                musicCardShelfRenderer = null,
                                                                                musicPlaylistShelfRenderer = null,
                                                                                musicDescriptionShelfRenderer = null,
                                                                                musicResponsiveHeaderRenderer =
                                                                                    MusicResponsiveHeaderRenderer(
                                                                                        thumbnail = thumbnail(thumbnailUrl),
                                                                                        buttons = emptyList(),
                                                                                        title = Runs(listOf(Run("Single Column Album", null))),
                                                                                        subtitle =
                                                                                            Runs(
                                                                                                listOf(
                                                                                                    Run("Album", null),
                                                                                                    Run(" • ", null),
                                                                                                    Run("2026", null),
                                                                                                ),
                                                                                            ),
                                                                                        secondSubtitle = null,
                                                                                        straplineTextOne =
                                                                                            Runs(
                                                                                                listOf(
                                                                                                    Run(
                                                                                                        "AVEC",
                                                                                                        NavigationEndpoint(
                                                                                                            browseEndpoint = BrowseEndpoint("UC_TEST_ARTIST"),
                                                                                                        ),
                                                                                                    ),
                                                                                                ),
                                                                                            ),
                                                                                        description = null,
                                                                                        facepile = null,
                                                                                    ),
                                                                                musicEditablePlaylistDetailHeaderRenderer = null,
                                                                                gridRenderer = null,
                                                                                itemSectionRenderer = null,
                                                                            ),
                                                                        ),
                                                                    continuations = null,
                                                                ),
                                                            musicQueueRenderer = null,
                                                        ),
                                                    endpoint = null,
                                                ),
                                        ),
                                    ),
                            ),
                        sectionListRenderer = null,
                        twoColumnBrowseResultsRenderer = null,
                    ),
                continuationContents = null,
                onResponseReceivedActions = null,
                header = null,
                microformat =
                    BrowseResponse.Microformat(
                        BrowseResponse.Microformat.MicroformatDataRenderer(
                            "https://music.youtube.com/playlist?list=$playlistId&feature=share",
                        ),
                    ),
                responseContext = ResponseContext(visitorData = null, serviceTrackingParams = null),
                background = null,
            )

        val album = AlbumPage.getAlbum(response, albumBrowseId)

        assertNotNull(album)
        requireNotNull(album)
        assertEquals(albumBrowseId, album.browseId)
        assertEquals(playlistId, album.playlistId)
        assertEquals("Single Column Album", album.title)
        assertEquals("AVEC", album.artists?.single()?.name)
        assertEquals(2026, album.year)
        assertEquals(thumbnailUrl, album.thumbnail)
    }

    private fun thumbnail(url: String) =
        ThumbnailRenderer(
            musicThumbnailRenderer =
                ThumbnailRenderer.MusicThumbnailRenderer(
                    thumbnail = Thumbnails(listOf(Thumbnail(url = url, width = 512, height = 512))),
                    thumbnailCrop = null,
                    thumbnailScale = null,
                ),
            musicAnimatedThumbnailRenderer = null,
            croppedSquareThumbnailRenderer = null,
        )
}
