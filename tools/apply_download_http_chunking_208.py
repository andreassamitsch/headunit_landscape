from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def write(path: str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print(f"updated {path}")


# Idempotency: the implementation workflow can be retriggered safely.
gradle_path = "app/build.gradle.kts"
gradle = Path(gradle_path).read_text(encoding="utf-8")
if 'versionCode = 1370092' in gradle and 'versionName = "13.7.83"' in gradle:
    print("13.7.83 already applied; nothing to do")
    raise SystemExit(0)

gradle = replace_once(gradle, "versionCode = 1370091", "versionCode = 1370092", "versionCode")
gradle = replace_once(gradle, 'versionName = "13.7.82"', 'versionName = "13.7.83"', "versionName")
write(gradle_path, gradle)


# ---------------------------------------------------------------------------
# Transparent Media3 upstream HTTP range chunker.
# ---------------------------------------------------------------------------
chunker = r'''package com.metrolist.music.playback

import android.net.Uri
import androidx.media3.common.C
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSpec
import androidx.media3.datasource.TransferListener
import java.io.EOFException
import java.io.IOException
import kotlin.math.min

/**
 * Transparently serves one logical Media3 DataSpec through consecutive bounded HTTP ranges.
 *
 * The DownloadManager/CacheDataSource still see one continuous resource. Only the network
 * upstream is reopened at bounded offsets, analogous to yt-dlp's http_chunk_size strategy.
 * Chunking is enabled by the caller per cache key and is abandoned safely when the server does
 * not confirm byte ranges on the first request.
 */
internal class HttpRangeChunkingDataSource(
    private val upstream: DataSource,
    private val chunkSizeBytes: Long,
    private val enabledForKey: (String?) -> Boolean,
    private val onChunkCompleted: (String?) -> Unit,
) : DataSource {
    private var originalSpec: DataSpec? = null
    private var mediaKey: String? = null
    private var chunkingEnabled = false
    private var upstreamOpened = false
    private var bytesReadTotal = 0L
    private var bytesReadInChunk = 0L
    private var currentChunkLength = 0L
    private var requestLength = C.LENGTH_UNSET
    private var sourceLength = C.LENGTH_UNSET
    private var currentChunkReported = false
    private var currentRange: ParsedHttpContentRange? = null

    override fun addTransferListener(transferListener: TransferListener) {
        upstream.addTransferListener(transferListener)
    }

    @Throws(IOException::class)
    override fun open(dataSpec: DataSpec): Long {
        resetState(dataSpec)
        chunkingEnabled = chunkSizeBytes > 0L && enabledForKey(mediaKey)
        if (!chunkingEnabled) {
            upstreamOpened = true
            return upstream.open(dataSpec)
        }

        openNextChunk(requireRange = false)
        val firstRange = currentRange
        if (firstRange == null || firstRange.start != dataSpec.position) {
            // A server that ignores Range could otherwise make subsequent chunks duplicate bytes.
            // Fall back to the untouched Media3 request before exposing any bytes to the caller.
            closeUpstreamQuietly()
            chunkingEnabled = false
            upstreamOpened = true
            return upstream.open(dataSpec)
        }

        sourceLength = firstRange.totalLength
        if (requestLength == C.LENGTH_UNSET && sourceLength != C.LENGTH_UNSET) {
            requestLength = (sourceLength - dataSpec.position).coerceAtLeast(0L)
        }
        return requestLength
    }

    @Throws(IOException::class)
    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        if (length == 0) return 0
        if (!chunkingEnabled) return upstream.read(buffer, offset, length)

        while (true) {
            if (currentChunkLength > 0L && bytesReadInChunk >= currentChunkLength) {
                reportCurrentChunkCompleted()
                if (!hasMoreBytes()) return C.RESULT_END_OF_INPUT
                openNextChunk(requireRange = true)
            }

            val read = upstream.read(buffer, offset, length)
            if (read > 0) {
                bytesReadTotal += read.toLong()
                bytesReadInChunk += read.toLong()
                if (currentChunkLength > 0L && bytesReadInChunk >= currentChunkLength) {
                    reportCurrentChunkCompleted()
                }
                return read
            }

            if (read == C.RESULT_END_OF_INPUT) {
                if (!hasMoreBytes()) return C.RESULT_END_OF_INPUT
                if (bytesReadInChunk < currentChunkLength) {
                    throw EOFException(
                        "HTTP range ended early at ${bytesReadInChunk}/${currentChunkLength} bytes",
                    )
                }
                openNextChunk(requireRange = true)
                continue
            }

            return read
        }
    }

    override fun getUri(): Uri? = upstream.uri

    override fun getResponseHeaders(): Map<String, List<String>> = upstream.responseHeaders

    @Throws(IOException::class)
    override fun close() {
        try {
            if (upstreamOpened) upstream.close()
        } finally {
            upstreamOpened = false
            originalSpec = null
            currentRange = null
        }
    }

    private fun resetState(dataSpec: DataSpec) {
        originalSpec = dataSpec
        mediaKey = dataSpec.key
        bytesReadTotal = 0L
        bytesReadInChunk = 0L
        currentChunkLength = 0L
        requestLength = dataSpec.length
        sourceLength = C.LENGTH_UNSET
        currentChunkReported = false
        currentRange = null
    }

    @Throws(IOException::class)
    private fun openNextChunk(requireRange: Boolean) {
        val base = originalSpec ?: throw IOException("Chunked data source is not open")
        closeUpstreamQuietly()

        val chunkLength = nextHttpChunkLength(requestLength, bytesReadTotal, chunkSizeBytes)
        if (chunkLength <= 0L) {
            currentChunkLength = 0L
            currentRange = null
            return
        }

        val chunkSpec = base.subrange(bytesReadTotal, chunkLength)
        upstreamOpened = true
        upstream.open(chunkSpec)
        bytesReadInChunk = 0L
        currentChunkReported = false

        val parsed = parseHttpContentRange(responseHeader("Content-Range"))
        if (parsed != null && parsed.start == chunkSpec.position) {
            currentRange = parsed
            currentChunkLength = parsed.length.coerceAtMost(chunkLength)
            if (parsed.totalLength != C.LENGTH_UNSET) sourceLength = parsed.totalLength
            if (requestLength == C.LENGTH_UNSET && sourceLength != C.LENGTH_UNSET) {
                requestLength = (sourceLength - base.position).coerceAtLeast(0L)
            }
        } else {
            currentRange = null
            currentChunkLength = chunkLength
            if (requireRange) {
                throw IOException(
                    "Server did not confirm requested byte range at position ${chunkSpec.position}",
                )
            }
        }
    }

    private fun responseHeader(name: String): String? =
        upstream.responseHeaders.entries
            .firstOrNull { (key, _) -> key.equals(name, ignoreCase = true) }
            ?.value
            ?.firstOrNull()

    private fun hasMoreBytes(): Boolean {
        if (requestLength != C.LENGTH_UNSET) return bytesReadTotal < requestLength
        if (sourceLength != C.LENGTH_UNSET) {
            val start = originalSpec?.position ?: 0L
            return start + bytesReadTotal < sourceLength
        }
        return false
    }

    private fun reportCurrentChunkCompleted() {
        if (!currentChunkReported && currentChunkLength > 0L && bytesReadInChunk >= currentChunkLength) {
            currentChunkReported = true
            onChunkCompleted(mediaKey)
        }
    }

    private fun closeUpstreamQuietly() {
        if (!upstreamOpened) return
        try {
            upstream.close()
        } catch (_: IOException) {
            // The next open/read surfaces the actionable network error. Closing is best effort.
        } finally {
            upstreamOpened = false
        }
    }

    class Factory(
        private val upstreamFactory: DataSource.Factory,
        private val chunkSizeBytes: Long,
        private val enabledForKey: (String?) -> Boolean,
        private val onChunkCompleted: (String?) -> Unit,
    ) : DataSource.Factory {
        override fun createDataSource(): DataSource =
            HttpRangeChunkingDataSource(
                upstream = upstreamFactory.createDataSource(),
                chunkSizeBytes = chunkSizeBytes,
                enabledForKey = enabledForKey,
                onChunkCompleted = onChunkCompleted,
            )
    }
}

internal data class ParsedHttpContentRange(
    val start: Long,
    val endInclusive: Long,
    val totalLength: Long,
) {
    val length: Long get() = endInclusive - start + 1L
}

internal fun parseHttpContentRange(value: String?): ParsedHttpContentRange? {
    val match = HTTP_CONTENT_RANGE.matchEntire(value?.trim().orEmpty()) ?: return null
    val start = match.groupValues[1].toLongOrNull() ?: return null
    val end = match.groupValues[2].toLongOrNull() ?: return null
    val total = match.groupValues[3].toLongOrNull() ?: return null
    if (start < 0L || end < start || total <= end) return null
    return ParsedHttpContentRange(start, end, total)
}

internal fun nextHttpChunkLength(requestLength: Long, bytesRead: Long, chunkSizeBytes: Long): Long {
    require(bytesRead >= 0L)
    require(chunkSizeBytes > 0L)
    if (requestLength == C.LENGTH_UNSET) return chunkSizeBytes
    return min(chunkSizeBytes, (requestLength - bytesRead).coerceAtLeast(0L))
}

private val HTTP_CONTENT_RANGE = Regex(
    """bytes\s+(\d+)-(\d+)/(\d+)""",
    RegexOption.IGNORE_CASE,
)
'''
write("app/src/main/kotlin/com/metrolist/music/playback/HttpRangeChunkingDataSource.kt", chunker)


# ---------------------------------------------------------------------------
# DownloadUtil wiring + diagnostics + A/B transfer toggle.
# ---------------------------------------------------------------------------
du_path = "app/src/main/kotlin/com/metrolist/music/playback/DownloadUtil.kt"
du = Path(du_path).read_text(encoding="utf-8")

du = replace_once(
    du,
    "import com.metrolist.innertube.strategy.ContentHints\nimport com.metrolist.music.constants.AudioQuality",
    "import com.metrolist.innertube.strategy.ContentHints\nimport com.metrolist.music.BuildConfig\nimport com.metrolist.music.constants.AudioQuality",
    "BuildConfig import",
)

du = replace_once(
    du,
    """    val validationResult: String,\n    val resolverRecoveryEvents: List<String> = emptyList(),\n)""",
    """    val validationResult: String,\n    val resolverRecoveryEvents: List<String> = emptyList(),\n    val httpChunkingEnabled: Boolean = false,\n    val httpChunkSizeBytes: Long = 0L,\n    val httpChunksCompleted: Int = 0,\n)""",
    "diagnostic chunk fields",
)

du = replace_once(
    du,
    """    private val diagnosticClientOverrides = ConcurrentHashMap<String, String>()\n    private val recoveryEvents = ConcurrentHashMap<String, ArrayDeque<String>>()""",
    """    private val diagnosticClientOverrides = ConcurrentHashMap<String, String>()\n    private val diagnosticHttpChunkingOverrides = ConcurrentHashMap<String, Boolean>()\n    private val httpChunksCompleted = ConcurrentHashMap<String, Int>()\n    private val recoveryEvents = ConcurrentHashMap<String, ArrayDeque<String>>()""",
    "chunking state maps",
)

du = replace_once(
    du,
    """                .setUpstreamDataSourceFactory(\n                    OkHttpDataSource.Factory(streamHttpClient),\n                ),""",
    """                .setUpstreamDataSourceFactory(\n                    HttpRangeChunkingDataSource.Factory(\n                        upstreamFactory = OkHttpDataSource.Factory(streamHttpClient),\n                        chunkSizeBytes = HTTP_DOWNLOAD_CHUNK_SIZE_BYTES,\n                        enabledForKey = { mediaId -> mediaId != null && isHttpChunkingEnabled(mediaId) },\n                        onChunkCompleted = { mediaId ->\n                            if (mediaId != null) recordHttpChunkCompleted(mediaId)\n                        },\n                    ),\n                ),""",
    "chunking datasource wiring",
)

du = replace_once(
    du,
    """                            validationResult = resolverSnapshot.validationResult,\n                            resolverRecoveryEvents = recoveryEventsFor(mediaId),\n                        ),""",
    """                            validationResult = resolverSnapshot.validationResult,\n                            resolverRecoveryEvents = recoveryEventsFor(mediaId),\n                            httpChunkingEnabled = isHttpChunkingEnabled(mediaId),\n                            httpChunkSizeBytes = if (isHttpChunkingEnabled(mediaId)) HTTP_DOWNLOAD_CHUNK_SIZE_BYTES else 0L,\n                            httpChunksCompleted = httpChunksCompleted[mediaId] ?: 0,\n                        ),""",
    "chunk diagnostics snapshot",
)

du = replace_once(
    du,
    """                        songUrlCache.invalidate(downloadId)\n                        diagnosticClientOverrides.remove(downloadId)\n                        recoveryEvents.remove(downloadId)\n                        resolverDiagnostics.update { it - downloadId }""",
    """                        songUrlCache.invalidate(downloadId)\n                        diagnosticClientOverrides.remove(downloadId)\n                        diagnosticHttpChunkingOverrides.remove(downloadId)\n                        httpChunksCompleted.remove(downloadId)\n                        recoveryEvents.remove(downloadId)\n                        resolverDiagnostics.update { it - downloadId }""",
    "remove chunk diagnostics",
)

du = replace_once(
    du,
    """    fun resetDiagnosticStreamClient(mediaId: String): Boolean {\n        val removed = diagnosticClientOverrides.remove(mediaId) ?: return false\n        recordResolverRecoveryEvent(mediaId, \"ab_override_reset:$removed\")\n        restartWithFreshResolver(mediaId)\n        return true\n    }\n\n    private fun restartWithFreshResolver(mediaId: String) {""",
    """    fun resetDiagnosticStreamClient(mediaId: String): Boolean {\n        val removed = diagnosticClientOverrides.remove(mediaId) ?: return false\n        recordResolverRecoveryEvent(mediaId, \"ab_override_reset:$removed\")\n        restartWithFreshResolver(mediaId)\n        return true\n    }\n\n    fun toggleDiagnosticHttpChunking(mediaId: String): Boolean {\n        val enabled = !isHttpChunkingEnabled(mediaId)\n        diagnosticHttpChunkingOverrides[mediaId] = enabled\n        httpChunksCompleted.remove(mediaId)\n        resolverDiagnostics.update { current ->\n            current[mediaId]?.let { existing ->\n                current + (\n                    mediaId to existing.copy(\n                        httpChunkingEnabled = enabled,\n                        httpChunkSizeBytes = if (enabled) HTTP_DOWNLOAD_CHUNK_SIZE_BYTES else 0L,\n                        httpChunksCompleted = 0,\n                    )\n                )\n            } ?: current\n        }\n        recordResolverRecoveryEvent(mediaId, \"http_chunking:${if (enabled) \"on\" else \"off\"}\")\n        restartHttpTransfer(mediaId)\n        return enabled\n    }\n\n    private fun isHttpChunkingEnabled(mediaId: String): Boolean =\n        BuildConfig.IS_DUDU7 && (diagnosticHttpChunkingOverrides[mediaId] ?: true)\n\n    private fun recordHttpChunkCompleted(mediaId: String) {\n        val count = httpChunksCompleted.compute(mediaId) { _, current -> (current ?: 0) + 1 } ?: 1\n        resolverDiagnostics.update { current ->\n            current[mediaId]?.let { existing ->\n                current + (mediaId to existing.copy(httpChunksCompleted = count))\n            } ?: current\n        }\n    }\n\n    private fun restartHttpTransfer(mediaId: String) {\n        scope.launch {\n            downloadManager.setStopReason(mediaId, DIAGNOSTIC_HTTP_CHUNK_SWITCH_STOP_REASON)\n            delay(300L)\n            downloadManager.setStopReason(mediaId, Download.STOP_REASON_NONE)\n        }\n    }\n\n    private fun restartWithFreshResolver(mediaId: String) {""",
    "chunk A/B controls",
)

du = replace_once(
    du,
    """private const val DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON = 8204\nprivate const val MAX_RECOVERY_EVENTS = 8""",
    """internal const val HTTP_DOWNLOAD_CHUNK_SIZE_BYTES = 10L * 1024L * 1024L\nprivate const val DIAGNOSTIC_CLIENT_SWITCH_STOP_REASON = 8204\nprivate const val DIAGNOSTIC_HTTP_CHUNK_SWITCH_STOP_REASON = 8208\nprivate const val MAX_RECOVERY_EVENTS = 8""",
    "chunk constants",
)
write(du_path, du)


# ---------------------------------------------------------------------------
# Queue UI: explicit HTTP A/B control and copyable transport diagnostics.
# ---------------------------------------------------------------------------
queue_path = "app/src/main/kotlin/com/metrolist/music/ui/screens/library/DownloadQueueScreen.kt"
queue = Path(queue_path).read_text(encoding="utf-8")

queue = replace_once(
    queue,
    """                Row(verticalAlignment = Alignment.CenterVertically) {\n                    if (\n                        BuildConfig.IS_DUDU7 &&\n                        resolverDiagnostics?.candidateClients?.distinct()?.size?.let { it > 1 } == true &&""",
    """                Row(verticalAlignment = Alignment.CenterVertically) {\n                    if (\n                        BuildConfig.IS_DUDU7 &&\n                        download.state != Download.STATE_COMPLETED &&\n                        download.state != Download.STATE_REMOVING\n                    ) {\n                        TextButton(\n                            onClick = {\n                                val enabled = downloadUtil.toggleDiagnosticHttpChunking(download.request.id)\n                                Toast.makeText(\n                                    context,\n                                    if (enabled) \"HTTP: 10 MiB Chunked\" else \"HTTP: Standard\",\n                                    Toast.LENGTH_SHORT,\n                                ).show()\n                                showDiagnostics = false\n                            },\n                        ) {\n                            Text(\"HTTP A/B\")\n                        }\n                    }\n                    if (\n                        BuildConfig.IS_DUDU7 &&\n                        resolverDiagnostics?.candidateClients?.distinct()?.size?.let { it > 1 } == true &&""",
    "HTTP A/B button",
)

queue = replace_once(
    queue,
    """        appendLine(\"failure_reason=${download.failureReason}\")\n        appendLine(\"stop_reason=${download.stopReason}\")\n        appendLine(\"stream_client=$streamClient\")""",
    """        appendLine(\"failure_reason=${download.failureReason}\")\n        appendLine(\"stop_reason=${download.stopReason}\")\n        appendLine(\"http_chunking=${resolverDiagnostics?.let { if (it.httpChunkingEnabled) \"on\" else \"off\" } ?: \"not_available\"}\")\n        appendLine(\"http_chunk_size_bytes=${resolverDiagnostics?.httpChunkSizeBytes ?: \"not_available\"}\")\n        appendLine(\"http_chunks_completed=${resolverDiagnostics?.httpChunksCompleted ?: \"not_available\"}\")\n        appendLine(\"stream_client=$streamClient\")""",
    "chunk diagnostic report lines",
)
write(queue_path, queue)


# ---------------------------------------------------------------------------
# Pure unit tests for bounded-range planning/parsing.
# ---------------------------------------------------------------------------
test = r'''package com.metrolist.music.playback

import androidx.media3.common.C
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HttpRangeChunkingDataSourceTest {
    @Test
    fun `youtube sized transfer is planned in ten MiB chunks`() {
        val chunk = 10L * 1024L * 1024L
        val total = 58_265_392L
        assertEquals(chunk, nextHttpChunkLength(total, 0L, chunk))
        assertEquals(chunk, nextHttpChunkLength(total, chunk, chunk))
        assertEquals(5_836_352L, nextHttpChunkLength(total, 5L * chunk, chunk))
        assertEquals(0L, nextHttpChunkLength(total, total, chunk))
    }

    @Test
    fun `unknown request length keeps bounded chunks`() {
        assertEquals(10L * 1024L * 1024L, nextHttpChunkLength(C.LENGTH_UNSET, 20L, 10L * 1024L * 1024L))
    }

    @Test
    fun `content range exposes absolute range and total`() {
        val parsed = parseHttpContentRange("bytes 10485760-20971519/58265392")
        assertEquals(10_485_760L, parsed?.start)
        assertEquals(20_971_519L, parsed?.endInclusive)
        assertEquals(58_265_392L, parsed?.totalLength)
        assertEquals(10_485_760L, parsed?.length)
    }

    @Test
    fun `malformed or unsafe content ranges are rejected`() {
        assertNull(parseHttpContentRange(null))
        assertNull(parseHttpContentRange("bytes */58265392"))
        assertNull(parseHttpContentRange("bytes 20-10/100"))
        assertNull(parseHttpContentRange("bytes 0-100/100"))
    }
}
'''
write("app/src/test/kotlin/com/metrolist/music/playback/HttpRangeChunkingDataSourceTest.kt", test)
