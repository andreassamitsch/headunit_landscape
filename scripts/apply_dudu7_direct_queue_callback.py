#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"Expected one occurrence in {path}, found {count}: {old[:120]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


connection = Path("app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt")
replace_once(connection, "import kotlinx.coroutines.channels.Channel\n", "")
replace_once(connection, "import kotlinx.coroutines.flow.receiveAsFlow\n", "")
replace_once(
    connection,
    """    private val userSongSelectionChannel = Channel<Unit>(capacity = Channel.BUFFERED)
    val userSongSelections = userSongSelectionChannel.receiveAsFlow()

    fun notifyUserSongSelection() {
        userSongSelectionChannel.trySend(Unit)
    }
""",
    """    var onUserSongSelection: (() -> Unit)? = null

    fun notifyUserSongSelection() {
        onUserSongSelection?.invoke()
    }
""",
)

verify = Path("scripts/verify_dudu7_architecture.py")
text = verify.read_text(encoding="utf-8")
text = text.replace('        "userSongSelections?.collect",\n', '        "onUserSongSelection = returnToQueue",\n')
text = text.replace(
    '''    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt": (
        "Channel.BUFFERED",
        "userSongSelectionChannel.receiveAsFlow()",
        "userSongSelectionChannel.trySend(Unit)",
    ),
''',
    '''    "app/src/main/kotlin/com/metrolist/music/playback/PlayerConnection.kt": (
        "var onUserSongSelection: (() -> Unit)? = null",
        "onUserSongSelection?.invoke()",
    ),
''',
)
verify.write_text(text, encoding="utf-8")

print("Direct Dudu7 queue callback patch applied")
