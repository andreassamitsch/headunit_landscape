from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/component/Items.kt")
text = path.read_text()

# Undo the accidental API change on the local SongGridItem: the touch callback
# belongs to YouTubeGridItem, which BrowseScreen actually renders.
song_start = text.index("fun SongGridItem(")
song_end = text.index("\n@Composable\nfun ArtistListItem", song_start)
song = text[song_start:song_end]
song = song.replace(
    "    isPlaying: Boolean = false,\n    onPlayClick: (() -> Unit)? = null,\n    fillMaxWidth: Boolean = false,",
    "    isPlaying: Boolean = false,\n    fillMaxWidth: Boolean = false,",
    1,
)
song = song.replace(
    "            OverlayPlayButton(\n                visible = true,\n                onClick = onPlayClick,\n            )",
    "            OverlayPlayButton(\n                visible = true\n            )",
    1,
)
text = text[:song_start] + song + text[song_end:]

# Add the callback to the actual online grid component used by BrowseScreen.
yt_start = text.index("fun YouTubeGridItem(")
yt_end = text.index("\n@Composable\nfun LocalSongsGrid", yt_start)
yt = text[yt_start:yt_end]
if "onPlayClick: (() -> Unit)? = null" not in yt:
    yt = yt.replace(
        "    isPlaying: Boolean = false,\n    fillMaxWidth: Boolean = false,",
        "    isPlaying: Boolean = false,\n    onPlayClick: (() -> Unit)? = null,\n    fillMaxWidth: Boolean = false,",
        1,
    )
if "onClick = onPlayClick" not in yt:
    yt = yt.replace(
        "            OverlayPlayButton(\n                visible = true\n            )",
        "            OverlayPlayButton(\n                visible = true,\n                onClick = onPlayClick,\n            )",
        1,
    )
if "onPlayClick: (() -> Unit)? = null" not in yt or "onClick = onPlayClick" not in yt:
    raise SystemExit("YouTubeGridItem touch patch was not applied")
text = text[:yt_start] + yt + text[yt_end:]
path.write_text(text)
