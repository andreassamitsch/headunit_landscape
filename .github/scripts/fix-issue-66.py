from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not find patch anchor: {label}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[2]
coordinator_path = root / "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinator.kt"
coordinator = coordinator_path.read_text(encoding="utf-8")

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
            withTimeoutOrNull<Boolean>(RESTORE_TIMEOUT_MS) {
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
print("Issue 66 compile and FM transition fixes applied")
