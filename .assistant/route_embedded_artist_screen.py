from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/NavigationBuilder.kt")
text = path.read_text(encoding="utf-8")
old = "        ArtistScreen(navController, embeddedInPlayer = embeddedInPlayer)\n"
new = '''        if (embeddedInPlayer) {
            com.metrolist.music.ui.screens.artist.EmbeddedArtistScreen(navController)
        } else {
            ArtistScreen(navController)
        }
'''
if old not in text:
    raise SystemExit("Expected embedded ArtistScreen route was not found")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Routed vehicle artist pages to touch-safe embedded screen")
