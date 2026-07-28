#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


album_page_path = "innertube/src/main/kotlin/com/metrolist/innertube/pages/AlbumPage.kt"
album_page = read(album_page_path)
album_page = replace_once(
    album_page,
    "import com.metrolist.innertube.models.MusicResponsiveListItemRenderer\n",
    "import com.metrolist.innertube.models.MusicResponsiveListItemRenderer\nimport com.metrolist.innertube.models.MusicShelfRenderer\n",
    "music shelf import",
)
album_page = replace_once(
    album_page,
    '''        fun getSongs(response: BrowseResponse, album: AlbumItem): List<SongItem> {
            val tabs = response.contents?.singleColumnBrowseResultsRenderer?.tabs ?: response.contents?.twoColumnBrowseResultsRenderer?.tabs
            val shelfRenderer = tabs?.firstOrNull()?.tabRenderer?.content?.sectionListRenderer?.contents?.firstOrNull()?.musicShelfRenderer ?:
                response.contents?.twoColumnBrowseResultsRenderer?.secondaryContents?.sectionListRenderer?.contents?.firstOrNull()?.musicShelfRenderer

            val songs = shelfRenderer?.contents?.getItems()?.mapNotNull {
                getSong(it, album)
            }
            return songs ?: emptyList()
        }
''',
    '''        fun getShelfContents(response: BrowseResponse): List<MusicShelfRenderer.Content> {
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
''',
    "generic album song shelf",
)
write(album_page_path, album_page)


youtube_path = "innertube/src/main/kotlin/com/metrolist/innertube/YouTube.kt"
youtube = read(youtube_path)
youtube = replace_once(
    youtube,
    '''            val shelf =
                response.contents
                    ?.twoColumnBrowseResultsRenderer
                    ?.secondaryContents
                    ?.sectionListRenderer
                    ?.contents
                    ?.firstOrNull()
            val shelfContents =
                shelf?.musicPlaylistShelfRenderer?.contents
                    ?: shelf?.musicShelfRenderer?.contents
                    ?: emptyList()
''',
    '''            val shelfContents = AlbumPage.getShelfContents(response)
''',
    "playlist album shelf fallback",
)
write(youtube_path, youtube)


test_path = "innertube/src/test/kotlin/com/metrolist/innertube/pages/AlbumPageTest.kt"
test = read(test_path)
test = replace_once(
    test,
    "import com.metrolist.innertube.models.MusicResponsiveHeaderRenderer\n",
    "import com.metrolist.innertube.models.MusicResponsiveHeaderRenderer\nimport com.metrolist.innertube.models.MusicShelfRenderer\n",
    "test music shelf import",
)
header_section = '''                                                                            SectionListRenderer.Content(
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
'''
shelf_section = header_section + '''                                                                            SectionListRenderer.Content(
                                                                                musicCarouselShelfRenderer = null,
                                                                                musicShelfRenderer =
                                                                                    MusicShelfRenderer(
                                                                                        title = null,
                                                                                        contents =
                                                                                            listOf(
                                                                                                MusicShelfRenderer.Content(
                                                                                                    musicResponsiveListItemRenderer = null,
                                                                                                    musicMultiRowListItemRenderer = null,
                                                                                                    continuationItemRenderer = null,
                                                                                                ),
                                                                                            ),
                                                                                        continuations = null,
                                                                                        bottomEndpoint = null,
                                                                                        moreContentButton = null,
                                                                                    ),
                                                                                musicCardShelfRenderer = null,
                                                                                musicPlaylistShelfRenderer = null,
                                                                                musicDescriptionShelfRenderer = null,
                                                                                musicResponsiveHeaderRenderer = null,
                                                                                musicEditablePlaylistDetailHeaderRenderer = null,
                                                                                gridRenderer = null,
                                                                                itemSectionRenderer = null,
                                                                            ),
'''
test = replace_once(test, header_section, shelf_section, "single-column shelf fixture")
test = replace_once(
    test,
    '''        assertEquals(thumbnailUrl, album.thumbnail)
''',
    '''        assertEquals(thumbnailUrl, album.thumbnail)
        assertEquals(1, AlbumPage.getShelfContents(response).size)
''',
    "single-column shelf assertion",
)
write(test_path, test)


checks = {
    album_page_path: ["fun getShelfContents(response: BrowseResponse)", "musicPlaylistShelfRenderer?.contents"],
    youtube_path: ["val shelfContents = AlbumPage.getShelfContents(response)"],
    test_path: ["assertEquals(1, AlbumPage.getShelfContents(response).size)"],
}
for path, markers in checks.items():
    text = read(path)
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"{path}: missing marker {marker}")

print("Applied single-column album song shelf fallback test")
