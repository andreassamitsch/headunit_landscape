from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not find patch anchor: {label}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[2]
coordinator_path = root / "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinator.kt"
test_path = root / "app/src/test/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinatorTest.kt"
coordinator = coordinator_path.read_text(encoding="utf-8")

coordinator = replace_once(
    coordinator,
    """    fun markUserYtSelection() {
        pendingUserYtSelection = true
        activeSource = Dudu7PlaybackSource.YT_MUSIC
    }
""",
    """    fun markUserYtSelection(requiresRestoreBypass: Boolean) {
        pendingUserYtSelection = requiresRestoreBypass
        activeSource = Dudu7PlaybackSource.YT_MUSIC
    }
""",
    "explicit YT handoff state",
)

coordinator = replace_once(
    coordinator,
    """        memory.markUserYtSelection()
        Timber.tag(TAG).i("User selected YT content; source handoff prepared from %s", current)
""",
    """        memory.markUserYtSelection(
            requiresRestoreBypass = current != Dudu7PlaybackSource.YT_MUSIC,
        )
        Timber.tag(TAG).i("User selected YT content; source handoff prepared from %s", current)
""",
    "YT selection from current source",
)

coordinator = replace_once(
    coordinator,
    """    private fun inferSource(
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ): Dudu7PlaybackSource {
        if (physicalRadio.state.value.isActive) return Dudu7PlaybackSource.FM
        val mediaId = playerOrNull(playerConnection)?.currentMediaItem?.mediaId
""",
    """    private fun inferSource(
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ): Dudu7PlaybackSource {
        val fmState = physicalRadio.state.value
        if (
            fmState.isActive ||
            (fmState.isBusy && memory.activeSource == Dudu7PlaybackSource.FM)
        ) {
            return Dudu7PlaybackSource.FM
        }
        val mediaId = playerOrNull(playerConnection)?.currentMediaItem?.mediaId
""",
    "FM startup source inference",
)

coordinator = replace_once(
    coordinator,
    """        val restored =
            withTimeoutOrNull(RESTORE_TIMEOUT_MS) {
                while (true) {
                    val player = playerOrNull(playerConnection)
                    if (player != null && queueMatches(player, snapshot)) {
                        applySnapshotState(player, snapshot, forcePlay)
                        return@withTimeoutOrNull true
                    }
                    delay(25L)
                }
            } ?: false
        if (!restored) {
""",
    """        val restored: Boolean =
            withTimeoutOrNull(RESTORE_TIMEOUT_MS) {
                while (true) {
                    val player = playerOrNull(playerConnection)
                    if (player != null && queueMatches(player, snapshot)) {
                        applySnapshotState(player, snapshot, forcePlay)
                        break
                    }
                    delay(25L)
                }
                true
            } ?: false
        if (!restored) {
""",
    "Boolean queue restore result",
)

coordinator = replace_once(
    coordinator,
    """    private suspend fun stopPhysicalRadioAndWait(physicalRadio: FytPhysicalRadio) {
        val state = physicalRadio.state.value
        if (!state.isActive && !state.isBusy) return
        physicalRadio.powerOff()
        withTimeoutOrNull(FM_SHUTDOWN_TIMEOUT_MS) {
            physicalRadio.state.first { !it.isActive && !it.isBusy }
        }
    }
""",
    """    private suspend fun stopPhysicalRadioAndWait(physicalRadio: FytPhysicalRadio) {
        var state = physicalRadio.state.value
        if (!state.isActive && !state.isBusy) return

        if (state.isBusy && !state.isActive) {
            withTimeoutOrNull(FM_SHUTDOWN_TIMEOUT_MS) {
                physicalRadio.state.first { !it.isBusy }
            }
            state = physicalRadio.state.value
        }

        if (state.isActive) {
            physicalRadio.powerOff()
            withTimeoutOrNull(FM_SHUTDOWN_TIMEOUT_MS) {
                physicalRadio.state.first { !it.isActive && !it.isBusy }
            }
        }
    }
""",
    "FM startup shutdown handoff",
)

coordinator_path.write_text(coordinator, encoding="utf-8")

test = test_path.read_text(encoding="utf-8")
test = replace_once(
    test,
    """        memory.markUserYtSelection()

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
""",
    """        memory.markUserYtSelection(requiresRestoreBypass = true)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
""",
    "explicit YT handoff test call",
)
test = replace_once(
    test,
    """    @Test
    fun `explicit YT selection is consumed exactly once`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection(requiresRestoreBypass = true)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertTrue(memory.consumeUserYtSelection())
        assertFalse(memory.consumeUserYtSelection())
    }
}
""",
    """    @Test
    fun `explicit YT selection is consumed exactly once`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection(requiresRestoreBypass = true)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertTrue(memory.consumeUserYtSelection())
        assertFalse(memory.consumeUserYtSelection())
    }

    @Test
    fun `new YT selection while YT is already active leaves no stale bypass`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection(requiresRestoreBypass = false)

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertFalse(memory.consumeUserYtSelection())
    }
}
""",
    "same-source YT selection regression test",
)
test_path.write_text(test, encoding="utf-8")

print("Issue 66 compile, FM transition and YT handoff fixes applied")
