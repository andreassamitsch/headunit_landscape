@file:OptIn(androidx.media3.common.util.UnstableApi::class)

package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import com.metrolist.music.extensions.getCurrentQueueIndex
import com.metrolist.music.extensions.getQueueWindows
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

    fun queueUiState(): Dudu7QueueUiState =
        Dudu7QueueUiState(
            title = title,
            mediaIds = items.map { it.mediaId },
            currentIndex = safeIndex,
        )
}

internal data class Dudu7QueueUiState(
    val title: String?,
    val mediaIds: List<String>,
    val currentIndex: Int,
)

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

    fun markUserYtSelection(requiresRestoreBypass: Boolean) {
        pendingUserYtSelection = requiresRestoreBypass
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
        // An explicit song selection owns the next YT queue. This must bypass one
        // remembered YT snapshot restore even when YT/Favourites was already active;
        // otherwise the tab switch to Queue can resurrect the old favourites queue.
        memory.markUserYtSelection(requiresRestoreBypass = true)
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
        val fmState = physicalRadio.state.value
        if (
            fmState.isActive ||
            (fmState.isBusy && memory.activeSource == Dudu7PlaybackSource.FM)
        ) {
            return Dudu7PlaybackSource.FM
        }
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
            publishQueueUiState(playerConnection, snapshot, player)
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
            publishQueueUiState(playerConnection, snapshot, player)
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

    private fun publishQueueUiState(
        playerConnection: PlayerConnection,
        snapshot: Dudu7QueueSnapshot?,
        player: Player,
    ) {
        val effectiveTitle = snapshot?.title ?: playerConnection.service.queueTitle
        playerConnection.queueWindows.value = player.getQueueWindows()
        playerConnection.queueTitle.value = effectiveTitle
        playerConnection.currentMediaItemIndex.value = player.currentMediaItemIndex
        playerConnection.currentWindowIndex.value = player.getCurrentQueueIndex()
        playerConnection.shuffleModeEnabled.value = player.shuffleModeEnabled
        playerConnection.repeatMode.value = player.repeatMode
        Timber.tag(TAG).i(
            "Published queue UI items=%d mediaIndex=%d windowIndex=%d title=%s",
            playerConnection.queueWindows.value.size,
            playerConnection.currentMediaItemIndex.value,
            playerConnection.currentWindowIndex.value,
            effectiveTitle,
        )
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

        val restored: Boolean =
            withTimeoutOrNull(RESTORE_TIMEOUT_MS) {
                while (true) {
                    val player = playerOrNull(playerConnection)
                    if (player != null && queueMatches(player, snapshot)) {
                        applySnapshotState(player, snapshot, forcePlay)
                        publishQueueUiState(playerConnection, snapshot, player)
                        break
                    }
                    delay(25L)
                }
                true
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

    private fun playerOrNull(playerConnection: PlayerConnection): Player? =
        runCatching { playerConnection.player }.getOrNull()
}
