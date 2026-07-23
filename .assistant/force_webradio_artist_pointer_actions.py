from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected {label}: {old[:180]!r}")
    return text.replace(old, new, 1)


path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    "import androidx.compose.ui.hapticfeedback.HapticFeedbackType\n",
    "import androidx.compose.ui.hapticfeedback.HapticFeedbackType\n"
    "import androidx.compose.ui.input.pointer.PointerEventPass\n"
    "import androidx.compose.ui.input.pointer.pointerInput\n",
    "pointer imports",
)

radio_click = '''                                                                .combinedClickable(
                                                                    onClick = playArtistRadio,
                                                                    onLongClick = {},
                                                                ).padding(horizontal = 16.dp),'''
radio_pointer = '''                                                                .pointerInput(radioEndpoint) {
                                                                    awaitPointerEventScope {
                                                                        while (true) {
                                                                            val event = awaitPointerEvent(PointerEventPass.Initial)
                                                                            if (event.changes.any { it.previousPressed && !it.pressed }) {
                                                                                event.changes.forEach { it.consume() }
                                                                                playArtistRadio()
                                                                            }
                                                                        }
                                                                    }
                                                                }.combinedClickable(
                                                                    onClick = playArtistRadio,
                                                                    onLongClick = {},
                                                                ).padding(horizontal = 16.dp),'''
text = replace_once(text, radio_click, radio_pointer, "embedded artist Radio click modifier")

shuffle_click = '''                                                                .combinedClickable(
                                                                    onClick = playArtistShuffle,
                                                                    onLongClick = {},
                                                                ),'''
shuffle_pointer = '''                                                                .pointerInput(shuffleEndpoint) {
                                                                    awaitPointerEventScope {
                                                                        while (true) {
                                                                            val event = awaitPointerEvent(PointerEventPass.Initial)
                                                                            if (event.changes.any { it.previousPressed && !it.pressed }) {
                                                                                event.changes.forEach { it.consume() }
                                                                                playArtistShuffle()
                                                                            }
                                                                        }
                                                                    }
                                                                }.combinedClickable(
                                                                    onClick = playArtistShuffle,
                                                                    onLongClick = {},
                                                                ),'''
text = replace_once(text, shuffle_click, shuffle_pointer, "embedded artist Shuffle click modifier")

path.write_text(text, encoding="utf-8")
print("Installed initial-pass pointer handling for embedded artist actions")
