/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.playback

import android.content.Context
import androidx.media3.common.MediaItem
import androidx.media3.common.Metadata
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.common.Player.COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM
import androidx.media3.common.Player.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM
import androidx.media3.common.Player.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM
import androidx.media3.common.Player.REPEAT_MODE_OFF
import androidx.media3.common.Player.STATE_ENDED
import androidx.media3.common.Timeline
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.extractor.metadata.icy.IcyInfo
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.constants.SleepTimerCustomDaysKey
import com.metrolist.music.constants.SleepTimerDayTimesKey
import com.metrolist.music.constants.SleepTimerDefaultKey
import com.metrolist.music.constants.SleepTimerEnabledKey
import com.metrolist.music.constants.SleepTimerEndTimeKey
import com.metrolist.music.constants.SleepTimerRepeatKey
import com.metrolist.music.constants.SleepTimerStartTimeKey
import com.metrolist.music.db.MusicDatabase
import com.metrolist.music.extensions.currentMetadata
import com.metrolist.music.extensions.getCurrentQueueIndex
import com.metrolist.music.extensions.getQueueWindows
import com.metrolist.music.extensions.metadata
import com.metrolist.music.extensions.togglePlayPause
import com.metrolist.music.playback.MusicService.MusicBinder
import com.metrolist.music.playback.queues.Queue
import com.metrolist.music.radio.isRadioMediaId
import com.metrolist.shazamkit.models.RecognitionResult
import com.metrolist.music.utils.dataStore
import com.metrolist.music.utils.get
import com.metrolist.music.utils.reportException
import com.metrolist.music.ui.utils.resize
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import timber.log.Timber
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlin.math.roundToInt

@OptIn(ExperimentalCoroutinesApi::class)
@androidx.media3.common.util.UnstableApi
class PlayerConnection(
    context: Context,
    binder: MusicBinder,
    val database: MusicDatabase,
    private val scope: CoroutineScope,
) : Player.Listener {
    private companion object {
        private const val TAG = "PlayerConnection"
    }

    val service = binder.service
    private val playerReadinessFlow = service.isPlayerReady

    private fun getPlayerSafe(): ExoPlayer {
        check(playerReadinessFlow.value) {
            "Player not yet initialized in MusicService; " +
                "service.isPlayerReady=${playerReadinessFlow.value}"
        }
        return try {
            service.player
        } catch (e: UninitializedPropertyAccessException) {
            throw IllegalStateException(
                "MusicService.player field not initialized despite isPlayerReady=true; " +
                    "possible race condition in service startup",
                e,
            )
        }
    }

    private fun getPlayerOrNull(): ExoPlayer? =
        try {
            if (!playerReadinessFlow.value) return null
            service.player
        } catch (_: UninitializedPropertyAccessException) {
            null
        } catch (_: NullPointerException) {
            null
        }

    val player: ExoPlayer
        get() = getPlayerSafe()

    /** Tracks whether player initialization completed successfully */
    private val isPlayerInitialized = MutableStateFlow(service.isPlayerReady.value)

    val playbackState: MutableStateFlow<Int>
    private val playWhenReady: MutableStateFlow<Boolean>
    val isPlaying: kotlinx.coroutines.flow.StateFlow<Boolean>

    private val initialState: Triple<Int, Boolean, Boolean> =
        try {
            val initialPlayer = getPlayerOrNull()
            if (initialPlayer != null) {
                Triple(
                    initialPlayer.playbackState,
                    initialPlayer.playWhenReady,
                    initialPlayer.playWhenReady && initialPlayer.playbackState != STATE_ENDED,
                )
            } else {
                Timber.tag(TAG).w("Player not ready during construction; using safe defaults")
                Triple(Player.STATE_IDLE, false, false)
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error during PlayerConnection initialization, using defaults")
            Triple(Player.STATE_IDLE, false, false)
        }

    init {
        Timber.tag(TAG).d("PlayerConnection init: playerReady=${playerReadinessFlow.value}")

        playbackState = MutableStateFlow(initialState.first)
        playWhenReady = MutableStateFlow(initialState.second)
        isPlaying =
            combine(playbackState, playWhenReady) { state, ready ->
                ready && state != STATE_ENDED
            }.stateIn(
                scope,
                SharingStarted.Lazily,
                initialState.third,
            )

        // Track service readiness changes in background.
        scope.launch {
            playerReadinessFlow.collect { ready ->
                isPlayerInitialized.value = ready
                if (ready) {
                    Timber.tag(TAG).d("Service player initialization detected by PlayerConnection")
                }
            }
        }

        Timber.tag(TAG).d("PlayerConnection state flows initialized successfully")
    }

    val isEffectivelyPlaying =
        combine(
            isPlaying,
            service.castConnectionHandler?.isCasting ?: MutableStateFlow(false),
            service.castConnectionHandler?.castIsPlaying ?: MutableStateFlow(false),
        ) { localPlaying, isCasting, castPlaying ->
            if (isCasting) castPlaying else localPlaying
        }.stateIn(
            scope,
            SharingStarted.Lazily,
            initialState.third,
        )

    val mediaMetadata = MutableStateFlow(getPlayerOrNull()?.currentMetadata)
    private var radioSongLookupJob: Job? = null
    private val radioSongCache = mutableMapOf<String, SongItem?>()
    /** Prevent repeated ICY/Media3 callbacks from reapplying the same radio song. */
    private var lastAppliedRadioMetadataKey: String? = null
    /** Reliable YouTube Music match for the current radio metadata. */
    val radioResolvedSong = MutableStateFlow<SongItem?>(null)
    /** True only when the stream or manual recognition supplied artist + title. */
    val radioHasTrackMetadata = MutableStateFlow(false)
    // stateIn so the latest DB result is cached and shared: on resume / re-subscription the value
    // is available immediately instead of re-running the Room query (which delayed now-playing
    // details, format and like-state on every foreground). Lazily keeps it hot across lifecycle
    // pauses, matching isPlaying above. StateFlow is still a Flow, so existing collectors are unaffected.
    val currentSong =
        mediaMetadata.flatMapLatest {
            database.song(it?.id)
        }.stateIn(scope, SharingStarted.Lazily, null)
    val resolvedRadioLibrarySong =
        radioResolvedSong.flatMapLatest { song ->
            database.song(song?.id)
        }.stateIn(scope, SharingStarted.Lazily, null)
    val currentLyrics =
        mediaMetadata.flatMapLatest { mediaMetadata ->
            database.lyrics(mediaMetadata?.id)
        }.stateIn(scope, SharingStarted.Lazily, null)
    val currentFormat =
        mediaMetadata.flatMapLatest { mediaMetadata ->
            database.format(mediaMetadata?.id)
        }.stateIn(scope, SharingStarted.Lazily, null)

    val queueTitle = MutableStateFlow<String?>(null)
    val queueWindows = MutableStateFlow<List<Timeline.Window>>(emptyList())
    val currentMediaItemIndex = MutableStateFlow(-1)
    val currentWindowIndex = MutableStateFlow(-1)

    val shuffleModeEnabled = MutableStateFlow(false)
    val repeatMode = MutableStateFlow(REPEAT_MODE_OFF)

    val canSkipPrevious = MutableStateFlow(true)
    val canSkipNext = MutableStateFlow(true)

    val error = MutableStateFlow<PlaybackException?>(null)
    val isMuted = service.isMuted
    val currentStreamClient = service.currentStreamClient

    val waitingForNetworkConnection = service.waitingForNetworkConnection

    // Callback to check if playback changes should be blocked (e.g., Listen Together guest)
    var shouldBlockPlaybackChanges: (() -> Boolean)? = null

    // Flag to allow internal sync operations to bypass blocking (set by ListenTogetherManager)
    @Volatile
    var allowInternalSync: Boolean = false

    var onSkipPrevious: (() -> Unit)? = null
    var onSkipNext: (() -> Unit)? = null

    var onUserSongSelection: (() -> Unit)? = null
    var onRadioArtistSelection: ((String) -> Unit)? = null
    var onRightPaneNavigation: ((String) -> Unit)? = null

    fun notifyUserSongSelection() {
        onUserSongSelection?.invoke()
    }

    fun requestRadioArtistNavigation(artistName: String): Boolean {
        val callback = onRadioArtistSelection ?: return false
        callback(artistName)
        return true
    }

    /** Route player-originated details into the embedded Dudu7 NavHost. */
    fun requestRightPaneNavigation(route: String): Boolean {
        val callback = onRightPaneNavigation ?: return false
        callback(route)
        return true
    }

    private var attachedPlayer: Player? = null

    init {
        scope.launch {
            service.playerFlow.collect { newPlayer ->
                if (newPlayer != null && newPlayer != attachedPlayer) {
                    updateAttachedPlayer(newPlayer)
                }
            }
        }
        val readyPlayer = getPlayerOrNull()
        if (attachedPlayer == null && readyPlayer != null) {
            updateAttachedPlayer(readyPlayer)
        }

        Timber.tag(TAG).d("PlayerConnection flow observer registered; playerReady=${playerReadinessFlow.value}")
    }

    private fun updateAttachedPlayer(newPlayer: Player) {
        attachedPlayer?.removeListener(this)
        attachedPlayer = newPlayer
        newPlayer.addListener(this)
        // Refresh all state from new player
        playbackState.value = newPlayer.playbackState
        playWhenReady.value = newPlayer.playWhenReady
        mediaMetadata.value = newPlayer.currentMetadata
        queueTitle.value = service.queueTitle
        queueWindows.value = newPlayer.getQueueWindows()
        currentWindowIndex.value = newPlayer.getCurrentQueueIndex()
        currentMediaItemIndex.value = newPlayer.currentMediaItemIndex
        shuffleModeEnabled.value = newPlayer.shuffleModeEnabled
        repeatMode.value = newPlayer.repeatMode
        Timber.tag(TAG).d("Attached to new player instance: $newPlayer")
    }

    fun playQueue(
        queue: Queue,
        notifyUserSelection: Boolean = true,
    ) {
        // Block if Listen Together guest (unless internal sync)
        if (!allowInternalSync && shouldBlockPlaybackChanges?.invoke() == true) {
            Timber.tag("PlayerConnection").d("playQueue blocked - Listen Together guest")
            return
        }
        if (!playerReadinessFlow.value) {
            Timber.tag(TAG).w("playQueue called before player ready; delegating to service")
        }
        if (!allowInternalSync && notifyUserSelection) {
            notifyUserSongSelection()
        }
        try {
            service.playQueue(queue)
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in playQueue")
            throw e
        }
    }

    fun startRadioSeamlessly() {
        // Block if Listen Together guest
        if (shouldBlockPlaybackChanges?.invoke() == true) {
            Timber.tag("PlayerConnection").d("startRadioSeamlessly blocked - Listen Together guest")
            return
        }
        if (!playerReadinessFlow.value) {
            Timber.tag(TAG).w("startRadioSeamlessly called before player ready; delegating to service")
        }
        try {
            service.startRadioSeamlessly()
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in startRadioSeamlessly")
            throw e
        }
    }

    fun playNext(item: MediaItem) = playNext(listOf(item))

    fun playNext(items: List<MediaItem>) {
        // Block if Listen Together guest (unless internal sync)
        if (!allowInternalSync && shouldBlockPlaybackChanges?.invoke() == true) {
            Timber.tag("PlayerConnection").d("playNext blocked - Listen Together guest")
            return
        }
        try {
            service.playNext(items)
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in playNext")
            throw e
        }
    }

    fun addToQueue(item: MediaItem) = addToQueue(listOf(item))

    fun addToQueue(items: List<MediaItem>) {
        // Block if Listen Together guest (unless internal sync)
        if (!allowInternalSync && shouldBlockPlaybackChanges?.invoke() == true) {
            Timber.tag("PlayerConnection").d("addToQueue blocked - Listen Together guest")
            return
        }
        try {
            service.addToQueue(items)
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in addToQueue")
            throw e
        }
    }

    fun toggleLike() {
        try {
            service.toggleLike()
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in toggleLike")
        }
    }

    fun toggleMute() {
        service.toggleMute()
    }

    fun setMuted(muted: Boolean) {
        service.setMuted(muted)
    }

    fun toggleLibrary() {
        try {
            service.toggleLibrary()
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in toggleLibrary")
        }
    }

    /**
     * Toggle play/pause - handles Cast when active
     */
    fun togglePlayPause() {
        if (!allowInternalSync && shouldBlockPlaybackChanges?.invoke() == true) return
        try {
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                if (castHandler.castIsPlaying.value) {
                    castHandler.pause()
                } else {
                    castHandler.play()
                }
            } else {
                player.togglePlayPause()
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in togglePlayPause")
        }
    }

    /**
     * Start playback - handles Cast when active
     */
    fun play() {
        try {
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                castHandler.play()
            } else {
                if (player.playbackState == Player.STATE_IDLE) {
                    player.prepare()
                }
                player.playWhenReady = true
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in play")
        }
    }

    /**
     * Pause playback - handles Cast when active
     */
    fun pause() {
        try {
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                castHandler.pause()
            } else {
                player.playWhenReady = false
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in pause")
        }
    }

    /**
     * Seek to position - handles Cast when active
     */
    fun seekTo(position: Long) {
        try {
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                castHandler.seekTo(position)
            } else {
                player.seekTo(position)
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in seekTo")
        }
    }

    fun seekToNext() {
        try {
            // When casting, use Cast skip instead of local player
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                castHandler.skipToNext()
                return
            }
            player.seekToNext()
            if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
                player.prepare()
            }
            player.playWhenReady = true
            onSkipNext?.invoke()
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in seekToNext")
        }
    }

    var onRestartSong: (() -> Unit)? = null

    fun seekToPrevious() {
        try {
            // When casting, use Cast skip instead of local player
            val castHandler = service.castConnectionHandler
            if (castHandler?.isCasting?.value == true) {
                castHandler.skipToPrevious()
                return
            }

            // A live radio stream has no meaningful "restart current item" position.
            // Previous must always select the previous saved station.
            if (isRadioMediaId(player.currentMediaItem?.mediaId) && player.hasPreviousMediaItem()) {
                player.seekToPreviousMediaItem()
                if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
                    player.prepare()
                }
                player.playWhenReady = true
                onSkipPrevious?.invoke()
                return
            }

            // Logic to mimic standard seekToPrevious behavior but with explicit callbacks
            // If we are more than 3 seconds in, just restart the song
            if (player.currentPosition > 3000 || !player.hasPreviousMediaItem()) {
                player.seekTo(0)
                if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
                    player.prepare()
                }
                player.playWhenReady = true
                onRestartSong?.invoke()
            } else {
                // Otherwise go to previous media item
                player.seekToPreviousMediaItem()
                if (player.playbackState == Player.STATE_IDLE || player.playbackState == Player.STATE_ENDED) {
                    player.prepare()
                }
                player.playWhenReady = true
                onSkipPrevious?.invoke()
            }
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error in seekToPrevious")
        }
    }

    /** Parses "0=09:00-23:00;1=22:00-06:00" into Map<dayIndex, Pair<start, end>>. */
    private fun parseDayTimes(raw: String): Map<Int, Pair<String, String>> {
        if (raw.isBlank()) return emptyMap()
        return raw
            .split(";")
            .mapNotNull { entry ->
                val parts = entry.split("=")
                if (parts.size != 2) return@mapNotNull null
                val dayIndex = parts[0].toIntOrNull() ?: return@mapNotNull null
                val times = parts[1].split("-")
                if (times.size != 2) return@mapNotNull null
                dayIndex to (times[0] to times[1])
            }.toMap()
    }

    private fun checkAndStartAutomaticSleepTimer(): Boolean {
        return try {
            val sleepTimerEnabled = service.applicationContext.dataStore.get(SleepTimerEnabledKey) ?: false
            Timber.tag(TAG).d("✓ Sleep Timer Check: enabled=$sleepTimerEnabled")

            if (!sleepTimerEnabled) {
                Timber.tag(TAG).d("✗ Sleep Timer disabled - skipping")
                return false
            }

            if (service.sleepTimer?.isActive == true) {
                Timber.tag(TAG).d("✗ Sleep Timer already active - skipping")
                return false
            }

            val sleepTimerRepeat = service.applicationContext.dataStore.get(SleepTimerRepeatKey) ?: "daily"
            val sleepTimerStartTime = service.applicationContext.dataStore.get(SleepTimerStartTimeKey) ?: "09:00"
            val sleepTimerEndTime = service.applicationContext.dataStore.get(SleepTimerEndTimeKey) ?: "23:00"
            val sleepTimerDefaultMinutes = (service.applicationContext.dataStore.get(SleepTimerDefaultKey) ?: 30f).roundToInt()
            val sleepTimerCustomDaysStr = service.applicationContext.dataStore.get(SleepTimerCustomDaysKey) ?: "0,1,2,3,4"
            val sleepTimerDayTimesStr = service.applicationContext.dataStore.get(SleepTimerDayTimesKey) ?: ""

            Timber
                .tag(
                    TAG,
                ).d(
                    "Sleep Timer Config: repeat=$sleepTimerRepeat start=$sleepTimerStartTime end=$sleepTimerEndTime default=$sleepTimerDefaultMinutes custom=$sleepTimerCustomDaysStr",
                )

            val currentTime = LocalTime.now()
            val today = LocalDate.now()
            val dayOfWeek = today.dayOfWeek.value % 7
            val adjustedDayOfWeek = if (dayOfWeek == 0) 6 else dayOfWeek - 1

            Timber.tag(TAG).d("Current: time=$currentTime dayOfWeek=$adjustedDayOfWeek")

            val isDayAllowed =
                when (sleepTimerRepeat) {
                    "daily" -> {
                        true
                    }

                    "weekdays" -> {
                        adjustedDayOfWeek in 0..4
                    }

                    "weekends" -> {
                        adjustedDayOfWeek in 5..6
                    }

                    "weekdays_weekends" -> {
                        true
                    }

                    // both groups active; per-day time handles the distinction
                    "custom" -> {
                        val customDays = sleepTimerCustomDaysStr.split(",").mapNotNull { it.trim().toIntOrNull() }
                        Timber.tag(TAG).d("Custom days: $customDays, adjustedDayOfWeek=$adjustedDayOfWeek")
                        adjustedDayOfWeek in customDays
                    }

                    else -> {
                        false
                    }
                }

            if (!isDayAllowed) {
                Timber.tag(TAG).d("✗ Day not allowed for Sleep Timer")
                return false
            }

// "daily" uses the single global time window.
// All other modes store per-day times in the dayTimes map so that
// e.g. weekdays and weekends can have different windows.
            val timeFormatter = DateTimeFormatter.ofPattern("HH:mm")
            val usesDayTimesMap = sleepTimerRepeat != "daily"
            val (startStr, endStr) =
                if (usesDayTimesMap) {
                    parseDayTimes(sleepTimerDayTimesStr)[adjustedDayOfWeek]
                        ?: (sleepTimerStartTime to sleepTimerEndTime)
                } else {
                    sleepTimerStartTime to sleepTimerEndTime
                }

            val startTime = LocalTime.parse(startStr, timeFormatter)
            val endTime = LocalTime.parse(endStr, timeFormatter)

            // Support overnight ranges (e.g. 22:00–06:00) in addition to normal ranges
            val isTimeInRange =
                if (endTime.isAfter(startTime)) {
                    currentTime.isAfter(startTime) && currentTime.isBefore(endTime)
                } else {
                    currentTime.isAfter(startTime) || currentTime.isBefore(endTime)
                }

            Timber.tag(TAG).d("Time check: $currentTime between $startStr-$endStr? $isTimeInRange")

            if (isTimeInRange) {
                Timber.tag(TAG).i("AUTO SLEEP TIMER STARTED: $sleepTimerDefaultMinutes minutes")
                service.sleepTimer?.start(sleepTimerDefaultMinutes)
                return true
            }

            Timber.tag(TAG).d("✗ Time not in range")
            return false
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Sleep Timer error")
            return false
        }
    }

    override fun onPlaybackStateChanged(state: Int) {
        playbackState.value = state
        error.value = player.playerError
    }

    override fun onPlayWhenReadyChanged(
        newPlayWhenReady: Boolean,
        reason: Int,
    ) {
        val wasPlaying = playWhenReady.value
        playWhenReady.value = newPlayWhenReady

        // Central sleep timer trigger: fires on every paused -> playing transition,
        if (newPlayWhenReady && !wasPlaying) {
            checkAndStartAutomaticSleepTimer()
        }
    }

    override fun onMediaItemTransition(
        mediaItem: MediaItem?,
        reason: Int,
    ) {
        radioSongLookupJob?.cancel()
        lastAppliedRadioMetadataKey = null
        radioResolvedSong.value = null
        radioHasTrackMetadata.value = false
        mediaMetadata.value = mediaItem?.metadata
        currentMediaItemIndex.value = player.currentMediaItemIndex
        currentWindowIndex.value = player.getCurrentQueueIndex()
        updateCanSkipPreviousAndNext()
    }

    override fun onMediaMetadataChanged(newMetadata: androidx.media3.common.MediaMetadata) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) {
            mediaMetadata.value = base
            return
        }

        val stationName =
            currentItem.mediaMetadata.extras?.getString("radio_name")
                ?.takeIf { it.isNotBlank() }
                ?: base.title
        val rawTitle =
            (newMetadata.title ?: newMetadata.displayTitle)
                ?.toString()
                ?.trim()
                .orEmpty()
                .takeUnless { it.equals(stationName, ignoreCase = true) || it.equals("WebRadio", ignoreCase = true) }
                .orEmpty()
        if (rawTitle.isNotBlank()) {
            applyRadioStreamTitle(rawTitle)
        }
    }

    override fun onMetadata(metadata: Metadata) {
        val streamTitle =
            metadata.getFirstEntryOfType(IcyInfo::class.java)
                ?.title
                ?.trim()
                .orEmpty()
        if (streamTitle.isNotBlank()) {
            applyRadioStreamTitle(streamTitle)
        }
    }

    private fun applyRadioStreamTitle(rawTitle: String) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) return

        val stationName =
            currentItem.mediaMetadata.extras?.getString("radio_name")
                ?.takeIf { it.isNotBlank() }
                ?: base.title
        val parsed = parseRadioStreamTitle(rawTitle)
        val metadataKey =
            "${base.id}|${normalizeTrackText(parsed.first.orEmpty())}|${normalizeTrackText(parsed.second)}"
        if (lastAppliedRadioMetadataKey == metadataKey) return
        lastAppliedRadioMetadataKey = metadataKey
        val dynamic =
            base.copy(
                title = parsed.second,
                artists =
                    listOf(
                        com.metrolist.music.models.MediaMetadata.Artist(
                            id = null,
                            name = parsed.first ?: stationName,
                        ),
                    ),
            )
        mediaMetadata.value = dynamic

        val artist = parsed.first
        val isClear = isClearRadioTrackMetadata(artist, parsed.second, stationName)
        radioHasTrackMetadata.value = isClear
        if (isClear) {
            lookupRadioSong(base, artist!!, parsed.second)
        } else {
            radioSongLookupJob?.cancel()
            radioResolvedSong.value = null
            Timber.tag(TAG).d("Skipping radio song lookup for ambiguous metadata: %s", rawTitle)
        }
    }

    /** Apply a manual Shazam result to the current radio item and resolve its YTM identity. */
    fun applyRecognizedRadioTrack(result: RecognitionResult) {
        val currentItem = getPlayerOrNull()?.currentMediaItem ?: return
        val base = currentItem.metadata ?: return
        if (!isRadioMediaId(base.id)) return
        val preferredCover = result.coverArtHqUrl ?: result.coverArtUrl
        lastAppliedRadioMetadataKey =
            "${base.id}|${normalizeTrackText(result.artist)}|${normalizeTrackText(result.title)}"
        mediaMetadata.value =
            base.copy(
                title = result.title,
                artists = listOf(com.metrolist.music.models.MediaMetadata.Artist(id = null, name = result.artist)),
                thumbnailUrl = preferredCover ?: base.thumbnailUrl,
            )
        radioHasTrackMetadata.value = result.artist.isNotBlank() && result.title.isNotBlank()
        if (radioHasTrackMetadata.value) {
            lookupRadioSong(base, result.artist, result.title, preferredCover)
        }
    }

    private fun parseRadioStreamTitle(raw: String): Pair<String?, String> {
        val cleaned = raw.substringBefore(" [").trim()
        val separator = listOf(" - ", " – ", " — ", " | ").firstOrNull { it in cleaned }
        if (separator == null) return null to cleaned
        val artist = cleaned.substringBefore(separator).trim().takeIf { it.isNotBlank() }
        val title = cleaned.substringAfter(separator).trim().ifBlank { cleaned }
        return artist to title
    }

    private fun isClearRadioTrackMetadata(
        artist: String?,
        title: String,
        stationName: String,
    ): Boolean {
        if (artist.isNullOrBlank() || title.isBlank()) return false
        val normalizedArtist = normalizeTrackText(artist)
        val normalizedTitle = normalizeTrackText(title)
        val normalizedStation = normalizeTrackText(stationName)
        if (normalizedArtist.length < 2 || normalizedTitle.length < 2) return false
        if (normalizedArtist == normalizedStation || normalizedTitle == normalizedStation) return false
        if ("http" in normalizedArtist || "http" in normalizedTitle || "www" in normalizedArtist || "www" in normalizedTitle) return false

        val generic =
            setOf(
                "radio",
                "webradio",
                "live",
                "stream",
                "unknown",
                "unbekannt",
                "station identification",
                "jingle",
                "promo",
                "advertisement",
                "commercial",
                "werbung",
                "news",
                "nachrichten",
            )
        return normalizedArtist !in generic && normalizedTitle !in generic
    }

    private fun normalizeTrackText(value: String): String =
        value
            .lowercase()
            .replace(
                Regex("""[\(\[][^(\[]*(official|music video|video|audio|lyrics?|remaster(?:ed)?|live)[^\)\]]*[\)\]]"""),
                " ",
            ).replace(Regex("""\b(feat|ft)\.?\b.*"""), " ")
            .replace(Regex("""[^\p{L}\p{N}]+"""), " ")
            .trim()
            .replace(Regex("""\s+"""), " ")

    private fun tokenCoverage(expected: String, actual: String): Double {
        if (expected.isBlank() || actual.isBlank()) return 0.0
        if (actual.contains(expected) || expected.contains(actual)) return 1.0
        val expectedTokens = expected.split(' ').filter { it.length > 1 }.toSet()
        val actualTokens = actual.split(' ').filter { it.length > 1 }.toSet()
        if (expectedTokens.isEmpty()) return 0.0
        return expectedTokens.intersect(actualTokens).size.toDouble() / expectedTokens.size
    }

    private fun isStrongRadioCoverMatch(
        song: SongItem,
        artist: String,
        title: String,
    ): Boolean {
        val expectedTitle = normalizeTrackText(title)
        val actualTitle = normalizeTrackText(song.title)
        val expectedArtist = normalizeTrackText(artist)
        val actualArtist = normalizeTrackText(song.artists.joinToString(" ") { it.name })
        return tokenCoverage(expectedTitle, actualTitle) >= 0.80 &&
            tokenCoverage(expectedArtist, actualArtist) >= 0.70
    }

    private fun lookupRadioSong(
        base: com.metrolist.music.models.MediaMetadata,
        artist: String,
        title: String,
        preferredCover: String? = null,
    ) {
        val key = "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        if (radioSongCache.containsKey(key)) {
            applyResolvedRadioSong(base, title, radioSongCache[key], preferredCover)
            return
        }

        radioSongLookupJob?.cancel()
        radioResolvedSong.value = null
        radioSongLookupJob =
            scope.launch {
                val song =
                    runCatching {
                        YouTube.search("$artist - $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { candidate -> isStrongRadioCoverMatch(candidate, artist, title) }
                    }.getOrNull()
                radioSongCache[key] = song
                applyResolvedRadioSong(base, title, song, preferredCover)
            }
    }

    private fun applyResolvedRadioSong(
        base: com.metrolist.music.models.MediaMetadata,
        expectedTitle: String,
        song: SongItem?,
        preferredCover: String?,
    ) {
        val current = mediaMetadata.value
        if (current?.id != base.id || current.title != expectedTitle) return
        radioResolvedSong.value = song
        val cover = preferredCover ?: song?.thumbnail?.resize(1200, 1200)
        if (song != null) {
            Timber.tag(TAG).d("Resolved radio song to YouTube Music: %s (%s)", song.title, song.id)
            mediaMetadata.value =
                current.copy(
                    title = song.title,
                    artists = song.artists.map { com.metrolist.music.models.MediaMetadata.Artist(it.id, it.name) },
                    thumbnailUrl = cover ?: current.thumbnailUrl,
                    album = song.album?.let { com.metrolist.music.models.MediaMetadata.Album(it.id, it.name) },
                )
        } else if (!cover.isNullOrBlank()) {
            mediaMetadata.value = current.copy(thumbnailUrl = cover)
        } else {
            Timber.tag(TAG).d("No sufficiently matching radio song for expected title %s", expectedTitle)
        }
    }

    override fun onTimelineChanged(
        timeline: Timeline,
        reason: Int,
    ) {
        queueWindows.value = player.getQueueWindows()
        queueTitle.value = service.queueTitle
        currentMediaItemIndex.value = player.currentMediaItemIndex
        currentWindowIndex.value = player.getCurrentQueueIndex()
        updateCanSkipPreviousAndNext()
    }

    override fun onShuffleModeEnabledChanged(enabled: Boolean) {
        shuffleModeEnabled.value = enabled
        queueWindows.value = player.getQueueWindows()
        currentWindowIndex.value = player.getCurrentQueueIndex()
        updateCanSkipPreviousAndNext()
    }

    override fun onRepeatModeChanged(mode: Int) {
        repeatMode.value = mode
        updateCanSkipPreviousAndNext()
    }

    override fun onPlayerErrorChanged(playbackError: PlaybackException?) {
        if (playbackError != null) {
            reportException(playbackError)
        }
        error.value = playbackError
    }

    private fun updateCanSkipPreviousAndNext() {
        if (!player.currentTimeline.isEmpty) {
            val window =
                player.currentTimeline.getWindow(player.currentMediaItemIndex, Timeline.Window())
            canSkipPrevious.value = player.isCommandAvailable(COMMAND_SEEK_IN_CURRENT_MEDIA_ITEM) ||
                !window.isLive ||
                player.isCommandAvailable(COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM)
            canSkipNext.value = window.isLive &&
                window.isDynamic ||
                player.isCommandAvailable(COMMAND_SEEK_TO_NEXT_MEDIA_ITEM)
        } else {
            canSkipPrevious.value = false
            canSkipNext.value = false
        }
    }

    fun dispose() {
        try {
            attachedPlayer?.removeListener(this)
            attachedPlayer = null
            Timber.tag(TAG).d("PlayerConnection disposed successfully")
        } catch (e: Exception) {
            Timber.tag(TAG).e(e, "Error during PlayerConnection disposal")
        }
    }
}
