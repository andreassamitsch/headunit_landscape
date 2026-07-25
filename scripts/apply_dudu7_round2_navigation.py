from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt")
text = path.read_text(encoding="utf-8")

old_import = "import com.metrolist.music.ui.screens.artist.ArtistItemsScreen\nimport com.metrolist.music.ui.screens.artist.ArtistScreen\n"
new_import = "import com.metrolist.music.ui.screens.artist.ArtistItemsScreen\nimport com.metrolist.music.ui.screens.artist.ArtistScreen\nimport com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n"
if old_import in text:
    text = text.replace(old_import, new_import, 1)
elif "import com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen\n" not in text:
    raise SystemExit("Artist imports not found")

old_route = """    ) {
        ArtistScreen(
            navController = navController,
            embeddedInPlayer = embeddedInPlayer,
        )
    }

    composable(
        route = \"artist/{artistId}/songs\",
"""
new_route = """    ) {
        if (embeddedInPlayer) {
            EmbeddedArtistScreen(navController)
        } else {
            ArtistScreen(navController = navController)
        }
    }

    composable(
        route = \"artist/{artistId}/songs\",
"""
if old_route in text:
    text = text.replace(old_route, new_route, 1)
elif "EmbeddedArtistScreen(navController)" not in text:
    raise SystemExit("Artist route not found")

path.write_text(text, encoding="utf-8")
print("Dudu7 artist route now uses EmbeddedArtistScreen")
