#!/usr/bin/env python3
from pathlib import Path

path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/artist/ArtistScreen.kt")
text = path.read_text(encoding="utf-8")
old = """                }
            }
        }

        val isScrollingUp = lazyListState.isScrollingUp()
"""
new = """                }
            }
        }
        }

        val isScrollingUp = lazyListState.isScrollingUp()
"""
if new not in text:
    if old not in text:
        raise SystemExit("Artist keyed LazyColumn closing marker missing")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Closed the keyed artist LazyColumn render block")
