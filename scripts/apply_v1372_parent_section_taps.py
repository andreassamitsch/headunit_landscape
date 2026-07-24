#!/usr/bin/env python3
from pathlib import Path


artist_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
artist = artist_path.read_text(encoding="utf-8")

artist = artist.replace(
    "    val rightPaneTapTargets = remember { mutableStateMapOf<String, Pair<Rect, () -> Unit>>() }",
    "    val rightPaneTapTargets = remember { mutableMapOf<String, Pair<Rect, () -> Unit>>() }",
    1,
)

start_marker = "                        val embeddedSectionTapModifier =\n"
end_marker = "                        if (isSongSection) {\n"
start = artist.find(start_marker)
if start >= 0:
    end = artist.find(end_marker, start)
    if end < 0:
        raise SystemExit("ArtistScreen song-section end marker missing")
    replacement = '''                        val sectionTapKey = "${index}_${section.title}"
                        if (section.items.isNotEmpty()) {
                            item(key = "section_${section.title}") {
                                DisposableEffect(sectionTapKey) {
                                    onDispose {
                                        rightPaneTapTargets.remove(sectionTapKey)
                                    }
                                }
                                NavigationTitle(
                                    title = section.title,
                                    modifier =
                                        Modifier
                                            .onGloballyPositioned { coordinates ->
                                                val sectionClick = openSection
                                                if (embeddedInPlayer && sectionClick != null) {
                                                    rightPaneTapTargets[sectionTapKey] =
                                                        coordinates.boundsInRoot() to sectionClick
                                                } else {
                                                    rightPaneTapTargets.remove(sectionTapKey)
                                                }
                                            }.animateItem(),
                                    onClick = openSection,
                                )
                            }
                        }

'''
    artist = artist[:start] + replacement + artist[end:]

required = [
    "rightPaneTapTargets[sectionTapKey]",
    "coordinates.boundsInRoot() to sectionClick",
    "Dudu7ArtistSectionTap",
]
missing = [marker for marker in required if marker not in artist]
if missing:
    raise SystemExit(f"Parent artist tap target markers missing: {missing}")
if "val embeddedSectionTapModifier" in artist:
    raise SystemExit("Obsolete child section tap handler is still present")

artist_path.write_text(artist, encoding="utf-8")
print("Registered artist section tap bounds with the right-pane parent bridge")
