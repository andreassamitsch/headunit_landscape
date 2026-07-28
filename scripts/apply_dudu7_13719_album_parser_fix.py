#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


# Version --------------------------------------------------------------------
build_path = "app/build.gradle.kts"
build = read(build_path)
build = replace_once(build, "versionCode = 1370027", "versionCode = 1370028", "versionCode")
build = replace_once(build, 'versionName = "13.7.18"', 'versionName = "13.7.19"', "versionName")
write(build_path, build)


# Generic album response parser ---------------------------------------------
album_page_path = "innertube/src/main/kotlin/com/metrolist/innertube/pages/AlbumPage.kt"
album_page = read(album_page_path)
album_page = replace_once(
    album_page,
    '''    companion object {
        fun getPlaylistId(response: BrowseResponse): String? {
            var playlistId = response.microformat?.microformatDataRenderer?.urlCanonical?.substringAfterLast('=')
            if (playlistId == null)
            {
                playlistId = response.header?.musicDetailHeaderRenderer?.menu?.menuRenderer?.topLevelButtons?.firstOrNull()
                    ?.buttonRenderer?.navigationEndpoint?.watchPlaylistEndpoint?.playlistId
            }
            return playlistId
        }
''',
    '''    companion object {
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
''',
    "album parser and playlist id",
)
album_page = replace_once(
    album_page,
    '''        fun getThumbnail(response: BrowseResponse): String? {
            return response.background?.getThumbnailUrl() ?: response.header?.musicDetailHeaderRenderer?.thumbnail
                ?.getThumbnailUrl()
        }
''',
    '''        fun getThumbnail(response: BrowseResponse): String? =
            response.background?.getThumbnailUrl()
                ?: getHeader(response)?.thumbnail?.getThumbnailUrl()
                ?: response.header?.musicDetailHeaderRenderer?.thumbnail?.getThumbnailUrl()
''',
    "album thumbnail variants",
)
album_page = replace_once(
    album_page,
    '''        fun getArtists(response: BrowseResponse): List<Artist> {
            val artists = getHeader(response)?.straplineTextOne?.runs?.oddElements()?.map {
                Artist(
                    name = it.text,
                    id = it.navigationEndpoint?.browseEndpoint?.browseId
                )
            } ?: response.header?.musicDetailHeaderRenderer?.subtitle?.runs?.splitBySeparator()?.getOrNull(1)?.oddElements()?.map {
                Artist(
                    name = it.text,
                    id = it.navigationEndpoint?.browseEndpoint?.browseId
                )
            } ?: emptyList()

            return artists
        }
''',
    '''        fun getArtists(response: BrowseResponse): List<Artist> {
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
''',
    "album artist variants",
)
write(album_page_path, album_page)


# Make YouTube.album use the generic parser instead of fixed two-column !! ----
youtube_path = "innertube/src/main/kotlin/com/metrolist/innertube/YouTube.kt"
youtube = read(youtube_path)
start = youtube.index("    suspend fun album(\n")
end = youtube.index("    suspend fun albumSongs(\n", start)
new_album_function = '''    suspend fun album(
        browseId: String,
        withSongs: Boolean = true,
    ): Result<AlbumPage> =
        runCatching {
            val response = innerTube.browse(WEB_REMIX, browseId).body<BrowseResponse>()
            val parsedAlbum =
                AlbumPage.getAlbum(response, browseId)
                    ?: error("Album response did not contain usable metadata for $browseId")
            val inlineSongs =
                if (withSongs) {
                    AlbumPage.getSongs(response, parsedAlbum)
                } else {
                    emptyList()
                }
            val albumSongsList =
                when {
                    !withSongs -> emptyList()
                    inlineSongs.isNotEmpty() -> inlineSongs
                    else -> albumSongs(parsedAlbum.playlistId, parsedAlbum).getOrThrow()
                }

            // When YouTube credits the album to a label/distributor channel but every
            // track names the same performing artist, surface the performer instead.
            val performer =
                albumSongsList.firstOrNull()?.artists?.firstOrNull()?.takeIf { first ->
                    first.name.isNotBlank() &&
                        albumSongsList.all { it.artists.firstOrNull()?.name == first.name }
                }
            val resolvedAlbum =
                if (performer != null && parsedAlbum.artists?.any { it.name == performer.name } != true) {
                    parsedAlbum.copy(artists = listOf(performer))
                } else {
                    parsedAlbum
                }
            val otherVersions =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.secondaryContents
                    ?.sectionListRenderer
                    ?.contents
                    ?.getOrNull(1)
                    ?.musicCarouselShelfRenderer
                    ?.contents
                    ?.mapNotNull { it.musicTwoRowItemRenderer }
                    ?.mapNotNull(NewReleaseAlbumPage::fromMusicTwoRowItemRenderer)
                    .orEmpty()

            AlbumPage(
                album = resolvedAlbum,
                songs = albumSongsList,
                otherVersions = otherVersions,
            )
        }

'''
youtube = youtube[:start] + new_album_function + youtube[end:]
write(youtube_path, youtube)


# Expose failures and retry instead of an endless spinner --------------------
view_model_path = "app/src/main/kotlin/com/metrolist/music/viewmodels/AlbumViewModel.kt"
write(
    view_model_path,
    '''/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.viewmodels

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.AlbumItem
import com.metrolist.music.db.MusicDatabase
import com.metrolist.music.utils.reportException
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AlbumViewModel
@Inject
constructor(
    private val database: MusicDatabase,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    val albumId = savedStateHandle.get<String>("albumId")!!
    val playlistId = MutableStateFlow("")
    val albumWithSongs =
        database
            .albumWithSongs(albumId)
            .stateIn(viewModelScope, SharingStarted.Eagerly, null)
    var otherVersions = MutableStateFlow<List<AlbumItem>>(emptyList())

    private val _loadError = MutableStateFlow<String?>(null)
    val loadError = _loadError.asStateFlow()
    private var loadJob: Job? = null

    init {
        retry()
    }

    fun retry() {
        loadJob?.cancel()
        loadJob =
            viewModelScope.launch {
                _loadError.value = null
                val album = database.album(albumId).first()
                YouTube
                    .album(albumId)
                    .onSuccess {
                        playlistId.value = it.album.playlistId
                        otherVersions.value = it.otherVersions
                        database.transaction {
                            if (album == null) {
                                insert(it)
                            } else {
                                update(album.album, it, album.artists)
                            }
                        }
                    }.onFailure {
                        reportException(it)
                        _loadError.value = it.message ?: "Unbekannter Album-Ladefehler"
                        if (it.message?.contains("NOT_FOUND") == true) {
                            database.query {
                                album?.album?.let(::delete)
                            }
                        }
                    }
            }
    }
}
''',
)

album_screen_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/AlbumScreen.kt"
album_screen = read(album_screen_path)
album_screen = replace_once(
    album_screen,
    "import androidx.compose.material3.Checkbox\n",
    "import androidx.compose.material3.Button\nimport androidx.compose.material3.Checkbox\n",
    "album retry button import",
)
album_screen = replace_once(
    album_screen,
    "    val albumWithSongs by viewModel.albumWithSongs.collectAsStateWithLifecycle()\n",
    "    val albumWithSongs by viewModel.albumWithSongs.collectAsStateWithLifecycle()\n    val loadError by viewModel.loadError.collectAsStateWithLifecycle()\n",
    "album error state",
)
loading_start = album_screen.index('        } else {\n            item(key = "loading") {')
loading_end = album_screen.index("        }\n    }\n\n    TopAppBar(", loading_start) + len("        }\n")
loading_replacement = '''        } else {
            item(key = if (loadError == null) "loading" else "load_error") {
                if (loadError == null) {
                    Box(
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        ContainedLoadingIndicator()
                    }
                } else {
                    Column(
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                        modifier =
                            Modifier
                                .fillMaxWidth()
                                .padding(32.dp),
                    ) {
                        Text(
                            text = "Album konnte nicht geladen werden.",
                            style = MaterialTheme.typography.titleMedium,
                            textAlign = TextAlign.Center,
                        )
                        Text(
                            text = loadError.orEmpty(),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                            maxLines = 4,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Button(onClick = viewModel::retry) {
                            Text("ERNEUT VERSUCHEN")
                        }
                    }
                }
            }
        }
'''
album_screen = album_screen[:loading_start] + loading_replacement + album_screen[loading_end:]
write(album_screen_path, album_screen)


# Regression test: valid single-column album response ------------------------
test_path = "innertube/src/test/kotlin/com/metrolist/innertube/pages/AlbumPageTest.kt"
write(
    test_path,
    '''package com.metrolist.innertube.pages

import com.metrolist.innertube.models.BrowseEndpoint
import com.metrolist.innertube.models.MusicResponsiveHeaderRenderer
import com.metrolist.innertube.models.NavigationEndpoint
import com.metrolist.innertube.models.ResponseContext
import com.metrolist.innertube.models.Run
import com.metrolist.innertube.models.Runs
import com.metrolist.innertube.models.SectionListRenderer
import com.metrolist.innertube.models.Tab
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
'''.replace("import com.metrolist.innertube.models.Tab\n", ""),
)


# Verification --------------------------------------------------------------
checks = {
    build_path: ["versionCode = 1370028", 'versionName = "13.7.19"'],
    album_page_path: [
        "fun getAlbum(response: BrowseResponse, browseId: String)",
        "getHeader(response)?.thumbnail?.getThumbnailUrl()",
        "substringAfter(\"list=\"",
    ],
    youtube_path: [
        "AlbumPage.getAlbum(response, browseId)",
        "AlbumPage.getSongs(response, parsedAlbum)",
    ],
    view_model_path: ["val loadError = _loadError.asStateFlow()", "fun retry()"],
    album_screen_path: ["Album konnte nicht geladen werden.", "Button(onClick = viewModel::retry)"],
    test_path: ["parsesSingleColumnResponsiveAlbumResponse", "OLAK5uy_single_column"],
}
for path, markers in checks.items():
    text = read(path)
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"{path}: missing marker {marker}")

album_function = read(youtube_path)[read(youtube_path).index("    suspend fun album(\n"):read(youtube_path).index("    suspend fun albumSongs(\n")]
if "twoColumnBrowseResultsRenderer\n                                ?.tabs\n                                ?.firstOrNull()" in album_function:
    raise SystemExit("YouTube.album still contains the old fixed two-column parser")

print("Applied generic album parser and regression test for Dudu7 13.7.19")
