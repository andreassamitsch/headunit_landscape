#!/usr/bin/env python3
from pathlib import Path


def require(path: str, *needles: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")


def forbid(path: str, *needles: str) -> None:
    text = Path(path).read_text(encoding="utf-8")
    present = [needle for needle in needles if needle in text]
    if present:
        raise SystemExit(f"{path}: forbidden {present}")


require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt",
    'artist/{artistId}/items?browseId={browseId}&params={params}',
)
forbid(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt",
    'artist/{artistId}/items?browseId={browseId}?params={params}',
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt",
    'items?browseId=${android.net.Uri.encode(it.browseId)}&params=${android.net.Uri.encode(it.params.orEmpty())}',
)
require(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "private fun RadioDragHandle",
    "R.drawable.drag_handle",
    "Modifier.draggableHandle",
    'Text("Logos suchen")',
    'Text("Logo auswählen"',
    "manualFavicon = true",
    'Text("Automatisch")',
)
forbid(
    "app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt",
    "longPressDraggableHandle",
)
require(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStation.kt",
    "val manualFavicon: Boolean = false",
    'putBoolean("radio_manual_favicon", manualFavicon)',
)
require(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationStore.kt",
    'put("manualFavicon", station.manualFavicon)',
    'manualFavicon = optBoolean("manualFavicon", false)',
)
require(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoResolver.kt",
    "if (station.manualFavicon) return@withContext",
)
require(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt",
    'route.startsWith("search/")',
    "paneNavController.currentDestination?.route == SearchRoutes.ROUTE",
    "paneNavController.popBackStack(tab.route, inclusive = false)",
    "tab != VehicleRightPaneTab.QUEUE",
)
require(
    "app/build.gradle.kts",
    "versionCode = 158",
    'versionName = "13.6.9"',
)
print("PASS: all Metrolist Dudu7 13.6.9 acceptance markers found")
