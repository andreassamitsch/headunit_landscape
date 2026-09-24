from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def write(path: str, text: str) -> None:
    p = Path(path)
    p.write_text(text, encoding="utf-8")
    print(f"updated {path}")


# ---------------------------------------------------------------------------
# 1) YTPlayerUtils: sanitized resolver snapshot + deterministic client priority
# ---------------------------------------------------------------------------
yt_path = "app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt"
yt = Path(yt_path).read_text(encoding="utf-8")

yt = replace_once(
    yt,
    '''    data class PlaybackData(\n        val audioConfig: PlayerResponse.PlayerConfig.AudioConfig?,\n        val videoDetails: PlayerResponse.VideoDetails?,\n        val playbackTracking: PlayerResponse.PlaybackTracking?,\n        val format: PlayerResponse.StreamingData.Format,\n        val streamUrl: String,\n        val streamExpiresInSeconds: Int,\n        val streamClient: String = "unknown",\n        val streamHeaders: Map<String, String> = emptyMap(),\n    )''',
    '''    data class ResolverDiagnostics(\n        val candidateClients: List<String> = emptyList(),\n        val selectedClient: String = "unknown",\n        val selectedClientIndex: Int? = null,\n        val preferredClient: String? = null,\n        val nParameterBeforeTransform: String = "unknown",\n        val nParameterAfterTransform: String = "unknown",\n        val nTransformRequired: Boolean = false,\n        val nTransformAttempted: Boolean = false,\n        val nTransformResult: String = "not_required",\n        val poTokenRequired: Boolean = false,\n        val poTokenAvailable: Boolean = false,\n        val poTokenAppended: Boolean = false,\n        val signatureCipherPresent: Boolean = false,\n        val validationResult: String = "not_run",\n    )\n\n    data class PlaybackData(\n        val audioConfig: PlayerResponse.PlayerConfig.AudioConfig?,\n        val videoDetails: PlayerResponse.VideoDetails?,\n        val playbackTracking: PlayerResponse.PlaybackTracking?,\n        val format: PlayerResponse.StreamingData.Format,\n        val streamUrl: String,\n        val streamExpiresInSeconds: Int,\n        val streamClient: String = "unknown",\n        val streamHeaders: Map<String, String> = emptyMap(),\n        val resolverDiagnostics: ResolverDiagnostics = ResolverDiagnostics(),\n    )''',
    "PlaybackData diagnostics",
)

yt = replace_once(
    yt,
    '''        connectivityManager: ConnectivityManager,\n        contentHints: ContentHints = ContentHints(),\n    ): Result<PlaybackData> = runCatching {''',
    '''        connectivityManager: ConnectivityManager,\n        contentHints: ContentHints = ContentHints(),\n        preferredStreamClient: String? = null,\n    ): Result<PlaybackData> = runCatching {''',
    "preferred stream client parameter",
)

yt = replace_once(
    yt,
    '''        val streamClients = fallbackStrategy.resolveClients(effectiveHints)''',
    '''        val baseStreamClients = fallbackStrategy.resolveClients(effectiveHints)\n        val streamClients = preferStreamClient(baseStreamClients, preferredStreamClient)\n        val candidateClientIds = streamClients.map { it.diagnosticId() }''',
    "client ordering",
)

yt = replace_once(
    yt,
    '''        var successClient: YouTubeClient? = null\n\n        val hasHighQuality''',
    '''        var successClient: YouTubeClient? = null\n        var selectedResolverDiagnostics: ResolverDiagnostics? = null\n        var bestFallbackDiagnostics: ResolverDiagnostics? = null\n\n        val hasHighQuality''',
    "resolver diagnostic state",
)

yt = replace_once(
    yt,
    '''        for ((clientIndex, client) in streamClients.withIndex()) {\n            // reset for each client\n            format = null\n            streamUrl = null\n            streamExpiresInSeconds = null''',
    '''        for ((clientIndex, client) in streamClients.withIndex()) {\n            // reset for each client\n            format = null\n            streamUrl = null\n            streamExpiresInSeconds = null\n            var currentResolverDiagnostics = ResolverDiagnostics(\n                candidateClients = candidateClientIds,\n                selectedClient = client.diagnosticId(),\n                selectedClientIndex = clientIndex,\n                preferredClient = preferredStreamClient,\n                poTokenAvailable = poToken?.streamingDataPoToken != null,\n            )''',
    "per-client diagnostic state",
)

yt = replace_once(
    yt,
    '''                Timber.tag(logTag).d("Format found: ${format.mimeType}, bitrate: ${format.bitrate}")\n\n                streamUrl = findUrlOrNull(format, videoId, responseToUse, skipNewPipe = wasOriginallyAgeRestricted)''',
    '''                Timber.tag(logTag).d("Format found: ${format.mimeType}, bitrate: ${format.bitrate}")\n                currentResolverDiagnostics = currentResolverDiagnostics.copy(\n                    signatureCipherPresent = !format.signatureCipher.isNullOrEmpty() || !format.cipher.isNullOrEmpty(),\n                )\n\n                streamUrl = findUrlOrNull(format, videoId, responseToUse, skipNewPipe = wasOriginallyAgeRestricted)''',
    "signature cipher diagnostic",
)

yt = replace_once(
    yt,
    '''                Timber.tag(TAG).d("N-transform decision:")\n                Timber.tag(TAG).d("  needsNTransform: $needsNTransform")\n                Timber.tag(TAG).d("  Reason: useWebPoTokens=${currentClient.useWebPoTokens}, " +\n                    "clientInList=${currentClient.clientName in listOf(\"WEB\", \"WEB_REMIX\", \"WEB_CREATOR\", \"TVHTML5\")}")\n\n                if (needsNTransform) {''',
    '''                Timber.tag(TAG).d("N-transform decision:")\n                Timber.tag(TAG).d("  needsNTransform: $needsNTransform")\n                Timber.tag(TAG).d("  Reason: useWebPoTokens=${currentClient.useWebPoTokens}, " +\n                    "clientInList=${currentClient.clientName in listOf(\"WEB\", \"WEB_REMIX\", \"WEB_CREATOR\", \"TVHTML5\")}")\n\n                val nBeforeTransform = runCatching {\n                    Uri.parse(streamUrl).getQueryParameter("n") != null\n                }.getOrDefault(false)\n                currentResolverDiagnostics = currentResolverDiagnostics.copy(\n                    nParameterBeforeTransform = if (nBeforeTransform) "present" else "absent",\n                    nParameterAfterTransform = if (nBeforeTransform) "present" else "absent",\n                    nTransformRequired = needsNTransform,\n                    nTransformAttempted = needsNTransform,\n                    poTokenRequired = currentClient.useWebPoTokens,\n                )\n\n                if (needsNTransform) {''',
    "n pre-transform diagnostics",
)

yt = replace_once(
    yt,
    '''                        Timber.tag(TAG).d("Applying n-transform to stream URL...")\n                        Timber.tag(TAG).d("  Original URL length: ${streamUrl.length}")\n                        Timber.tag(TAG).d("  Original URL preview: ${streamUrl.take(100)}...")\n\n                        val originalUrl = streamUrl\n                        // Use CipherDeobfuscator for n-transform (fixed implementation)\n                        streamUrl = CipherDeobfuscator.transformNParamInUrl(streamUrl)\n\n                        Timber.tag(TAG).d("  Transformed URL length: ${streamUrl.length}")\n                        Timber.tag(TAG).d("  URL changed: ${originalUrl != streamUrl}")''',
    '''                        Timber.tag(TAG).d("Applying n-transform to stream URL...")\n                        Timber.tag(TAG).d("  Original URL length: ${streamUrl.length}")\n                        Timber.tag(TAG).d("  Original URL n parameter present: $nBeforeTransform")\n\n                        val originalUrl = streamUrl\n                        // Use CipherDeobfuscator for n-transform (fixed implementation)\n                        streamUrl = CipherDeobfuscator.transformNParamInUrl(streamUrl)\n\n                        val nAfterTransform = runCatching {\n                            Uri.parse(streamUrl).getQueryParameter("n") != null\n                        }.getOrDefault(false)\n                        currentResolverDiagnostics = currentResolverDiagnostics.copy(\n                            nParameterAfterTransform = if (nAfterTransform) "present" else "absent",\n                            nTransformResult = if (originalUrl != streamUrl) "changed" else "unchanged",\n                        )\n                        Timber.tag(TAG).d("  Transformed URL length: ${streamUrl.length}")\n                        Timber.tag(TAG).d("  URL changed: ${originalUrl != streamUrl}")''',
    "n transform privacy and result",
)

yt = replace_once(
    yt,
    '''                        if (needsPoToken) {\n                            Timber.tag(TAG).d("Appending pot= parameter to stream URL")\n                            val separator = if ("?" in streamUrl) "&" else "?"\n                            streamUrl = "${streamUrl}${separator}pot=${Uri.encode(poToken.streamingDataPoToken)}"\n                            Timber.tag(TAG).d("  Final URL length (with pot): ${streamUrl.length}")\n                        }''',
    '''                        if (needsPoToken) {\n                            Timber.tag(TAG).d("Appending pot= parameter to stream URL")\n                            val separator = if ("?" in streamUrl) "&" else "?"\n                            streamUrl = "${streamUrl}${separator}pot=${Uri.encode(poToken.streamingDataPoToken)}"\n                            currentResolverDiagnostics = currentResolverDiagnostics.copy(poTokenAppended = true)\n                            Timber.tag(TAG).d("  Final URL length (with pot): ${streamUrl.length}")\n                        }''',
    "pot diagnostic",
)

yt = replace_once(
    yt,
    '''                    } catch (e: Exception) {\n                        Timber.tag(TAG).e(e, "N-transform or pot append failed: ${e.message}")\n                        Timber.tag(TAG).e("Stack trace: ${e.stackTraceToString().take(500)}")\n                        // Continue with original URL\n                    }\n                } else {\n                    Timber.tag(TAG).d("Skipping n-transform (not required for this client/content)")\n                }''',
    '''                    } catch (e: Exception) {\n                        currentResolverDiagnostics = currentResolverDiagnostics.copy(\n                            nTransformResult = "failed:${e::class.simpleName ?: "Exception"}",\n                        )\n                        Timber.tag(TAG).e("N-transform or pot append failed: ${e::class.simpleName ?: "Exception"}")\n                        // Continue with original URL without logging URL/token/signature values.\n                    }\n                } else {\n                    currentResolverDiagnostics = currentResolverDiagnostics.copy(nTransformResult = "not_required")\n                    Timber.tag(TAG).d("Skipping n-transform (not required for this client/content)")\n                }''',
    "n exception privacy",
)

yt = replace_once(
    yt,
    '''                        bestFallbackClient = currentClient\n                    }\n                    continue''',
    '''                        bestFallbackClient = currentClient\n                        bestFallbackDiagnostics = currentResolverDiagnostics.copy(\n                            validationResult = "quality_fallback_candidate",\n                        )\n                    }\n                    continue''',
    "quality fallback diagnostics",
)

yt = replace_once(
    yt,
    '''                    successClient = currentClient\n                    break\n                }\n\n                // WEB_REMIX authenticated CDN URLs''',
    '''                    successClient = currentClient\n                    selectedResolverDiagnostics = currentResolverDiagnostics.copy(\n                        validationResult = "skipped_last_client",\n                    )\n                    break\n                }\n\n                // WEB_REMIX authenticated CDN URLs''',
    "last client validation diagnostic",
)

yt = replace_once(
    yt,
    '''                    Timber.tag(TAG).i("Playback: client=${currentClient.clientName}, videoId=$videoId")\n                    successClient = currentClient\n                    break\n                }\n\n                if (validateStatus(streamUrl, currentClient.streamHeaders())) {''',
    '''                    Timber.tag(TAG).i("Playback: client=${currentClient.clientName}, videoId=$videoId")\n                    successClient = currentClient\n                    selectedResolverDiagnostics = currentResolverDiagnostics.copy(\n                        validationResult = "skipped_web_remix",\n                    )\n                    break\n                }\n\n                if (validateStatus(streamUrl, currentClient.streamHeaders())) {''',
    "web remix validation diagnostic",
)

yt = replace_once(
    yt,
    '''                    Timber.tag(TAG).i("Playback: client=${currentClient.clientName}, videoId=$videoId")\n                    successClient = currentClient\n                    break\n                } else {\n                    Timber.tag(logTag).d("Stream validation failed for client: ${currentClient.clientName}")''',
    '''                    Timber.tag(TAG).i("Playback: client=${currentClient.clientName}, videoId=$videoId")\n                    successClient = currentClient\n                    selectedResolverDiagnostics = currentResolverDiagnostics.copy(validationResult = "success")\n                    break\n                } else {\n                    currentResolverDiagnostics = currentResolverDiagnostics.copy(validationResult = "failed")\n                    Timber.tag(logTag).d("Stream validation failed for client: ${currentClient.clientName}")''',
    "validated stream diagnostic",
)

yt = replace_once(
    yt,
    '''            successClient = bestFallbackClient\n        }''',
    '''            successClient = bestFallbackClient\n            selectedResolverDiagnostics = bestFallbackDiagnostics\n        }''',
    "best fallback selection diagnostic",
)

yt = replace_once(
    yt,
    '''        if (isUploadedTrack) {\n            println("[PLAYBACK_DEBUG] SUCCESS: Got playback data for uploaded track - format=${format.mimeType}, streamUrl=${streamUrl.take(100)}...")\n        }\n        PlaybackData(''',
    '''        if (isUploadedTrack) {\n            println("[PLAYBACK_DEBUG] SUCCESS: Got playback data for uploaded track - format=${format.mimeType}, urlLength=${streamUrl.length}")\n        }\n        PlaybackData(''',
    "uploaded debug URL privacy",
)

yt = replace_once(
    yt,
    '''            streamClient = successClient?.clientName ?: "unknown",\n            streamHeaders = successClient?.streamHeaders().orEmpty(),\n        )''',
    '''            streamClient = successClient?.clientName ?: "unknown",\n            streamHeaders = successClient?.streamHeaders().orEmpty(),\n            resolverDiagnostics = selectedResolverDiagnostics ?: ResolverDiagnostics(\n                candidateClients = candidateClientIds,\n                selectedClient = successClient?.diagnosticId() ?: "unknown",\n                preferredClient = preferredStreamClient,\n                poTokenAvailable = poToken?.streamingDataPoToken != null,\n            ),\n        )''',
    "PlaybackData resolver snapshot",
)

yt = replace_once(
    yt,
    '''    }.onFailure { e ->\n        println("[PLAYBACK_DEBUG] EXCEPTION during playback for videoId=$videoId: ${e::class.simpleName}: ${e.message}")\n        e.printStackTrace()\n    }''',
    '''    }.onFailure { e ->\n        println("[PLAYBACK_DEBUG] EXCEPTION during playback for videoId=$videoId: ${e::class.simpleName}")\n    }''',
    "playback exception privacy",
)

yt = replace_once(
    yt,
    '''    private fun YouTubeClient.streamHeaders(): Map<String, String> =''',
    '''    private fun YouTubeClient.diagnosticId(): String {\n        val source = friendlyName?.takeIf { it.isNotBlank() }\n            ?: if (clientName == "ANDROID_VR") "${clientName}_${clientVersion}" else clientName\n        return source.replace(Regex("[^A-Za-z0-9_.-]"), "_").take(48)\n    }\n\n    private fun preferStreamClient(\n        clients: List<YouTubeClient>,\n        preferredClient: String?,\n    ): List<YouTubeClient> {\n        if (preferredClient.isNullOrBlank()) return clients\n        val preferredIndex = clients.indexOfFirst { it.diagnosticId() == preferredClient }\n        if (preferredIndex <= 0) return clients\n        return buildList {\n            add(clients[preferredIndex])\n            clients.forEachIndexed { index, client ->\n                if (index != preferredIndex) add(client)\n            }\n        }\n    }\n\n    private fun YouTubeClient.streamHeaders(): Map<String, String> =''',
    "client diagnostic helper",
)

if "streamUrl.take(" in yt or "Original URL preview" in yt:
    raise SystemExit("YTPlayerUtils still contains explicit stream URL preview logging")
write(yt_path, yt)


# ---------------------------------------------------------------------------
# 2) DownloadUtil: per-media resolver snapshot + in-memory A/B override
# ---------------------------------------------------------------------------
du_path = "app/src/main/kotlin/com/metrolist/music/playback/DownloadUtil.kt"
du = Path(du_path).read_text(encoding="utf-8")

du = replace_once(
    du,
    '''import kotlinx.coroutines.cancel\nimport kotlinx.coroutines.flow.Flow''',
    '''import kotlinx.coroutines.cancel\nimport kotlinx.coroutines.delay\nimport kotlinx.coroutines.flow.Flow''',
    "DownloadUtil delay import",
)
du = replace_once(
    du,
    '''import java.time.LocalDateTime\nimport java.util.concurrent.Executor''',
    '''import java.time.LocalDateTime\nimport java.util.concurrent.ConcurrentHashMap\nimport java.util.concurrent.Executor''',
    "DownloadUtil concurrent map import",
)
du = replace_once(
    du,
    '''@Singleton\nclass DownloadUtil''',
    '''data class DownloadResolverDiagnostics(\n    val resolvedAtMs: Long,\n    val selectedClient: String,\n    val selectedClientIndex: Int?,\n    val preferredClient: String?,\n    val candidateClients: List<String>,\n    val itag: Int,\n    val mimeType: String,\n    val codec: String,\n    val bitrate: Int,\n    val contentLength: Long,\n    val nParameterBeforeTransform: String,\n    val nParameterAfterTransform: String,\n    val nTransformRequired: Boolean,\n    val nTransformAttempted: Boolean,\n    val nTransformResult: String,\n    val poTokenRequired: Boolean,\n    val poTokenAvailable: Boolean,\n    val poTokenAppended: Boolean,\n    val signatureCipherPresent: Boolean,\n    val validationResult: String,\n    val resolverRecoveryEvents: List<String> = emptyList(),\n)\n\n@Singleton\nclass DownloadUtil''',
    "DownloadResolverDiagnostics data class",
)
du = replace_once(
    du,
    '''    private val audioQuality by enumPreference(context, AudioQualityKey, AudioQuality.AUTO)\n    private val songUrlCache = StreamUrlCache()''',
    '''    private val audioQuality by enumPreference(context, AudioQualityKey, AudioQuality.AUTO)\n    private val songUrlCache = StreamUrlCache()\n    private val diagnosticClientOverrides = ConcurrentHashMap<String, String>()\n    private val recoveryEvents = ConcurrentHashMap<String, ArrayDeque<String>>()''',
    "diagnostic maps",
)
du = replace_once(
    du,
    '''    val downloads = MutableStateFlow<Map<String, Download>>(emptyMap())''',
    '''    val downloads = MutableStateFlow<Map<String, Download>>(emptyMap())\n    val resolverDiagnostics = MutableStateFlow<Map<String, DownloadResolverDiagnostics>>(emptyMap())''',
    "resolver diagnostics flow",
)
du = replace_once(
    du,
    '''                    contentHints = ContentHints(\n                        isExplicit = song?.explicit,\n                        isUploaded = song?.isUploaded,\n                    ),\n                )''',
    '''                    contentHints = ContentHints(\n                        isExplicit = song?.explicit,\n                        isUploaded = song?.isUploaded,\n                    ),\n                    preferredStreamClient = diagnosticClientOverrides[mediaId],\n                )''',
    "pass preferred client",
)
du = replace_once(
    du,
    '''                    probedLength ?: error("Failed to retrieve content length")\n                }\n\n            database.query {''',
    '''                    probedLength ?: error("Failed to retrieve content length")\n                }\n\n            val resolverSnapshot = playbackData.resolverDiagnostics\n            val codec = format.mimeType\n                .substringAfter("codecs=", "unknown")\n                .trim()\n                .removeSurrounding("\\\"")\n            recordResolverRecoveryEvent(mediaId, "resolved:${resolverSnapshot.selectedClient}")\n            resolverDiagnostics.update { current ->\n                current.toMutableMap().apply {\n                    set(\n                        mediaId,\n                        DownloadResolverDiagnostics(\n                            resolvedAtMs = System.currentTimeMillis(),\n                            selectedClient = resolverSnapshot.selectedClient,\n                            selectedClientIndex = resolverSnapshot.selectedClientIndex,\n                            preferredClient = resolverSnapshot.preferredClient,\n                            candidateClients = resolverSnapshot.candidateClients,\n                            itag = format.itag,\n                            mimeType = format.mimeType.substringBefore(';'),\n                            codec = codec,\n                            bitrate = format.bitrate,\n                            contentLength = actualContentLength,\n                            nParameterBeforeTransform = resolverSnapshot.nParameterBeforeTransform,\n                            nParameterAfterTransform = resolverSnapshot.nParameterAfterTransform,\n                            nTransformRequired = resolverSnapshot.nTransformRequired,\n                            nTransformAttempted = resolverSnapshot.nTransformAttempted,\n                            nTransformResult = resolverSnapshot.nTransformResult,\n                            poTokenRequired = resolverSnapshot.poTokenRequired,\n                            poTokenAvailable = resolverSnapshot.poTokenAvailable,\n                            poTokenAppended = resolverSnapshot.poTokenAppended,\n                            signatureCipherPresent = resolverSnapshot.signatureCipherPresent,\n                            validationResult = resolverSnapshot.validationResult,\n                            resolverRecoveryEvents = recoveryEventsFor(mediaId),\n                        ),\n                    )\n                }\n            }\n\n            database.query {''',
    "store resolver snapshot",
)
du = replace_once(
    du,
    '''                        if (download.state == Download.STATE_FAILED && finalException.isExpiredStreamError()) {\n                            songUrlCache.invalidate(download.request.id)\n                        }''',
    '''                        if (download.state == Download.STATE_FAILED && finalException.isExpiredStreamError()) {\n                            recordResolverRecoveryEvent(download.request.id, "media3_expired_stream_invalidated")\n                            songUrlCache.invalidate(download.request.id)\n                        }''',
    "expired stream recovery event",
)
du = replace_once(
    du,
    '''                        val downloadId = download.request.id\n                        songUrlCache.invalidate(downloadId)''',
    '''                        val downloadId = download.request.id\n                        songUrlCache.invalidate(downloadId)\n                        diagnosticClientOverrides.remove(downloadId)\n                        recoveryEvents.remove(downloadId)\n                        resolverDiagnostics.update { it - downloadId }''',
    "cleanup diagnostics on removal",
)
du = replace_once(
    du,
    '''    fun getDownload(songId: String): Flow<Download?> = downloads.map { it[songId] }\n\n    fun release() {''',
    '''    fun getDownload(songId: String): Flow<Download?> = downloads.map { it[songId] }\n\n    fun rotateDiagnosticStreamClient(mediaId: String): String? {\n        val snapshot = resolverDiagnostics.value[mediaId] ?: return null\n        val candidates = snapshot.candidateClients.distinct()\n        if (candidates.size < 2) return null\n        val current = diagnosticClientOverrides[mediaId] ?: snapshot.selectedClient\n        val currentIndex = candidates.indexOf(current).takeIf { it >= 0 }\n            ?: snapshot.selectedClientIndex?.takeIf { it in candidates.indices }\n            ?: -1\n        val next = candidates[(currentIndex + 1).mod(candidates.size)]\n        diagnosticClientOverrides[mediaId] = next\n        recordResolverRecoveryEvent(mediaId, "ab_override:$next")\n        restartWithFreshResolver(mediaId)\n        return next\n    }\n\n    fun resetDiagnosticStreamClient(mediaId: String): Boolean {\n        val removed = diagnosticClientOverrides.remove(mediaId) ?: return false\n        recordResolverRecoveryEvent(mediaId, "ab_override_reset:$removed")\n        restartWithFreshResolver(mediaId)\n        return true\n    }\n\n    private fun restartWithFreshResolver(mediaId: String) {\n        songUrlCache.invalidate(mediaId)\n        scope.launch {\n            downloadManager.setStopReason(mediaId, DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON)\n            delay(300L)\n            downloadManager.setStopReason(mediaId, Download.STOP_REASON_NONE)\n        }\n    }\n\n    private fun recordResolverRecoveryEvent(mediaId: String, event: String) {\n        val events = recoveryEvents.computeIfAbsent(mediaId) { ArrayDeque() }\n        val snapshot = synchronized(events) {\n            events.addLast(event.take(80))\n            while (events.size > MAX_RECOVERY_EVENTS) events.removeFirst()\n            events.toList()\n        }\n        resolverDiagnostics.update { current ->\n            current[mediaId]?.let { existing ->\n                current + (mediaId to existing.copy(resolverRecoveryEvents = snapshot))\n            } ?: current\n        }\n    }\n\n    private fun recoveryEventsFor(mediaId: String): List<String> {\n        val events = recoveryEvents[mediaId] ?: return emptyList()\n        return synchronized(events) { events.toList() }\n    }\n\n    fun release() {''',
    "A/B diagnostic controls",
)
du = replace_once(
    du,
    '''private val PARTIAL_CONTENT_RANGE = Regex''',
    '''private const val DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON = 8204\nprivate const val MAX_RECOVERY_EVENTS = 8\n\nprivate val PARTIAL_CONTENT_RANGE = Regex''',
    "diagnostic constants",
)
write(du_path, du)


# ---------------------------------------------------------------------------
# 3) Download queue UI/report: merge Media3 rate with resolver snapshot + A/B
# ---------------------------------------------------------------------------
q_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/library/DownloadQueueScreen.kt"
q = Path(q_path).read_text(encoding="utf-8")
q = replace_once(
    q,
    '''import com.metrolist.music.playback.ExoDownloadService''',
    '''import com.metrolist.music.playback.DownloadResolverDiagnostics\nimport com.metrolist.music.playback.ExoDownloadService''',
    "queue diagnostic import",
)
q = replace_once(
    q,
    '''    val downloads by downloadUtil.downloads.collectAsStateWithLifecycle()''',
    '''    val downloads by downloadUtil.downloads.collectAsStateWithLifecycle()\n    val resolverDiagnostics by downloadUtil.resolverDiagnostics.collectAsStateWithLifecycle()''',
    "collect resolver diagnostics",
)
q = q.replace(
    '''                    download = download,\n                    notMetRequirements = notMetRequirements,''',
    '''                    download = download,\n                    resolverDiagnostics = resolverDiagnostics[download.request.id],\n                    notMetRequirements = notMetRequirements,''',
)
q = q.replace(
    '''                    download = download,\n                    notMetRequirements = 0,''',
    '''                    download = download,\n                    resolverDiagnostics = resolverDiagnostics[download.request.id],\n                    notMetRequirements = 0,''',
)
if q.count("resolverDiagnostics = resolverDiagnostics[download.request.id]") != 2:
    raise SystemExit("queue row resolver snapshot wiring failed")
q = replace_once(
    q,
    '''private fun DownloadQueueRow(\n    download: Download,\n    notMetRequirements: Int,''',
    '''private fun DownloadQueueRow(\n    download: Download,\n    resolverDiagnostics: DownloadResolverDiagnostics?,\n    notMetRequirements: Int,''',
    "row resolver parameter",
)
q = replace_once(
    q,
    '''    val context = LocalContext.current\n    val copiedMessage''',
    '''    val context = LocalContext.current\n    val downloadUtil = LocalDownloadUtil.current\n    val copiedMessage''',
    "row download util",
)
q = replace_once(
    q,
    '''                sampleWindowMs = sampleWindowMs,\n                nowMs = System.currentTimeMillis(),''',
    '''                sampleWindowMs = sampleWindowMs,\n                resolverDiagnostics = resolverDiagnostics,\n                nowMs = System.currentTimeMillis(),''',
    "report resolver argument",
)
q = replace_once(
    q,
    '''            confirmButton = {\n                TextButton(\n                    onClick = {\n                        copyDiagnosticReport(context, report)\n                        Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()\n                    },\n                ) {\n                    Text(stringResource(R.string.download_queue_diagnostics_copy))\n                }\n            },''',
    '''            confirmButton = {\n                Row(verticalAlignment = Alignment.CenterVertically) {\n                    if (\n                        BuildConfig.IS_DUDU7 &&\n                        resolverDiagnostics?.candidateClients?.distinct()?.size?.let { it > 1 } == true &&\n                        download.state != Download.STATE_COMPLETED &&\n                        download.state != Download.STATE_REMOVING\n                    ) {\n                        TextButton(\n                            onClick = {\n                                val next = downloadUtil.rotateDiagnosticStreamClient(download.request.id)\n                                if (next != null) {\n                                    Toast.makeText(context, "A/B: $next", Toast.LENGTH_SHORT).show()\n                                    showDiagnostics = false\n                                }\n                            },\n                        ) {\n                            Text("A/B")\n                        }\n                    }\n                    if (BuildConfig.IS_DUDU7 && resolverDiagnostics?.preferredClient != null) {\n                        TextButton(\n                            onClick = {\n                                if (downloadUtil.resetDiagnosticStreamClient(download.request.id)) {\n                                    Toast.makeText(context, "A/B: Standard", Toast.LENGTH_SHORT).show()\n                                    showDiagnostics = false\n                                }\n                            },\n                        ) {\n                            Text("Standard")\n                        }\n                    }\n                    TextButton(\n                        onClick = {\n                            copyDiagnosticReport(context, report)\n                            Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()\n                        },\n                    ) {\n                        Text(stringResource(R.string.download_queue_diagnostics_copy))\n                    }\n                }\n            },''',
    "A/B buttons",
)
q = replace_once(
    q,
    '''    sampledBytesPerSecond: Double?,\n    sampleWindowMs: Long?,\n    nowMs: Long,''',
    '''    sampledBytesPerSecond: Double?,\n    sampleWindowMs: Long?,\n    resolverDiagnostics: DownloadResolverDiagnostics?,\n    nowMs: Long,''',
    "report signature",
)
q = replace_once(
    q,
    '''    val mimeType = download.request.mimeType?.let(::sanitizeDiagnosticValue) ?: "not_available"\n    val streamClient = safeWhitelistedQueryValue(download, "c") ?: "not_available"\n    val itag = safeNumericQueryValue(download, "itag") ?: "not_available"\n    val nParameter = safeQueryParameterPresence(download, "n")''',
    '''    val mimeType = resolverDiagnostics?.mimeType?.let(::sanitizeDiagnosticValue) ?: "not_available"\n    val streamClient = resolverDiagnostics?.selectedClient?.let(::sanitizeDiagnosticValue) ?: "not_available"\n    val itag = resolverDiagnostics?.itag?.toString() ?: "not_available"\n    val nParameter = resolverDiagnostics?.nParameterAfterTransform ?: "not_available"''',
    "report resolver values",
)
q = replace_once(
    q,
    '''        appendLine("stream_client=$streamClient")\n        appendLine("itag=$itag")\n        appendLine("mime_type=$mimeType")\n        appendLine("codec=not_available")\n        appendLine("bitrate_bps=not_available")\n        appendLine("n_parameter=$nParameter")\n        appendLine("resolver_recovery_events=not_available_in_media3_download_snapshot")''',
    '''        appendLine("stream_client=$streamClient")\n        appendLine("stream_client_index=${resolverDiagnostics?.selectedClientIndex ?: "not_available"}")\n        appendLine("stream_client_override=${resolverDiagnostics?.preferredClient?.let(::sanitizeDiagnosticValue) ?: "default"}")\n        appendLine("stream_client_candidates=${resolverDiagnostics?.candidateClients?.joinToString(",") { sanitizeDiagnosticValue(it) } ?: "not_available"}")\n        appendLine("resolver_snapshot_age_ms=${resolverDiagnostics?.let { (nowMs - it.resolvedAtMs).coerceAtLeast(0L) } ?: "not_available"}")\n        appendLine("itag=$itag")\n        appendLine("mime_type=$mimeType")\n        appendLine("codec=${resolverDiagnostics?.codec?.let(::sanitizeDiagnosticValue) ?: "not_available"}")\n        appendLine("bitrate_bps=${resolverDiagnostics?.bitrate ?: "not_available"}")\n        appendLine("resolver_content_length_bytes=${resolverDiagnostics?.contentLength ?: "not_available"}")\n        appendLine("n_parameter=$nParameter")\n        appendLine("n_parameter_before_transform=${resolverDiagnostics?.nParameterBeforeTransform ?: "not_available"}")\n        appendLine("n_parameter_after_transform=${resolverDiagnostics?.nParameterAfterTransform ?: "not_available"}")\n        appendLine("n_transform_required=${resolverDiagnostics?.nTransformRequired ?: "not_available"}")\n        appendLine("n_transform_attempted=${resolverDiagnostics?.nTransformAttempted ?: "not_available"}")\n        appendLine("n_transform_result=${resolverDiagnostics?.nTransformResult?.let(::sanitizeDiagnosticValue) ?: "not_available"}")\n        appendLine("potoken_required=${resolverDiagnostics?.poTokenRequired ?: "not_available"}")\n        appendLine("potoken_available=${resolverDiagnostics?.poTokenAvailable ?: "not_available"}")\n        appendLine("potoken_appended=${resolverDiagnostics?.poTokenAppended ?: "not_available"}")\n        appendLine("signature_cipher_present=${resolverDiagnostics?.signatureCipherPresent ?: "not_available"}")\n        appendLine("stream_validation=${resolverDiagnostics?.validationResult?.let(::sanitizeDiagnosticValue) ?: "not_available"}")\n        appendLine("resolver_recovery_events=${resolverDiagnostics?.resolverRecoveryEvents?.joinToString(",") { sanitizeDiagnosticValue(it) }?.takeIf { it.isNotEmpty() } ?: "none"}")''',
    "expanded diagnostic report",
)
write(q_path, q)


# ---------------------------------------------------------------------------
# 4) Version bump
# ---------------------------------------------------------------------------
b_path = "app/build.gradle.kts"
b = Path(b_path).read_text(encoding="utf-8")
b = replace_once(b, "versionCode = 1370090", "versionCode = 1370091", "versionCode")
b = replace_once(b, 'versionName = "13.7.81"', 'versionName = "13.7.82"', "versionName")
write(b_path, b)


# ---------------------------------------------------------------------------
# 5) Build/publish workflow derived from the already proven 13.7.81 gate
# ---------------------------------------------------------------------------
old_wf = Path(".github/workflows/build-dudu7-13.7.81-download-diagnostics.yml").read_text(encoding="utf-8")
new_wf = old_wf
new_wf = new_wf.replace("13.7.81", "13.7.82")
new_wf = new_wf.replace("13-7-81", "13-7-82")
new_wf = new_wf.replace("1370090", "1370091")
new_wf = new_wf.replace("feature/download-diagnostics-201", "feature/download-resolver-diagnostics-204")
new_wf = new_wf.replace("fix/long-download-throttle-198", "feature/download-diagnostics-201")
new_wf = new_wf.replace("Issue 201 implementation boundaries", "Issues 201/203/204 implementation boundaries")
new_wf = new_wf.replace("Issue: #201 download diagnostics in progress queue", "Issues: #201 resolver diagnostics; #203 log privacy; #204 streamclient A/B")
new_wf = new_wf.replace("Known limitation: codec/bitrate/resolver recovery history are not retained by the Media3 Download snapshot and are reported as not_available", "Resolver snapshot: captured before Media3 handoff; A/B override is in-memory only and preserves Media3 download cache")
new_wf = new_wf.replace("Codec, Bitrate und Resolver-Recovery-Historie sind im Media3-Download-Snapshot nicht vorhanden und werden als `not_available` ausgewiesen.", "Resolver-Metadaten werden vor dem Media3-Handoff sanitisiert erfasst; der A/B-Override ist nur kurzlebig im Speicher und verändert die Standardauflösung ohne aktiven Test nicht.")
verify_anchor = "          grep -q 'privacy=stream URL, token, signature, cookie and authorization-header values are intentionally excluded' \"$QUEUE\"\n"
verify_extra = verify_anchor + "          grep -q 'n_parameter_before_transform=' \"$QUEUE\"\n          grep -q 'stream_client_candidates=' \"$QUEUE\"\n          grep -q 'potoken_available=' \"$QUEUE\"\n          grep -q 'stream_validation=' \"$QUEUE\"\n          grep -q 'rotateDiagnosticStreamClient' app/src/main/kotlin/com/metrolist/music/playback/DownloadUtil.kt\n          if grep -q 'streamUrl.take(' app/src/main/kotlin/com/metrolist/music/utils/YTPlayerUtils.kt; then\n            echo 'Unsafe stream URL preview remains in resolver logs' >&2\n            exit 1\n          fi\n"
if verify_anchor not in new_wf:
    raise SystemExit("workflow verification anchor not found")
new_wf = new_wf.replace(verify_anchor, verify_extra, 1)
new_wf = new_wf.replace("Base: feature/download-diagnostics-201 (13.7.80)", "Base: feature/download-diagnostics-201 (13.7.81)")
Path(".github/workflows/build-dudu7-13.7.82-resolver-diagnostics.yml").write_text(new_wf, encoding="utf-8")
print("created .github/workflows/build-dudu7-13.7.82-resolver-diagnostics.yml")

print("13.7.82 resolver diagnostics/A-B implementation patch completed")
