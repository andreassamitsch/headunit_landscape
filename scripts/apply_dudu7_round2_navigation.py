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

player = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt")
player_text = player.read_text(encoding="utf-8")
old_live = '''            Text(
                text = "●  FM LIVE",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
            )
'''
new_live = '''            Text(
                text = if (state.ta && state.taEnabled) "●  TA VERKEHR" else "●  FM LIVE",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color =
                    if (state.ta && state.taEnabled) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
            )
'''
if old_live in player_text:
    player_text = player_text.replace(old_live, new_live, 1)
elif "TA VERKEHR" not in player_text:
    raise SystemExit("FM live indicator not found")

old_status = '''                    if (state.pi != 0) append(" • PI ${state.pi.toString(16).uppercase()}")
                    if (state.pty != 0) append(" • PTY ${state.pty}")
'''
new_status = '''                    if (state.pi != 0) append(" • PI ${state.pi.toString(16).uppercase()}")
                    val pty = FytPhysicalRadio.ptyLabel(state.pty)
                    if (pty.isNotBlank()) append(" • $pty")
                    if (state.afEnabled) append(" • AF")
                    if (state.tp) append(" • TP")
                    if (state.ta && state.taEnabled) append(" • TA")
'''
if old_status in player_text:
    player_text = player_text.replace(old_status, new_status, 1)
elif "if (state.afEnabled) append" not in player_text:
    raise SystemExit("FM player status block not found")

player.write_text(player_text, encoding="utf-8")
print("Dudu7 FM player now shows AF, PTY, TP and TA")
