package com.metrolist.music.playback

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
    private var requestLength = C.LENGTH_UNSET.toLong()
    private var sourceLength = C.LENGTH_UNSET.toLong()
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
        if (requestLength == C.LENGTH_UNSET.toLong() && sourceLength != C.LENGTH_UNSET.toLong()) {
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
        sourceLength = C.LENGTH_UNSET.toLong()
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
            if (parsed.totalLength != C.LENGTH_UNSET.toLong()) sourceLength = parsed.totalLength
            if (requestLength == C.LENGTH_UNSET.toLong() && sourceLength != C.LENGTH_UNSET.toLong()) {
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
        if (requestLength != C.LENGTH_UNSET.toLong()) return bytesReadTotal < requestLength
        if (sourceLength != C.LENGTH_UNSET.toLong()) {
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
    if (requestLength == C.LENGTH_UNSET.toLong()) return chunkSizeBytes
    return min(chunkSizeBytes, (requestLength - bytesRead).coerceAtLeast(0L))
}

private val HTTP_CONTENT_RANGE = Regex(
    """bytes\s+(\d+)-(\d+)/(\d+)""",
    RegexOption.IGNORE_CASE,
)
