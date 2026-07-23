from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = path.read_text(encoding="utf-8")

malformed = '''                                            artistPage?.artist?.radioEndpoint?.let { radioEndpoint ->
                                                OutlinedButton(
                                                    onClick = {
                                                        if (embeddedInPlayer) {
                                                        navController.popBackStack("vehicle_queue", inclusive = false)
                                                    }
                                                    playerConnection.playQueue(YouTubeQueue(radioEndpoint))
                                                    },
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
                                            }'''

normalized = '''                                            artistPage?.artist?.radioEndpoint?.let { radioEndpoint ->
                                                OutlinedButton(
                                                    onClick = {
                                                        if (embeddedInPlayer) {
                                                            navController.popBackStack("vehicle_queue", inclusive = false)
                                                        }
                                                        playerConnection.playQueue(YouTubeQueue(radioEndpoint))
                                                    },
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
                                            }'''

if malformed not in text:
    raise SystemExit("Expected malformed embedded artist Radio block was not found")

path.write_text(text.replace(malformed, normalized, 1), encoding="utf-8")
print("Normalized embedded artist Radio source")
