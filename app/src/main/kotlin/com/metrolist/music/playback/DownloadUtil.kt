/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.playback

import android.content.Context
import android.net.ConnectivityManager
import androidx.core.content.getSystemService
import androidx.core.net.toUri
import androidx.media3.database.DatabaseProvider
import androidx.media3.datasource.HttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.datasource.cache.Cache
import androidx.media3.datasource.cache.CacheDataSource
import androidx.media3.datasource.okhttp.OkHttpDataSource
import androidx.media3.exoplayer.offline.Download
import androidx.media3.exoplayer.offline.DownloadManager
import androidx.media3.exoplayer.offline.DownloadNotificationHelper
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.strategy.ContentHints
import com.metrolist.music.constants.AudioQuality
import com.metrolist.music.constants.AudioQualityKey
import com.metrolist.music.db.MusicDatabase
import com.metrolist.music.db.entities.FormatEntity
import com.metrolist.music.db.entities.SongEntity
import com.metrolist.music.di.DownloadCache
import com.metrolist.music.di.PlayerCache
import com.metrolist.music.utils.YTPlayerUtils
import com.metrolist.music.utils.enumPreference
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Runnable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import timber.log.Timber
import java.io.IOException
import java.time.LocalDateTime
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executor
import javax.inject.Inject
import javax.inject.Singleton

data class DownloadResolverDiagnostics(
    val resolvedAtMs: Long,
    val selectedClient: String,
    val selectedClientIndex: Int?,
    val preferredClient: String?,
    val candidateClients: List<String>,
    val itag: Int,
    val mimeType: String,
    val codec: String,
    val bitrate: Int,
    val contentLength: Long,
    val nParameterBeforeTransform: String,
    val nParameterAfterTransform: String,
    val nTransformRequired: Boolean,
    val nTransformAttempted: Boolean,
    val nTransformResult: String,
    val poTokenRequired: Boolean,
    val poTokenAvailable: Boolean,
    val poTokenAppended: Boolean,
    val signatureCipherPresent: Boolean,
    val validationResult: String,
    val resolverRecoveryEvents: List<String> = emptyList(),
)

@Singleton
class DownloadUtil
@Inject
constructor(
    @ApplicationContext context: Context,
    val database: MusicDatabase,
    val databaseProvider: DatabaseProvider,
    @DownloadCache val downloadCache: Cache,
    @PlayerCache val playerCache: Cache,
) {
    private val TAG = "DownloadUtil"
    private val connectivityManager = context.getSystemService<ConnectivityManager>()!!
    private val audioQuality by enumPreference(context, AudioQualityKey, AudioQuality.AUTO)
    private val songUrlCache = StreamUrlCache()
    private val diagnosticClientOverrides = ConcurrentHashMap<String, String>()
    private val recoveryEvents = ConcurrentHashMap<String, ArrayDeque<String>>()
    private val streamHttpClient =
        OkHttpClient.Builder()
            .proxy(YouTube.proxy)
            .proxyAuthenticator { _, response ->
                YouTube.proxyAuth?.let { auth ->
                    response.request.newBuilder()
                        .header("Proxy-Authorization", auth)
                        .build()
                } ?: response.request
            }
            .build()

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    val downloads = MutableStateFlow<Map<String, Download>>(emptyMap())
    val resolverDiagnostics = MutableStateFlow<Map<String, DownloadResolverDiagnostics>>(emptyMap())

    private val dataSourceFactory =
        ResolvingDataSource.Factory(
            CacheDataSource
                .Factory()
                .setCache(playerCache)
                // The DownloadManager writes the final bytes to downloadCache. Do not mirror all
                // network bytes into playerCache as well; this matches current MetroList upstream.
                .setCacheWriteDataSinkFactory(null)
                .setUpstreamDataSourceFactory(
                    OkHttpDataSource.Factory(streamHttpClient),
                ),
        ) { dataSpec ->
            val mediaId = dataSpec.key ?: error("No media id")
            val length = if (dataSpec.length >= 0) dataSpec.length else 1

            if (playerCache.isCached(mediaId, dataSpec.position, length)) {
                return@Factory dataSpec
            }

            songUrlCache[mediaId]?.let { cachedStream ->
                return@Factory dataSpec
                    .withUri(cachedStream.url.toUri())
                    .withRequestHeaders(dataSpec.httpRequestHeaders + cachedStream.requestHeaders)
            }
            val cacheGeneration = songUrlCache.generation(mediaId)

            val playbackData = runBlocking(Dispatchers.IO) {
                val song = database.songEntity(mediaId)
                YTPlayerUtils.playerResponseForPlayback(
                    mediaId,
                    audioQuality = audioQuality,
                    connectivityManager = connectivityManager,
                    contentHints = ContentHints(
                        isExplicit = song?.explicit,
                        isUploaded = song?.isUploaded,
                    ),
                    preferredStreamClient = diagnosticClientOverrides[mediaId],
                )
            }.getOrThrow()
            val format = playbackData.format

            // Avoid requesting the whole file merely to discover its size. Long-form Googlevideo
            // streams can be throttled when a very large range is forced into the URL. Probe one
            // byte instead and read the total from Content-Range, as current MetroList upstream does.
            val actualContentLength =
                format.contentLength?.takeIf { it > 0L } ?: run {
                    val request = okhttp3.Request.Builder()
                        .get()
                        .url(playbackData.streamUrl)
                        .apply {
                            playbackData.streamHeaders.forEach { (name, value) ->
                                header(name, value)
                            }
                        }
                        .header("Range", "bytes=0-0")
                        .build()
                    val probedLength =
                        try {
                            streamHttpClient.newCall(request).execute().use { response ->
                                downloadContentLength(
                                    statusCode = response.code,
                                    contentRange = response.header("Content-Range"),
                                    contentLength = response.header("Content-Length"),
                                )
                            }
                        } catch (_: IOException) {
                            null
                        }
                    probedLength ?: error("Failed to retrieve content length")
                }

            val resolverSnapshot = playbackData.resolverDiagnostics
            val codec = format.mimeType
                .substringAfter("codecs=", "unknown")
                .trim()
                .removeSurrounding("\"")
            recordResolverRecoveryEvent(mediaId, "resolved:${resolverSnapshot.selectedClient}")
            resolverDiagnostics.update { current ->
                current.toMutableMap().apply {
                    set(
                        mediaId,
                        DownloadResolverDiagnostics(
                            resolvedAtMs = System.currentTimeMillis(),
                            selectedClient = resolverSnapshot.selectedClient,
                            selectedClientIndex = resolverSnapshot.selectedClientIndex,
                            preferredClient = resolverSnapshot.preferredClient,
                            candidateClients = resolverSnapshot.candidateClients,
                            itag = format.itag,
                            mimeType = format.mimeType.substringBefore(';'),
                            codec = codec,
                            bitrate = format.bitrate,
                            contentLength = actualContentLength,
                            nParameterBeforeTransform = resolverSnapshot.nParameterBeforeTransform,
                            nParameterAfterTransform = resolverSnapshot.nParameterAfterTransform,
                            nTransformRequired = resolverSnapshot.nTransformRequired,
                            nTransformAttempted = resolverSnapshot.nTransformAttempted,
                            nTransformResult = resolverSnapshot.nTransformResult,
                            poTokenRequired = resolverSnapshot.poTokenRequired,
                            poTokenAvailable = resolverSnapshot.poTokenAvailable,
                            poTokenAppended = resolverSnapshot.poTokenAppended,
                            signatureCipherPresent = resolverSnapshot.signatureCipherPresent,
                            validationResult = resolverSnapshot.validationResult,
                            resolverRecoveryEvents = recoveryEventsFor(mediaId),
                        ),
                    )
                }
            }

            database.query {
                upsert(
                    FormatEntity(
                        id = mediaId,
                        itag = format.itag,
                        mimeType = format.mimeType.split(";")[0],
                        codecs = format.mimeType.split("codecs=")[1].removeSurrounding("\""),
                        bitrate = format.bitrate,
                        sampleRate = format.audioSampleRate,
                        contentLength = actualContentLength,
                        loudnessDb = playbackData.audioConfig?.loudnessDb,
                        perceptualLoudnessDb = playbackData.audioConfig?.perceptualLoudnessDb,
                        playbackUrl = playbackData.playbackTracking?.videostatsPlaybackUrl?.baseUrl
                    ),
                )

                // Metadata registration only — dateDownload is intentionally NOT set here.
                // It belongs solely to onDownloadChanged()'s STATE_COMPLETED branch below,
                // which only fires once the download has actually finished. Setting it here
                // (at URL-resolve time, i.e. the moment the download merely *starts*) would
                // mark the song as "cached" before a single byte is written.
                val existing = getSongByIdBlocking(mediaId)?.song
                val updatedSong = existing ?: SongEntity(
                    id = mediaId,
                    title = playbackData.videoDetails?.title ?: "Unknown",
                    duration = playbackData.videoDetails?.lengthSeconds?.toIntOrNull() ?: 0,
                    thumbnailUrl = playbackData.videoDetails?.thumbnail?.thumbnails?.lastOrNull()?.url,
                    dateDownload = null,
                    isDownloaded = false
                )

                upsert(updatedSong)
            }

            // Do not append `range=0-<entire file>` here. Media3 owns the request position/range,
            // allowing progressive downloads to resume normally without forcing Googlevideo to
            // serve one oversized URL range. This is the key upstream-aligned fix for #198.
            val streamUrl = playbackData.streamUrl

            songUrlCache.put(
                mediaId = mediaId,
                url = streamUrl,
                requestHeaders = playbackData.streamHeaders,
                clientName = playbackData.streamClient,
                expiresInSeconds = playbackData.streamExpiresInSeconds,
                expectedGeneration = cacheGeneration,
            )
            dataSpec
                .withUri(streamUrl.toUri())
                .withRequestHeaders(dataSpec.httpRequestHeaders + playbackData.streamHeaders)
        }

    val downloadNotificationHelper =
        DownloadNotificationHelper(context, ExoDownloadService.CHANNEL_ID)

    @OptIn(DelicateCoroutinesApi::class)
    val downloadManager: DownloadManager =
        DownloadManager(
            context,
            databaseProvider,
            downloadCache,
            dataSourceFactory,
            Executor(Runnable::run)
        ).apply {
            maxParallelDownloads = 3
            addListener(
                object : DownloadManager.Listener {
                    override fun onDownloadChanged(
                        downloadManager: DownloadManager,
                        download: Download,
                        finalException: Exception?,
                    ) {
                        if (download.state == Download.STATE_FAILED && finalException.isExpiredStreamError()) {
                            recordResolverRecoveryEvent(download.request.id, "media3_expired_stream_invalidated")
                            songUrlCache.invalidate(download.request.id)
                        }

                        downloads.update { map ->
                            map.toMutableMap().apply {
                                set(download.request.id, download)
                            }
                        }

                        scope.launch {
                            when (download.state) {
                                Download.STATE_COMPLETED -> {
                                    database.updateDownloadedInfo(download.request.id, true, LocalDateTime.now())
                                }
                                Download.STATE_FAILED,
                                Download.STATE_STOPPED,
                                Download.STATE_REMOVING -> {
                                    database.updateDownloadedInfo(download.request.id, false, null)
                                }
                                else -> {
                                }
                            }
                        }
                    }

                    override fun onDownloadRemoved(
                        downloadManager: DownloadManager,
                        download: Download,
                    ) {
                        val downloadId = download.request.id
                        songUrlCache.invalidate(downloadId)
                        diagnosticClientOverrides.remove(downloadId)
                        recoveryEvents.remove(downloadId)
                        resolverDiagnostics.update { it - downloadId }

                        runCatching {
                            database.updateDownloadedInfo(downloadId, false, null)
                        }.onSuccess {
                            downloads.update { map ->
                                map.toMutableMap().apply {
                                    remove(downloadId)
                                }
                            }
                            Timber.tag(TAG).d("Successfully removed download $downloadId from in-memory map")
                        }.onFailure { error ->
                            Timber.tag(TAG).e(error, "Failed to update database for removed download $downloadId, keeping in-memory entry")
                        }
                    }
                }
            )
        }

    init {
        val result = mutableMapOf<String, Download>()
        val cursor = downloadManager.downloadIndex.getDownloads()
        while (cursor.moveToNext()) {
            result[cursor.download.request.id] = cursor.download
        }
        downloads.value = result
    }

    fun getDownload(songId: String): Flow<Download?> = downloads.map { it[songId] }

    fun rotateDiagnosticStreamClient(mediaId: String): String? {
        val snapshot = resolverDiagnostics.value[mediaId] ?: return null
        val candidates = snapshot.candidateClients.distinct()
        if (candidates.size < 2) return null
        val current = diagnosticClientOverrides[mediaId] ?: snapshot.selectedClient
        val currentIndex = candidates.indexOf(current).takeIf { it >= 0 }
            ?: snapshot.selectedClientIndex?.takeIf { it in candidates.indices }
            ?: -1
        val next = candidates[(currentIndex + 1).mod(candidates.size)]
        diagnosticClientOverrides[mediaId] = next
        recordResolverRecoveryEvent(mediaId, "ab_override:$next")
        restartWithFreshResolver(mediaId)
        return next
    }

    fun resetDiagnosticStreamClient(mediaId: String): Boolean {
        val removed = diagnosticClientOverrides.remove(mediaId) ?: return false
        recordResolverRecoveryEvent(mediaId, "ab_override_reset:$removed")
        restartWithFreshResolver(mediaId)
        return true
    }

    private fun restartWithFreshResolver(mediaId: String) {
        songUrlCache.invalidate(mediaId)
        scope.launch {
            downloadManager.setStopReason(mediaId, DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON)
            delay(300L)
            downloadManager.setStopReason(mediaId, Download.STOP_REASON_NONE)
        }
    }

    private fun recordResolverRecoveryEvent(mediaId: String, event: String) {
        val events = recoveryEvents.computeIfAbsent(mediaId) { ArrayDeque() }
        val snapshot = synchronized(events) {
            events.addLast(event.take(80))
            while (events.size > MAX_RECOVERY_EVENTS) events.removeFirst()
            events.toList()
        }
        resolverDiagnostics.update { current ->
            current[mediaId]?.let { existing ->
                current + (mediaId to existing.copy(resolverRecoveryEvents = snapshot))
            } ?: current
        }
    }

    private fun recoveryEventsFor(mediaId: String): List<String> {
        val events = recoveryEvents[mediaId] ?: return emptyList()
        return synchronized(events) { events.toList() }
    }

    fun release() {
        scope.cancel()
    }

    private fun Throwable?.isExpiredStreamError(): Boolean {
        var current = this
        while (current != null) {
            if (current is HttpDataSource.InvalidResponseCodeException &&
                (current.responseCode == 403 || current.responseCode == 410 || current.responseCode == 416)
            ) {
                return true
            }
            current = current.cause
        }
        return false
    }
}

internal fun downloadContentLength(
    statusCode: Int,
    contentRange: String?,
    contentLength: String?,
): Long? {
    val rangePattern =
        when (statusCode) {
            206 -> PARTIAL_CONTENT_RANGE
            416 -> UNSATISFIED_CONTENT_RANGE
            else -> null
        }
    if (rangePattern != null) {
        return contentRange
            ?.trim()
            ?.let(rangePattern::matchEntire)
            ?.groupValues
            ?.get(1)
            ?.toLongOrNull()
            ?.takeIf { it > 0L }
    }
    return if (statusCode == 200) contentLength?.toLongOrNull()?.takeIf { it > 0L } else null
}

private const val DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON = 8204
private const val MAX_RECOVERY_EVENTS = 8

private val PARTIAL_CONTENT_RANGE = Regex("""bytes\s+0-0/(\d+)""", RegexOption.IGNORE_CASE)
private val UNSATISFIED_CONTENT_RANGE = Regex("""bytes\s+\*/(\d+)""", RegexOption.IGNORE_CASE)
