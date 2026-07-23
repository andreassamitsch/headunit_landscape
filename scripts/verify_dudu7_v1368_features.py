#!/usr/bin/env python3
"""Static acceptance checks for the Dudu7/WebRadio 13.6.8 feature set."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(path: str, *needles: str) -> None:
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")


def forbid(path: str, *needles: str) -> None:
    text = read(path)
    present = [needle for needle in needles if needle in text]
    if present:
        raise SystemExit(f"{path}: forbidden legacy UI remains: {present}")


require("app/build.gradle.kts", 'versionCode = 157', 'versionName = "13.6.8"')
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "rememberReorderableLazyListState",
    "rememberReorderableLazyGridState",
    "longPressDraggableHandle",
    "store.reorder",
    "RadioFilterKind.COUNTRY",
    "RadioFilterKind.GENRE",
    "RadioFilterKind.LANGUAGE",
    "WebRadioViewTypeKey",
    "Aktion für diesen Radiosender auswählen",
)
forbid(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "R.drawable.arrow_upward",
    "R.drawable.arrow_downward",
    "R.drawable.edit",
    "R.drawable.delete",
)
require(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt",
    'mapOf("country" to normalizeCountry(cleanedQuery))',
    'mapOf("tag" to cleanedQuery)',
    'mapOf("language" to cleanedQuery)',
    '"österreich", "oesterreich" -> "Austria"',
)
require(
    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt",
    "radioResolvedSong",
    "resolvedRadioLibrarySong",
    "radioHasTrackMetadata",
    "applyRecognizedRadioTrack",
    "requestRightPaneNavigation",
    "isStrongRadioCoverMatch",
    "lastAppliedRadioMetadataKey",
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/player/Player.kt",
    "MusicRecognitionService.recognize",
    "resolvedRadioSong",
    "matchedSong.toMediaMetadata()",
    "syncUtils.likeSong(updated)",
    "SearchRoutes.resultRoute",
    "requestRightPaneNavigation",
    "showRadioRecognition",
)
require(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehiclePlayerControls.kt",
    "showRecognition",
    "recognitionInProgress",
    "likeEnabled",
    "Musik erkennen",
)
require(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
    "openRouteInRightPane",
    "onRightPaneNavigation",
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/EmbeddedArtistScreen.kt",
    "section.moreEndpoint",
    '"artist/${viewModel.artistId}/items?browseId=',
    "artistItemsContinuation",
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistItemsScreen.kt",
    "playCategoryFrom",
    "viewModel.loadAllItems()",
    "ListQueue(",
    "startIndex = startIndex",
    "notifyUserSongSelection",
)
print("Dudu7/WebRadio 13.6.8 static feature checks passed")
