from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new and new in text:
        return text
    if old not in text:
        raise RuntimeError(f"Could not find patch anchor: {label}")
    return text.replace(old, new, 1)


root = Path(__file__).resolve().parents[2]
layout_path = root / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
coordinator_path = root / "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinator.kt"
test_path = root / "app/src/test/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinatorTest.kt"
build_path = root / "app/build.gradle.kts"

layout = layout_path.read_text(encoding="utf-8")
layout = replace_once(
    layout,
    "import com.metrolist.music.R\nimport com.metrolist.music.extensions.move\n",
    "import com.metrolist.music.R\n"
    "import com.metrolist.music.extensions.move\n"
    "import com.metrolist.music.playback.Dudu7PlaybackSource\n"
    "import com.metrolist.music.playback.Dudu7SourcePlaybackCoordinator\n",
    "Dudu7 source playback imports",
)
layout = replace_once(
    layout,
    """    LaunchedEffect(currentPaneRoute) {
        VehicleRightPaneTab.entries
            .firstOrNull { it.route == currentPaneRoute }
            ?.let { selectedTab = it }
    }

    LaunchedEffect(androidIsPlaying, physicalRadioState.isActive) {
        if (androidIsPlaying && physicalRadioState.isActive) {
            physicalRadio.powerOff()
        }
    }
""",
    """    LaunchedEffect(currentPaneRoute) {
        VehicleRightPaneTab.entries
            .firstOrNull { it.route == currentPaneRoute }
            ?.let { selectedTab = it }
    }

    LaunchedEffect(selectedTab, playerConnection) {
        val activeConnection = playerConnection ?: return@LaunchedEffect
        val targetSource =
            when (selectedTab) {
                VehicleRightPaneTab.QUEUE -> Dudu7PlaybackSource.YT_MUSIC
                VehicleRightPaneTab.WEBRADIO -> Dudu7PlaybackSource.WEBRADIO
                VehicleRightPaneTab.PHYSICAL_RADIO -> Dudu7PlaybackSource.FM
                else -> null
            }
        if (targetSource != null) {
            Dudu7SourcePlaybackCoordinator.activate(
                context = context,
                target = targetSource,
                playerConnection = activeConnection,
                physicalRadio = physicalRadio,
            )
        }
    }

    LaunchedEffect(androidIsPlaying, physicalRadioState.isActive) {
        if (
            androidIsPlaying &&
            physicalRadioState.isActive &&
            Dudu7SourcePlaybackCoordinator.activeSource != Dudu7PlaybackSource.FM
        ) {
            physicalRadio.powerOff()
        }
    }
""",
    "tab source activation effect",
)
layout = replace_once(
    layout,
    """        val returnToQueue: () -> Unit = {
            if (physicalRadio.state.value.isActive) physicalRadio.powerOff()
            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {
""",
    """        val returnToQueue: () -> Unit = {
            if (activeConnection != null) {
                Dudu7SourcePlaybackCoordinator.prepareForUserSongSelection(
                    context = context,
                    playerConnection = activeConnection,
                    physicalRadio = physicalRadio,
                )
            } else if (physicalRadio.state.value.isActive) {
                physicalRadio.powerOff()
            }
            if (paneNavController.currentDestination?.route != VEHICLE_QUEUE_ROUTE) {
""",
    "user song selection source handoff",
)
layout = replace_once(
    layout,
    """                                        if (tab == VehicleRightPaneTab.WEBRADIO && physicalRadio.state.value.isActive) {
                                            physicalRadio.powerOff()
                                        }
""",
    "",
    "legacy WebRadio-only FM shutdown",
)
layout_path.write_text(layout, encoding="utf-8")

coordinator_path.parent.mkdir(parents=True, exist_ok=True)
coordinator_path.write_text(
    r'''@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import com.metrolist.music.playback.queues.ListQueue
import com.metrolist.music.radio.RadioStationStore
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.isRadioMediaId
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import timber.log.Timber

internal enum class Dudu7PlaybackSource {
    YT_MUSIC,
    WEBRADIO,
    FM,
}

internal data class Dudu7QueueSnapshot(
    val title: String?,
    val items: List<MediaItem>,
    val currentIndex: Int,
    val currentPositionMs: Long,
    val playWhenReady: Boolean,
    val repeatMode: Int,
    val shuffleModeEnabled: Boolean,
) {
    init {
        require(items.isNotEmpty())
    }

    val safeIndex: Int
        get() = currentIndex.coerceIn(0, items.lastIndex)

    val currentMediaId: String?
        get() = items.getOrNull(safeIndex)?.mediaId

    fun belongsTo(source: Dudu7PlaybackSource): Boolean {
        val allRadio = items.all { isRadioMediaId(it.mediaId) }
        val containsRadio = items.any { isRadioMediaId(it.mediaId) }
        return when (source) {
            Dudu7PlaybackSource.YT_MUSIC -> !containsRadio
            Dudu7PlaybackSource.WEBRADIO -> allRadio
            Dudu7PlaybackSource.FM -> false
        }
    }
}

internal class Dudu7SourcePlaybackMemory {
    private val snapshots = mutableMapOf<Dudu7PlaybackSource, Dudu7QueueSnapshot>()

    var activeSource: Dudu7PlaybackSource? = null
    private var pendingUserYtSelection = false

    fun save(
        source: Dudu7PlaybackSource,
        snapshot: Dudu7QueueSnapshot,
    ): Boolean {
        if (!snapshot.belongsTo(source)) return false
        snapshots[source] = snapshot
        return true
    }

    fun snapshot(source: Dudu7PlaybackSource): Dudu7QueueSnapshot? = snapshots[source]

    fun markUserYtSelection() {
        pendingUserYtSelection = true
        activeSource = Dudu7PlaybackSource.YT_MUSIC
    }

    fun consumeUserYtSelection(): Boolean {
        val pending = pendingUserYtSelection
        pendingUserYtSelection = false
        return pending
    }
}

internal object Dudu7SourcePlaybackCoordinator {
    private const val TAG = "Dudu7SourcePlayback"
    private const val PREFS = "dudu7_source_playback"
    private const val KEY_LAST_WEBRADIO_MEDIA_ID = "last_webradio_media_id"
    private const val RESTORE_TIMEOUT_MS = 3_000L
    private const val FM_SHUTDOWN_TIMEOUT_MS = 2_000L

    private val transitionMutex = Mutex()
    private val memory = Dudu7SourcePlaybackMemory()

    val activeSource: Dudu7PlaybackSource?
        get() = memory.activeSource

    fun prepareForUserSongSelection(
        context: Context,
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ) {
        val current = inferSource(playerConnection, physicalRadio)
        if (current == Dudu7PlaybackSource.WEBRADIO) {
            captureQueue(context, playerConnection, current)
        }
        if (physicalRadio.state.value.isActive) {
            physicalRadio.powerOff()
        }
        memory.markUserYtSelection()
        Timber.tag(TAG).i("User selected YT content; source handoff prepared from %s", current)
    }

    suspend fun activate(
        context: Context,
        target: Dudu7PlaybackSource,
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ) {
        transitionMutex.withLock {
            if (target == Dudu7PlaybackSource.YT_MUSIC && memory.consumeUserYtSelection()) {
                memory.activeSource = Dudu7PlaybackSource.YT_MUSIC
                stopPhysicalRadioAndWait(physicalRadio)
                Timber.tag(TAG).i("YT source accepted explicit user queue replacement")
                return@withLock
            }

            val current = inferSource(playerConnection, physicalRadio)
            if (current != target) {
                captureQueue(context, playerConnection, current)
            }
            memory.activeSource = target

            when (target) {
                Dudu7PlaybackSource.FM -> activateFm(playerConnection, physicalRadio)
                Dudu7PlaybackSource.WEBRADIO -> activateWebRadio(context, playerConnection, physicalRadio, current)
                Dudu7PlaybackSource.YT_MUSIC -> activateYtMusic(playerConnection, physicalRadio)
            }
        }
    }

    private fun inferSource(
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ): Dudu7PlaybackSource {
        if (physicalRadio.state.value.isActive) return Dudu7PlaybackSource.FM
        val mediaId = playerOrNull(playerConnection)?.currentMediaItem?.mediaId
        return if (isRadioMediaId(mediaId)) {
            Dudu7PlaybackSource.WEBRADIO
        } else {
            Dudu7PlaybackSource.YT_MUSIC
        }
    }

    private fun captureQueue(
        context: Context,
        playerConnection: PlayerConnection,
        source: Dudu7PlaybackSource,
    ): Dudu7QueueSnapshot? {
        if (source == Dudu7PlaybackSource.FM) return null
        val player = playerOrNull(playerConnection) ?: return null
        if (player.mediaItemCount <= 0) return null
        val snapshot =
            Dudu7QueueSnapshot(
                title = playerConnection.queueTitle.value,
                items = List(player.mediaItemCount) { player.getMediaItemAt(it) },
                currentIndex = player.currentMediaItemIndex.coerceAtLeast(0),
                currentPositionMs = player.currentPosition.coerceAtLeast(0L),
                playWhenReady = player.playWhenReady,
                repeatMode = player.repeatMode,
                shuffleModeEnabled = player.shuffleModeEnabled,
            )
        if (!memory.save(source, snapshot)) {
            Timber.tag(TAG).w(
                "Rejected mismatching queue snapshot source=%s current=%s",
                source,
                snapshot.currentMediaId,
            )
            return null
        }
        if (source == Dudu7PlaybackSource.WEBRADIO) {
            snapshot.currentMediaId?.let { mediaId ->
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                    .edit()
                    .putString(KEY_LAST_WEBRADIO_MEDIA_ID, mediaId)
                    .apply()
            }
        }
        Timber.tag(TAG).i(
            "Captured %s queue items=%d index=%d position=%d playing=%s",
            source,
            snapshot.items.size,
            snapshot.safeIndex,
            snapshot.currentPositionMs,
            snapshot.playWhenReady,
        )
        return snapshot
    }

    private fun activateFm(
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ) {
        playerConnection.pause()
        val state = physicalRadio.state.value
        if (!state.isActive) {
            physicalRadio.powerOn(state.frequency)
        }
        Timber.tag(TAG).i("Activated FM at remembered frequency %.1f", state.frequency)
    }

    private suspend fun activateWebRadio(
        context: Context,
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
        previousSource: Dudu7PlaybackSource,
    ) {
        stopPhysicalRadioAndWait(physicalRadio)
        val snapshot = memory.snapshot(Dudu7PlaybackSource.WEBRADIO)
        val player = playerOrNull(playerConnection)
        if (
            previousSource == Dudu7PlaybackSource.WEBRADIO &&
            player != null &&
            isRadioMediaId(player.currentMediaItem?.mediaId)
        ) {
            playerConnection.play()
            Timber.tag(TAG).i("WebRadio already active; resumed current favourite")
            return
        }
        if (snapshot != null) {
            activateSnapshot(playerConnection, snapshot, forcePlay = true)
            Timber.tag(TAG).i(
                "Restored WebRadio items=%d index=%d",
                snapshot.items.size,
                snapshot.safeIndex,
            )
            return
        }
        startRememberedWebRadio(context, playerConnection)
    }

    private suspend fun activateYtMusic(
        playerConnection: PlayerConnection,
        physicalRadio: FytPhysicalRadio,
    ) {
        stopPhysicalRadioAndWait(physicalRadio)
        val snapshot = memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)
        if (snapshot == null) {
            val player = playerOrNull(playerConnection)
            if (isRadioMediaId(player?.currentMediaItem?.mediaId)) {
                playerConnection.pause()
            }
            Timber.tag(TAG).w("No remembered YT queue available")
            return
        }
        activateSnapshot(
            playerConnection = playerConnection,
            snapshot = snapshot,
            forcePlay = snapshot.playWhenReady,
        )
        Timber.tag(TAG).i(
            "Restored YT queue items=%d index=%d position=%d playing=%s",
            snapshot.items.size,
            snapshot.safeIndex,
            snapshot.currentPositionMs,
            snapshot.playWhenReady,
        )
    }

    private suspend fun activateSnapshot(
        playerConnection: PlayerConnection,
        snapshot: Dudu7QueueSnapshot,
        forcePlay: Boolean,
    ) {
        val player = playerOrNull(playerConnection)
        if (player != null && queueMatches(player, snapshot)) {
            applySnapshotState(player, snapshot, forcePlay)
            return
        }
        restoreQueue(playerConnection, snapshot, forcePlay)
    }

    private fun queueMatches(
        player: Player,
        snapshot: Dudu7QueueSnapshot,
    ): Boolean {
        if (player.mediaItemCount != snapshot.items.size) return false
        return snapshot.items.indices.all { index ->
            player.getMediaItemAt(index).mediaId == snapshot.items[index].mediaId
        }
    }

    private fun applySnapshotState(
        player: Player,
        snapshot: Dudu7QueueSnapshot,
        forcePlay: Boolean,
    ) {
        player.repeatMode = snapshot.repeatMode
        player.shuffleModeEnabled = snapshot.shuffleModeEnabled
        if (snapshot.belongsTo(Dudu7PlaybackSource.WEBRADIO)) {
            if (player.currentMediaItemIndex != snapshot.safeIndex) {
                player.seekToDefaultPosition(snapshot.safeIndex)
            }
        } else {
            player.seekTo(snapshot.safeIndex, snapshot.currentPositionMs)
        }
        if (player.playbackState == Player.STATE_IDLE) {
            player.prepare()
        }
        player.playWhenReady = forcePlay
    }

    private suspend fun restoreQueue(
        playerConnection: PlayerConnection,
        snapshot: Dudu7QueueSnapshot,
        forcePlay: Boolean,
    ) {
        playerConnection.service.playQueue(
            queue =
                ListQueue(
                    title = snapshot.title,
                    items = snapshot.items,
                    startIndex = snapshot.safeIndex,
                    position = snapshot.currentPositionMs,
                ),
            playWhenReady = forcePlay,
        )

        val restored =
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
            Timber.tag(TAG).w(
                "Queue restore timed out current=%s expected=%s",
                playerOrNull(playerConnection)?.currentMediaItem?.mediaId,
                snapshot.currentMediaId,
            )
        }
    }

    private suspend fun startRememberedWebRadio(
        context: Context,
        playerConnection: PlayerConnection,
    ) {
        val stations = RadioStationStore.get(context.applicationContext).stations.value.distinctBy { it.uuid }
        if (stations.isEmpty()) {
            Timber.tag(TAG).w("Cannot auto-start WebRadio because no favourites are saved")
            return
        }
        val lastMediaId =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_LAST_WEBRADIO_MEDIA_ID, null)
        val startIndex = stations.indexOfFirst { it.mediaId == lastMediaId }.takeIf { it >= 0 } ?: 0
        val selected = stations[startIndex]
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LAST_WEBRADIO_MEDIA_ID, selected.mediaId)
            .apply()
        playerConnection.service.playQueue(
            queue =
                ListQueue(
                    title = "WebRadio",
                    items = stations.map { it.toMediaItem() },
                    startIndex = startIndex,
                ),
            playWhenReady = true,
        )
        Timber.tag(TAG).i(
            "Started remembered WebRadio favourite index=%d mediaId=%s",
            startIndex,
            selected.mediaId,
        )
    }

    private suspend fun stopPhysicalRadioAndWait(physicalRadio: FytPhysicalRadio) {
        val state = physicalRadio.state.value
        if (!state.isActive && !state.isBusy) return
        physicalRadio.powerOff()
        withTimeoutOrNull(FM_SHUTDOWN_TIMEOUT_MS) {
            physicalRadio.state.first { !it.isActive && !it.isBusy }
        }
    }

    private fun playerOrNull(playerConnection: PlayerConnection): Player? =
        runCatching { playerConnection.player }.getOrNull()
}
''',
    encoding="utf-8",
)

test_path.parent.mkdir(parents=True, exist_ok=True)
test_path.write_text(
    r'''package com.metrolist.music.playback

import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7SourcePlaybackCoordinatorTest {
    private fun item(mediaId: String): MediaItem =
        MediaItem.Builder()
            .setMediaId(mediaId)
            .build()

    @Test
    fun `YT and WebRadio queues are retained independently`() {
        val memory = Dudu7SourcePlaybackMemory()
        val yt =
            Dudu7QueueSnapshot(
                title = "YT queue",
                items = listOf(item("song-1"), item("song-2"), item("song-3")),
                currentIndex = 1,
                currentPositionMs = 42_500L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_ALL,
                shuffleModeEnabled = true,
            )
        val web =
            Dudu7QueueSnapshot(
                title = "WebRadio",
                items = listOf(item("radio:a"), item("radio:b"), item("radio:c")),
                currentIndex = 2,
                currentPositionMs = 0L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_OFF,
                shuffleModeEnabled = false,
            )

        assertTrue(memory.save(Dudu7PlaybackSource.YT_MUSIC, yt))
        assertTrue(memory.save(Dudu7PlaybackSource.WEBRADIO, web))

        assertEquals(listOf("song-1", "song-2", "song-3"), memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.items?.map { it.mediaId })
        assertEquals(1, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.safeIndex)
        assertEquals(42_500L, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.currentPositionMs)
        assertEquals(Player.REPEAT_MODE_ALL, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.repeatMode)
        assertEquals(true, memory.snapshot(Dudu7PlaybackSource.YT_MUSIC)?.shuffleModeEnabled)

        assertEquals(listOf("radio:a", "radio:b", "radio:c"), memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.items?.map { it.mediaId })
        assertEquals(2, memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.safeIndex)
        assertEquals("radio:c", memory.snapshot(Dudu7PlaybackSource.WEBRADIO)?.currentMediaId)
    }

    @Test
    fun `queue snapshot cannot overwrite a different source`() {
        val memory = Dudu7SourcePlaybackMemory()
        val web =
            Dudu7QueueSnapshot(
                title = "WebRadio",
                items = listOf(item("radio:a")),
                currentIndex = 0,
                currentPositionMs = 0L,
                playWhenReady = true,
                repeatMode = Player.REPEAT_MODE_OFF,
                shuffleModeEnabled = false,
            )

        assertFalse(memory.save(Dudu7PlaybackSource.YT_MUSIC, web))
        assertNull(memory.snapshot(Dudu7PlaybackSource.YT_MUSIC))
        assertTrue(memory.save(Dudu7PlaybackSource.WEBRADIO, web))
    }

    @Test
    fun `out of range queue index is safely clamped`() {
        val snapshot =
            Dudu7QueueSnapshot(
                title = null,
                items = listOf(item("song-1"), item("song-2")),
                currentIndex = 99,
                currentPositionMs = 1_000L,
                playWhenReady = false,
                repeatMode = Player.REPEAT_MODE_ONE,
                shuffleModeEnabled = false,
            )

        assertEquals(1, snapshot.safeIndex)
        assertEquals("song-2", snapshot.currentMediaId)
    }

    @Test
    fun `explicit YT selection is consumed exactly once`() {
        val memory = Dudu7SourcePlaybackMemory()

        memory.markUserYtSelection()

        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)
        assertTrue(memory.consumeUserYtSelection())
        assertFalse(memory.consumeUserYtSelection())
    }
}
''',
    encoding="utf-8",
)

build = build_path.read_text(encoding="utf-8")
build = replace_once(
    build,
    '        versionCode = 1370045\n        versionName = "13.7.36"\n',
    '        versionCode = 1370046\n        versionName = "13.7.37"\n',
    "Dudu7 version 13.7.37",
)
build_path.write_text(build, encoding="utf-8")

print("Issue 66 source-state implementation applied")
