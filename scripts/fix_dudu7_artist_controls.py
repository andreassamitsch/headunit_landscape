#!/usr/bin/env python3
"""Replace the embedded artist action gesture hacks with normal Compose buttons.

The fixed Dudu7 parent pane now observes gestures at PointerEventPass.Final, so
child Material controls can consume their own clicks normally. Keeping an extra
Initial-pass pointerInput on the artist Radio/Shuffle controls makes accessibility
and real taps unreliable.
"""
from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = path.read_text(encoding="utf-8")

radio_old = '''                                                if (embeddedInPlayer) {
                                                    Row(
                                                        modifier =
                                                            Modifier
                                                                .height(40.dp)
                                                                .clip(RoundedCornerShape(50))
                                                                .border(
                                                                    width = 1.dp,
                                                                    color = MaterialTheme.colorScheme.outline,
                                                                    shape = RoundedCornerShape(50),
                                                                ).pointerInput(radioEndpoint) {
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
                                                                ).padding(horizontal = 16.dp),
                                                        verticalAlignment = Alignment.CenterVertically,
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.radio),
                                                            contentDescription = null,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = stringResource(R.string.radio),
                                                            fontSize = 14.sp,
                                                        )
                                                    }
                                                } else {
                                                    OutlinedButton(
                                                        onClick = playArtistRadio,
                                                        shape = RoundedCornerShape(50),
                                                        modifier = Modifier.height(40.dp),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.radio),
                                                            contentDescription = null,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = stringResource(R.string.radio),
                                                            fontSize = 14.sp,
                                                        )
                                                    }
                                                }
'''
radio_new = '''                                                OutlinedButton(
                                                    onClick = playArtistRadio,
                                                    shape = RoundedCornerShape(50),
                                                    modifier = Modifier.height(40.dp),
                                                ) {
                                                    Icon(
                                                        painter = painterResource(R.drawable.radio),
                                                        contentDescription = null,
                                                        modifier = Modifier.size(20.dp),
                                                    )
                                                    Spacer(modifier = Modifier.width(8.dp))
                                                    Text(
                                                        text = stringResource(R.string.radio),
                                                        fontSize = 14.sp,
                                                    )
                                                }
'''

shuffle_old = '''                                                if (embeddedInPlayer) {
                                                    Box(
                                                        contentAlignment = Alignment.Center,
                                                        modifier =
                                                            Modifier
                                                                .size(48.dp)
                                                                .clip(RoundedCornerShape(24.dp))
                                                                .background(MaterialTheme.colorScheme.primary)
                                                                .pointerInput(shuffleEndpoint) {
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
                                                                ),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.shuffle),
                                                            contentDescription = "Shuffle",
                                                            tint = MaterialTheme.colorScheme.onPrimary,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                    }
                                                } else {
                                                    IconButton(
                                                        onClick = playArtistShuffle,
                                                        modifier =
                                                            Modifier
                                                                .size(48.dp)
                                                                .background(
                                                                    MaterialTheme.colorScheme.primary,
                                                                    RoundedCornerShape(24.dp),
                                                                ),
                                                    ) {
                                                        Icon(
                                                            painter = painterResource(R.drawable.shuffle),
                                                            contentDescription = "Shuffle",
                                                            tint = MaterialTheme.colorScheme.onPrimary,
                                                            modifier = Modifier.size(20.dp),
                                                        )
                                                    }
                                                }
'''
shuffle_new = '''                                                IconButton(
                                                    onClick = playArtistShuffle,
                                                    modifier =
                                                        Modifier
                                                            .size(48.dp)
                                                            .background(
                                                                MaterialTheme.colorScheme.primary,
                                                                RoundedCornerShape(24.dp),
                                                            ),
                                                ) {
                                                    Icon(
                                                        painter = painterResource(R.drawable.shuffle),
                                                        contentDescription = "Shuffle",
                                                        tint = MaterialTheme.colorScheme.onPrimary,
                                                        modifier = Modifier.size(20.dp),
                                                    )
                                                }
'''

for label, old, new in (
    ("artist Radio control", radio_old, radio_new),
    ("artist Shuffle control", shuffle_old, shuffle_new),
):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one {label} block, found {count}")
    text = text.replace(old, new, 1)

for unused_import in (
    "import androidx.compose.foundation.border\n",
    "import androidx.compose.ui.input.pointer.PointerEventPass\n",
    "import androidx.compose.ui.input.pointer.pointerInput\n",
):
    text = text.replace(unused_import, "")

path.write_text(text, encoding="utf-8")
print("Dudu7 artist controls converted to standard Compose buttons")
