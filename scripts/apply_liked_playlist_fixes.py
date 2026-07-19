#!/usr/bin/env python3
"""Backport current MetroList Innertube fixes for YouTube system playlists.

YouTube Music now returns Liked Music (LM) and some other system playlists with
singleColumnBrowseResultsRenderer/musicShelfRenderer and may omit
playlistItemData. Older MetroList builds crash or return an empty/error page.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative_path: str, old: str, new: str, marker: str) -> None:
    path = ROOT / relative_path
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[liked-playlist] already applied: {relative_path}")
        return
    if old not in text:
        raise RuntimeError(f"Patch anchor not found in {relative_path}: {old[:160]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[liked-playlist] patched: {relative_path}")


YOUTUBE = "innertube/src/main/kotlin/com/metrolist/innertube/YouTube.kt"
RENDERER = "innertube/src/main/kotlin/com/metrolist/innertube/models/MusicResponsiveListItemRenderer.kt"
PLAYLIST_PAGE = "innertube/src/main/kotlin/com/metrolist/innertube/pages/PlaylistPage.kt"

# YouTube may omit playlistItemData for rows in Liked Music. Resolve IDs from
# all endpoint locations used by current MetroList instead of dereferencing it.
replace_once(
    RENDERER,
    """    val musicVideoType: String?
        get() =
            overlay
                ?.musicItemThumbnailOverlayRenderer
                ?.content
                ?.musicPlayButtonRenderer
                ?.playNavigationEndpoint
                ?.musicVideoType
                ?: navigationEndpoint?.musicVideoType

    @Serializable
""",
    """    val musicVideoType: String?
        get() =
            overlay
                ?.musicItemThumbnailOverlayRenderer
                ?.content
                ?.musicPlayButtonRenderer
                ?.playNavigationEndpoint
                ?.musicVideoType
                ?: navigationEndpoint?.musicVideoType

    // YouTube no longer guarantees playlistItemData for system playlists.
    val videoId: String?
        get() =
            playlistItemData?.videoId
                ?: navigationEndpoint?.watchEndpoint?.videoId
                ?: overlay?.musicItemThumbnailOverlayRenderer
                    ?.content?.musicPlayButtonRenderer
                    ?.playNavigationEndpoint?.watchEndpoint?.videoId
                ?: flexColumns.firstOrNull()
                    ?.musicResponsiveListItemFlexColumnRenderer
                    ?.text?.runs?.firstOrNull()
                    ?.navigationEndpoint?.watchEndpoint?.videoId

    val playlistSetVideoId: String?
        get() =
            playlistItemData?.playlistSetVideoId
                ?: navigationEndpoint?.watchEndpoint?.playlistSetVideoId
                ?: overlay?.musicItemThumbnailOverlayRenderer
                    ?.content?.musicPlayButtonRenderer
                    ?.playNavigationEndpoint?.watchEndpoint?.playlistSetVideoId

    @Serializable
""",
    marker="val playlistSetVideoId: String?",
)

replace_once(
    PLAYLIST_PAGE,
    "id = renderer.playlistItemData?.videoId ?: return null,",
    "id = renderer.videoId ?: return null,",
    marker="id = renderer.videoId ?: return null,",
)
replace_once(
    PLAYLIST_PAGE,
    "setVideoId = renderer.playlistItemData.playlistSetVideoId ?: return null,",
    "setVideoId = renderer.playlistSetVideoId ?: return null,",
    marker="setVideoId = renderer.playlistSetVideoId ?: return null,",
)

OLD_PLAYLIST_FUNCTION = r'''    suspend fun playlist(playlistId: String): Result<PlaylistPage> =
        runCatching {
            val response =
                innerTube
                    .browse(
                        client = WEB_REMIX,
                        browseId = "VL$playlistId",
                        setLogin = true,
                    ).body<BrowseResponse>()
            val base =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.tabs
                    ?.firstOrNull()
                    ?.tabRenderer
                    ?.content
                    ?.sectionListRenderer
                    ?.contents
                    ?.firstOrNull()
            val header =
                base?.musicResponsiveHeaderRenderer
                    ?: base?.musicEditablePlaylistDetailHeaderRenderer?.header?.musicResponsiveHeaderRenderer

            val editable = base?.musicEditablePlaylistDetailHeaderRenderer != null

            PlaylistPage(
                playlist =
                    PlaylistItem(
                        id = playlistId,
                        title =
                            header
                                ?.title
                                ?.runs
                                ?.firstOrNull()
                                ?.text!!,
                        author =
                            header.straplineTextOne?.runs?.firstOrNull()?.let {
                                Artist(
                                    name = it.text,
                                    id = it.navigationEndpoint?.browseEndpoint?.browseId,
                                )
                            },
                        songCountText =
                            header.secondSubtitle
                                ?.runs
                                ?.firstOrNull()
                                ?.text,
                        thumbnail =
                            header.thumbnail
                                ?.musicThumbnailRenderer
                                ?.thumbnail
                                ?.thumbnails
                                ?.lastOrNull()
                                ?.url!!,
                        playEndpoint = null,
                        shuffleEndpoint =
                            header.buttons
                                .lastOrNull()
                                ?.menuRenderer
                                ?.items
                                ?.firstOrNull()
                                ?.menuNavigationItemRenderer
                                ?.navigationEndpoint
                                ?.watchPlaylistEndpoint!!,
                        radioEndpoint =
                            header.buttons
                                .getOrNull(2)
                                ?.menuRenderer
                                ?.items
                                ?.find {
                                    it.menuNavigationItemRenderer?.icon?.iconType == "MIX"
                                }?.menuNavigationItemRenderer
                                ?.navigationEndpoint
                                ?.watchPlaylistEndpoint,
                        isEditable = editable,
                    ),
                songs =
                    response.contents
                        ?.twoColumnBrowseResultsRenderer
                        ?.secondaryContents
                        ?.sectionListRenderer
                        ?.contents
                        ?.firstOrNull()
                        ?.musicPlaylistShelfRenderer
                        ?.contents
                        ?.getItems()
                        ?.mapNotNull {
                            PlaylistPage.fromMusicResponsiveListItemRenderer(it)
                        } ?: emptyList(),
                songsContinuation =
                    response.contents
                        ?.twoColumnBrowseResultsRenderer
                        ?.secondaryContents
                        ?.sectionListRenderer
                        ?.contents
                        ?.firstOrNull()
                        ?.musicPlaylistShelfRenderer
                        ?.contents
                        ?.getContinuation()
                        ?: response.contents
                            ?.twoColumnBrowseResultsRenderer
                            ?.secondaryContents
                            ?.sectionListRenderer
                            ?.contents
                            ?.firstOrNull()
                            ?.musicPlaylistShelfRenderer
                            ?.continuations
                            ?.getContinuation(),
                continuation =
                    response.contents
                        ?.twoColumnBrowseResultsRenderer
                        ?.secondaryContents
                        ?.sectionListRenderer
                        ?.continuations
                        ?.getContinuation(),
            )
        }
'''

NEW_PLAYLIST_FUNCTION = r'''    suspend fun playlist(playlistId: String): Result<PlaylistPage> =
        runCatching {
            val response =
                innerTube
                    .browse(
                        client = WEB_REMIX,
                        browseId = "VL$playlistId",
                        setLogin = true,
                    ).body<BrowseResponse>()

            val twoColumnBase =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.tabs
                    ?.firstOrNull()
                    ?.tabRenderer
                    ?.content
                    ?.sectionListRenderer
                    ?.contents
                    ?.firstOrNull()
            val singleColumnSection =
                response.contents
                    ?.singleColumnBrowseResultsRenderer
                    ?.tabs
                    ?.firstOrNull()
                    ?.tabRenderer
                    ?.content
                    ?.sectionListRenderer
            val singleColumnBase = singleColumnSection?.contents?.firstOrNull()
            val base = twoColumnBase ?: singleColumnBase
            val header =
                base?.musicResponsiveHeaderRenderer
                    ?: base?.musicEditablePlaylistDetailHeaderRenderer?.header?.musicResponsiveHeaderRenderer
            val musicHeader = response.header?.musicHeaderRenderer
            val editable = base?.musicEditablePlaylistDetailHeaderRenderer != null

            val author =
                header?.straplineTextOne?.runs?.firstOrNull()?.let {
                    Artist(name = it.text, id = it.navigationEndpoint?.browseEndpoint?.browseId)
                } ?: musicHeader?.straplineTextOne?.runs?.firstOrNull()?.let {
                    Artist(name = it.text, id = it.navigationEndpoint?.browseEndpoint?.browseId)
                }

            val twoColumnShelf =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.secondaryContents
                    ?.sectionListRenderer
                    ?.contents
                    ?.firstOrNull()
            val singleColumnShelf = singleColumnSection?.contents?.firstOrNull()
            val twoColumnContents =
                twoColumnShelf?.musicPlaylistShelfRenderer?.contents
                    ?: twoColumnShelf?.musicShelfRenderer?.contents
            val singleColumnContents =
                singleColumnShelf?.musicPlaylistShelfRenderer?.contents
                    ?: singleColumnShelf?.musicShelfRenderer?.contents
            val twoColumnContinuations =
                twoColumnShelf?.musicPlaylistShelfRenderer?.continuations
                    ?: twoColumnShelf?.musicShelfRenderer?.continuations
            val singleColumnContinuations =
                singleColumnShelf?.musicPlaylistShelfRenderer?.continuations
                    ?: singleColumnShelf?.musicShelfRenderer?.continuations
            val mergedContents = twoColumnContents ?: singleColumnContents
            val mergedContinuations = twoColumnContinuations ?: singleColumnContinuations

            PlaylistPage(
                playlist =
                    PlaylistItem(
                        id = playlistId,
                        title =
                            header?.title?.runs?.firstOrNull()?.text
                                ?: musicHeader?.title?.runs?.firstOrNull()?.text
                                ?: "",
                        author = author,
                        songCountText =
                            (header?.secondSubtitle ?: musicHeader?.secondSubtitle)
                                ?.runs
                                ?.firstOrNull()
                                ?.text,
                        thumbnail =
                            header?.thumbnail
                                ?.musicThumbnailRenderer
                                ?.thumbnail
                                ?.thumbnails
                                ?.lastOrNull()
                                ?.url
                                ?: musicHeader?.thumbnail
                                    ?.musicThumbnailRenderer
                                    ?.thumbnails
                                    ?.lastOrNull()
                                    ?.url
                                ?: "",
                        playEndpoint = null,
                        shuffleEndpoint =
                            header?.buttons?.lastOrNull()
                                ?.menuRenderer?.items?.firstOrNull()
                                ?.menuNavigationItemRenderer?.navigationEndpoint?.watchPlaylistEndpoint
                                ?: musicHeader?.buttons?.lastOrNull()
                                    ?.menuRenderer?.items?.firstOrNull()
                                    ?.menuNavigationItemRenderer?.navigationEndpoint?.watchPlaylistEndpoint,
                        radioEndpoint =
                            header?.buttons?.getOrNull(2)
                                ?.menuRenderer?.items?.find {
                                    it.menuNavigationItemRenderer?.icon?.iconType == "MIX"
                                }?.menuNavigationItemRenderer?.navigationEndpoint?.watchPlaylistEndpoint
                                ?: musicHeader?.buttons?.getOrNull(2)
                                    ?.menuRenderer?.items?.find {
                                        it.menuNavigationItemRenderer?.icon?.iconType == "MIX"
                                    }?.menuNavigationItemRenderer?.navigationEndpoint?.watchPlaylistEndpoint,
                        isEditable = editable,
                    ),
                songs =
                    mergedContents
                        ?.getItems()
                        ?.mapNotNull { PlaylistPage.fromMusicResponsiveListItemRenderer(it) }
                        ?: emptyList(),
                songsContinuation =
                    mergedContents?.getContinuation()
                        ?: mergedContinuations?.getContinuation(),
                continuation =
                    response.contents
                        ?.twoColumnBrowseResultsRenderer
                        ?.secondaryContents
                        ?.sectionListRenderer
                        ?.continuations
                        ?.getContinuation()
                        ?: singleColumnSection?.continuations?.getContinuation(),
            )
        }
'''

replace_once(
    YOUTUBE,
    OLD_PLAYLIST_FUNCTION,
    NEW_PLAYLIST_FUNCTION,
    marker="val twoColumnContents =",
)

print("[liked-playlist] all parser fixes applied successfully")
