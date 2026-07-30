package com.metrolist.music.playback

import android.content.Context
import android.os.Looper
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.common.Player
import androidx.media3.common.SimpleBasePlayer
import androidx.media3.common.util.UnstableApi
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import com.metrolist.music.radio.fyt.FmFavouriteModel
import com.metrolist.music.radio.fyt.FmFavouriteRef
import com.metrolist.music.radio.fyt.FmPresetOrderStore
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import com.metrolist.music.radio.fyt.rememberFmFavouriteSelection
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber
import kotlin.math.abs

/**
 * Media3 representation of the FYT hardware tuner.
 *
 * The class does not render audio. The FYT/MCU audio path remains responsible for
 * sound, while this Player publishes the ordered FM favourites, current station,
 * playback state and transport commands to Android's MediaSession.
 */
@UnstableApi
internal class Dudu7FmSessionPlayer(
    context: Context,
) : SimpleBasePlayer(Looper.getMainLooper()) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val radio = FytPhysicalRadio.get(appContext)
    private val _isActive = MutableStateFlow(radio.state.value.isActive)

    val isActive: StateFlow<Boolean> = _isActive.asStateFlow()

    private var snapshot = radio.state.value
    private var favourites: List<FytPhysicalRadio.Preset> = emptyList()
    private var activeFavouriteId: String? = null
    private var currentIndex: Int = C.INDEX_UNSET
    private var released = false

    init {
        syncFromRadio(snapshot)
        scope.launch {
            radio.state.collect { state ->
                syncFromRadio(state)
            }
        }
    }

    override fun getState(): State {
        val playlist = buildPlaylist()
        val hasItems = playlist.isNotEmpty()
        val index = if (hasItems) currentIndex.coerceIn(0, playlist.lastIndex) else C.INDEX_UNSET
        val active = snapshot.isActive

        return State.Builder()
            .setAvailableCommands(availableCommands(hasItems))
            .setPlaylist(playlist)
            .setPlaylistMetadata(
                MediaMetadata.Builder()
                    .setTitle("FM-Favoriten")
                    .setMediaType(MediaMetadata.MEDIA_TYPE_PLAYLIST)
                    .build(),
            )
            .setCurrentMediaItemIndex(index)
            .setContentPositionMs(0L)
            .setPlaybackState(if (hasItems && active) Player.STATE_READY else Player.STATE_IDLE)
            .setPlayWhenReady(
                active && !snapshot.isMuted,
                Player.PLAY_WHEN_READY_CHANGE_REASON_REMOTE,
            )
            .setRepeatMode(Player.REPEAT_MODE_ALL)
            .setShuffleModeEnabled(false)
            .build()
    }

    override fun handlePrepare(): ListenableFuture<Any> {
        if (!snapshot.isActive) radio.powerOn()
        return completed()
    }

    override fun handleSetPlayWhenReady(playWhenReady: Boolean): ListenableFuture<Any> {
        if (playWhenReady) {
            if (!snapshot.isActive) radio.powerOn()
            radio.setMute(false)
        } else if (snapshot.isActive) {
            radio.setMute(true)
        }
        return completed()
    }

    override fun handleSeek(
        mediaItemIndex: Int,
        positionMs: Long,
        seekCommand: Int,
    ): ListenableFuture<Any> {
        if (favourites.isEmpty()) {
            when (seekCommand) {
                Player.COMMAND_SEEK_TO_NEXT,
                Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
                -> radio.seek(true)

                Player.COMMAND_SEEK_TO_PREVIOUS,
                Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
                -> radio.seek(false)
            }
            return completed()
        }

        val targetIndex = when (seekCommand) {
            Player.COMMAND_SEEK_TO_NEXT,
            Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM,
            -> Dudu7FmSessionNavigation.adjacentIndex(favourites.size, currentIndex, next = true)

            Player.COMMAND_SEEK_TO_PREVIOUS,
            Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM,
            -> Dudu7FmSessionNavigation.adjacentIndex(favourites.size, currentIndex, next = false)

            Player.COMMAND_SEEK_TO_MEDIA_ITEM,
            Player.COMMAND_SEEK_TO_DEFAULT_POSITION,
            -> mediaItemIndex.takeIf { it in favourites.indices } ?: currentIndex

            else -> mediaItemIndex.takeIf { it in favourites.indices } ?: currentIndex
        }

        favourites.getOrNull(targetIndex)?.let { target ->
            activeFavouriteId = target.id
            currentIndex = targetIndex
            rememberFmFavouriteSelection(target.id)
            invalidateState()
            Timber.tag(TAG).i(
                "Media3 FM seek command=%d targetIndex=%d target=%s frequency=%.1f",
                seekCommand,
                targetIndex,
                target.id,
                target.frequency,
            )
            radio.tunePreset(target)
        }
        return completed()
    }

    override fun handleRelease(): ListenableFuture<Any> {
        if (!released) {
            released = true
            scope.cancel()
        }
        return completed()
    }

    private fun syncFromRadio(state: FytPhysicalRadio.State) {
        snapshot = state
        favourites = FmPresetOrderStore.ordered(appContext, state.presets)
        val validIds = favourites.mapNotNull { it.id.takeIf(String::isNotBlank) }.toSet()
        val detectedId = state.currentPreset?.id?.takeIf { it in validIds }

        activeFavouriteId = Dudu7FmSessionNavigation.retainActiveId(
            validIds = validIds,
            rememberedId = activeFavouriteId,
            detectedId = detectedId,
            fallbackId = resolveCurrentFavouriteId(state),
        )

        currentIndex = favourites.indexOfFirst { it.id == activeFavouriteId }
        if (currentIndex < 0 && favourites.isNotEmpty()) {
            val resolvedIndex = resolveCurrentIndex(state)
            currentIndex = if (resolvedIndex >= 0) resolvedIndex else 0
            activeFavouriteId = favourites[currentIndex].id
        }

        _isActive.value = state.isActive
        invalidateState()
    }

    private fun resolveCurrentFavouriteId(state: FytPhysicalRadio.State): String? {
        val index = resolveCurrentIndex(state)
        return favourites.getOrNull(index)?.id
    }

    private fun resolveCurrentIndex(state: FytPhysicalRadio.State): Int {
        if (favourites.isEmpty()) return C.INDEX_UNSET
        val stationId = state.rtrStableId.takeIf {
            abs(state.rtrMatchedFrequency - state.frequency) < 0.05f && state.rtrMatchConfidence >= 60
        }.orEmpty()
        val freshRds = state.rdsConfirmed && abs(state.rdsFreshFrequency - state.frequency) < 0.05f
        return FmFavouriteModel.resolveCurrentIndex(
            favourites = favourites.map { FmFavouriteRef(it.id, it.stationId, it.frequency, it.pi) },
            activeId = activeFavouriteId,
            frequency = state.frequency,
            stationId = stationId,
            pi = state.pi,
            rdsConfirmed = freshRds,
        )
    }

    private fun buildPlaylist(): List<MediaItemData> {
        if (favourites.isEmpty()) {
            if (!snapshot.isActive) return emptyList()
            val metadata = currentMetadata(
                title = snapshot.displayStation.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" },
                frequency = snapshot.frequency,
                radioText = snapshot.rt,
            )
            val item = MediaItem.Builder()
                .setMediaId("fm:live:${formatFrequency(snapshot.frequency)}")
                .setMediaMetadata(metadata)
                .build()
            return listOf(
                MediaItemData.Builder(item.mediaId)
                    .setMediaItem(item)
                    .setMediaMetadata(metadata)
                    .setDurationUs(C.TIME_UNSET)
                    .setIsSeekable(false)
                    .build(),
            )
        }

        return favourites.mapIndexed { index, preset ->
            val isCurrent = index == currentIndex
            val frequency = if (isCurrent && snapshot.isActive) snapshot.frequency else preset.frequency
            val title = if (isCurrent && snapshot.isActive) {
                snapshot.displayStation.ifBlank { preset.name }
            } else {
                preset.name
            }
            val metadata = currentMetadata(
                title = title,
                frequency = frequency,
                radioText = snapshot.rt.takeIf { isCurrent && snapshot.isActive }.orEmpty(),
            )
            val id = preset.id.ifBlank { "frequency:${formatFrequency(preset.frequency)}" }
            val item = MediaItem.Builder()
                .setMediaId("fm:$id")
                .setMediaMetadata(metadata)
                .build()
            MediaItemData.Builder(id)
                .setMediaItem(item)
                .setMediaMetadata(metadata)
                .setDurationUs(C.TIME_UNSET)
                .setIsSeekable(false)
                .build()
        }
    }

    private fun currentMetadata(
        title: String,
        frequency: Float,
        radioText: String,
    ): MediaMetadata {
        val subtitle = buildString {
            append(formatFrequency(frequency))
            append(" MHz")
            radioText.trim().takeIf(String::isNotBlank)?.let {
                append(" • ")
                append(it)
            }
        }
        return MediaMetadata.Builder()
            .setTitle(title.ifBlank { "FM-Radio" })
            .setArtist(subtitle)
            .setAlbumTitle("FM-Radio")
            .setIsPlayable(true)
            .setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC)
            .build()
    }

    private fun availableCommands(hasItems: Boolean): Player.Commands =
        Player.Commands.Builder()
            .add(Player.COMMAND_PLAY_PAUSE)
            .add(Player.COMMAND_PREPARE)
            .add(Player.COMMAND_GET_CURRENT_MEDIA_ITEM)
            .add(Player.COMMAND_GET_TIMELINE)
            .add(Player.COMMAND_GET_METADATA)
            .add(Player.COMMAND_RELEASE)
            .addIf(Player.COMMAND_SEEK_TO_MEDIA_ITEM, hasItems)
            .addIf(Player.COMMAND_SEEK_TO_DEFAULT_POSITION, hasItems)
            .addIf(Player.COMMAND_SEEK_TO_NEXT, hasItems)
            .addIf(Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM, hasItems)
            .addIf(Player.COMMAND_SEEK_TO_PREVIOUS, hasItems)
            .addIf(Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM, hasItems)
            .build()

    private fun completed(): ListenableFuture<Any> = Futures.immediateFuture(Unit as Any)


    private fun formatFrequency(value: Float): String = "%.1f".format(java.util.Locale.US, value)

    companion object {
        private const val TAG = "Dudu7FmSessionPlayer"
    }
}
