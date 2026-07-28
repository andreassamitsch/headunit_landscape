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


# Version --------------------------------------------------------------------
build_path = "app/build.gradle.kts"
build = read(build_path)
build = replace_once(build, "versionCode = 1370026", "versionCode = 1370027", "versionCode")
build = replace_once(build, 'versionName = "13.7.17"', 'versionName = "13.7.18"', "versionName")
write(build_path, build)


# Artist album cards ---------------------------------------------------------
artist_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt"
artist = read(artist_path)

item_marker = '''                                    ) { item ->
                                        YouTubeGridItem(
'''
item_replacement = '''                                    ) { item ->
                                        val albumTapKey = "artist_album_${index}_${item.id}"
                                        DisposableEffect(albumTapKey) {
                                            onDispose {
                                                rightPaneTapTargets.remove(albumTapKey)
                                            }
                                        }
                                        YouTubeGridItem(
'''
artist = replace_once(artist, item_marker, item_replacement, "artist album item")

modifier_marker = '''                                            modifier =
                                                Modifier
                                                    .combinedClickable(
'''
modifier_replacement = '''                                            modifier =
                                                Modifier
                                                    .onGloballyPositioned { coordinates ->
                                                        if (embeddedInPlayer && item is AlbumItem) {
                                                            val albumId = item.id
                                                            rightPaneTapTargets[albumTapKey] =
                                                                coordinates.boundsInRoot() to {
                                                                    timber.log.Timber.tag("Dudu7ArtistAlbumTap").i(
                                                                        "Opening artist album item id=%s",
                                                                        albumId,
                                                                    )
                                                                    navController.navigate("album/$albumId")
                                                                }
                                                        } else {
                                                            rightPaneTapTargets.remove(albumTapKey)
                                                        }
                                                    }
                                                    .combinedClickable(
'''
if "Dudu7ArtistAlbumTap" not in artist:
    item_start = artist.index('val albumTapKey = "artist_album_${index}_${item.id}"')
    modifier_start = artist.find(modifier_marker, item_start)
    if modifier_start < 0:
        raise SystemExit("artist album modifier: marker not found")
    artist = (
        artist[:modifier_start]
        + modifier_replacement
        + artist[modifier_start + len(modifier_marker):]
    )

write(artist_path, artist)


# Verification --------------------------------------------------------------
checks = {
    build_path: ["versionCode = 1370027", 'versionName = "13.7.18"'],
    artist_path: [
        'val albumTapKey = "artist_album_${index}_${item.id}"',
        "Dudu7ArtistAlbumTap",
        'navController.navigate("album/$albumId")',
        "coordinates.boundsInRoot() to",
        "rightPaneTapTargets.remove(albumTapKey)",
    ],
}
for path, markers in checks.items():
    text = read(path)
    for marker in markers:
        if marker not in text:
            raise SystemExit(f"{path}: missing marker {marker}")

print("Applied Dudu7 artist album navigation for 13.7.18")
