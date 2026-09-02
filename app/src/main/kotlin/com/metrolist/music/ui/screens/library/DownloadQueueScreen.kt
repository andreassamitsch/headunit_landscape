/*
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens.library

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.SystemClock
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.offline.Download
import androidx.media3.exoplayer.offline.DownloadService
import com.metrolist.music.BuildConfig
import com.metrolist.music.LocalDownloadUtil
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.R
import com.metrolist.music.playback.DownloadResolverDiagnostics
import com.metrolist.music.playback.ExoDownloadService
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.max
import kotlin.math.roundToInt

private const val PROGRESS_REFRESH_MS = 750L
private const val RECENT_COMPLETED_LIMIT = 5
private const val MIN_RATE_SAMPLE_MS = 250L
private val SAFE_DIAGNOSTIC_QUERY_VALUE = Regex("[A-Za-z0-9_.-]{1,32}")
private val DIAGNOSTIC_TIME_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss.SSS XXX")

@Composable
fun DownloadQueueScreen(onBack: () -> Unit) {
    BackHandler(onBack = onBack)

    val context = LocalContext.current
    val downloadUtil = LocalDownloadUtil.current
    val downloads by downloadUtil.downloads.collectAsStateWithLifecycle()
    val resolverDiagnostics by downloadUtil.resolverDiagnostics.collectAsStateWithLifecycle()

    val hasLiveDownloads = downloads.values.any {
        it.state == Download.STATE_QUEUED ||
            it.state == Download.STATE_DOWNLOADING ||
            it.state == Download.STATE_RESTARTING
    }

    var refreshTick by remember { mutableStateOf(0L) }
    LaunchedEffect(hasLiveDownloads) {
        if (!hasLiveDownloads) return@LaunchedEffect
        while (true) {
            delay(PROGRESS_REFRESH_MS)
            refreshTick++
        }
    }

    // Media3 owns the mutable DownloadProgress objects. refreshTick only asks Compose to
    // re-read their current values while work is active; it does not create a second state store.
    val snapshot = remember(downloads, refreshTick) { downloads.values.toList() }
    val notMetRequirements = downloadUtil.downloadManager.notMetRequirements

    val activeCount = snapshot.count { it.state == Download.STATE_DOWNLOADING }
    val waitingCount = snapshot.count {
        it.state == Download.STATE_QUEUED ||
            it.state == Download.STATE_RESTARTING ||
            it.state == Download.STATE_STOPPED
    }
    val failedCount = snapshot.count { it.state == Download.STATE_FAILED }

    val queueDownloads = remember(snapshot) {
        snapshot
            .filter { it.state != Download.STATE_COMPLETED }
            .sortedWith(
                compareBy<Download> { downloadPriority(it) }
                    .thenByDescending { it.updateTimeMs },
            )
    }
    val recentCompleted = remember(snapshot) {
        snapshot
            .filter { it.state == Download.STATE_COMPLETED }
            .sortedByDescending { it.updateTimeMs }
            .take(RECENT_COMPLETED_LIMIT)
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = LocalPlayerAwareWindowInsets.current.asPaddingValues(),
    ) {
        item(key = "download_queue_header") {
            Row(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                TextButton(
                    onClick = onBack,
                    modifier = Modifier.heightIn(min = 48.dp),
                ) {
                    Text(stringResource(R.string.download_queue_back))
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.download_queue_title),
                    style = MaterialTheme.typography.headlineSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }

        item(key = "download_queue_summary") {
            Column(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 8.dp),
            ) {
                Text(
                    text =
                        stringResource(
                            R.string.download_queue_summary,
                            activeCount,
                            waitingCount,
                            failedCount,
                        ),
                    style = MaterialTheme.typography.titleMedium,
                )
                if (notMetRequirements != 0 && waitingCount > 0) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        text = stringResource(R.string.download_queue_waiting_requirements),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
        }

        if (queueDownloads.isEmpty()) {
            item(key = "download_queue_empty") {
                Text(
                    text = stringResource(R.string.download_queue_empty),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 24.dp),
                )
            }
        } else {
            items(
                items = queueDownloads,
                key = { "download_queue_${it.request.id}" },
            ) { download ->
                DownloadQueueRow(
                    download = download,
                    resolverDiagnostics = resolverDiagnostics[download.request.id],
                    notMetRequirements = notMetRequirements,
                    refreshToken = refreshTick,
                    onRetry = {
                        DownloadService.sendAddDownload(
                            context,
                            ExoDownloadService::class.java,
                            download.request,
                            false,
                        )
                    },
                    onResume = {
                        DownloadService.sendSetStopReason(
                            context,
                            ExoDownloadService::class.java,
                            download.request.id,
                            Download.STOP_REASON_NONE,
                            false,
                        )
                    },
                    onCancel = {
                        DownloadService.sendRemoveDownload(
                            context,
                            ExoDownloadService::class.java,
                            download.request.id,
                            false,
                        )
                    },
                )
                HorizontalDivider()
            }
        }

        if (recentCompleted.isNotEmpty()) {
            item(key = "download_queue_recent_header") {
                Text(
                    text = stringResource(R.string.download_queue_recently_completed),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(start = 20.dp, end = 20.dp, top = 24.dp, bottom = 8.dp),
                )
            }
            items(
                items = recentCompleted,
                key = { "download_queue_completed_${it.request.id}" },
            ) { download ->
                DownloadQueueRow(
                    download = download,
                    resolverDiagnostics = resolverDiagnostics[download.request.id],
                    notMetRequirements = 0,
                    refreshToken = refreshTick,
                    onRetry = {},
                    onResume = {},
                    onCancel = {},
                )
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun DownloadQueueRow(
    download: Download,
    resolverDiagnostics: DownloadResolverDiagnostics?,
    notMetRequirements: Int,
    refreshToken: Long,
    onRetry: () -> Unit,
    onResume: () -> Unit,
    onCancel: () -> Unit,
) {
    // Reading refreshToken makes progress-only Media3 changes observable to this row.
    @Suppress("UNUSED_VARIABLE")
    val progressRefresh = refreshToken

    val context = LocalContext.current
    val downloadUtil = LocalDownloadUtil.current
    val copiedMessage = stringResource(R.string.download_queue_diagnostics_copied)
    var showDiagnostics by remember(download.request.id) { mutableStateOf(false) }

    val title = remember(download.request.id, download.request.data.contentHashCode()) {
        if (download.request.data.isNotEmpty()) {
            Util.fromUtf8Bytes(download.request.data)
        } else {
            download.request.id
        }
    }
    val percent = download.percentDownloaded
    val bytesDownloaded = download.bytesDownloaded.coerceAtLeast(0L)

    var previousSampleBytes by remember(download.request.id) { mutableStateOf(bytesDownloaded) }
    var previousSampleElapsedMs by remember(download.request.id) { mutableStateOf(SystemClock.elapsedRealtime()) }
    var sampledBytesPerSecond by remember(download.request.id) { mutableStateOf<Double?>(null) }
    var sampleWindowMs by remember(download.request.id) { mutableStateOf<Long?>(null) }

    LaunchedEffect(refreshToken, download.request.id, download.state) {
        val nowElapsedMs = SystemClock.elapsedRealtime()
        val elapsedMs = nowElapsedMs - previousSampleElapsedMs
        val deltaBytes = bytesDownloaded - previousSampleBytes
        sampledBytesPerSecond =
            if (
                download.state == Download.STATE_DOWNLOADING &&
                elapsedMs >= MIN_RATE_SAMPLE_MS &&
                deltaBytes >= 0L
            ) {
                deltaBytes * 1000.0 / elapsedMs
            } else {
                null
            }
        sampleWindowMs = if (sampledBytesPerSecond != null) elapsedMs else null
        previousSampleBytes = bytesDownloaded
        previousSampleElapsedMs = nowElapsedMs
    }

    val status =
        when (download.state) {
            Download.STATE_DOWNLOADING -> stringResource(R.string.download_queue_status_downloading)
            Download.STATE_QUEUED -> {
                if (notMetRequirements != 0) {
                    stringResource(R.string.download_queue_waiting_requirements)
                } else {
                    stringResource(R.string.download_queue_status_waiting)
                }
            }
            Download.STATE_RESTARTING -> stringResource(R.string.download_queue_status_restarting)
            Download.STATE_STOPPED -> stringResource(R.string.download_queue_status_stopped)
            Download.STATE_FAILED -> stringResource(R.string.download_queue_status_failed)
            Download.STATE_REMOVING -> stringResource(R.string.download_queue_status_removing)
            Download.STATE_COMPLETED -> stringResource(R.string.download_queue_status_completed)
            else -> stringResource(R.string.download_queue_status_unknown)
        }

    val progressText =
        if (percent >= 0f && download.state != Download.STATE_COMPLETED) {
            stringResource(
                R.string.download_queue_progress,
                percent.roundToInt().coerceIn(0, 100),
                formatBytes(bytesDownloaded),
            )
        } else if (bytesDownloaded > 0L && download.state != Download.STATE_COMPLETED) {
            stringResource(R.string.download_queue_bytes_downloaded, formatBytes(bytesDownloaded))
        } else {
            null
        }

    if (showDiagnostics) {
        val report =
            buildDownloadDiagnosticReport(
                download = download,
                title = title,
                notMetRequirements = notMetRequirements,
                sampledBytesPerSecond = sampledBytesPerSecond,
                sampleWindowMs = sampleWindowMs,
                resolverDiagnostics = resolverDiagnostics,
                nowMs = System.currentTimeMillis(),
            )
        AlertDialog(
            onDismissRequest = { showDiagnostics = false },
            title = { Text(stringResource(R.string.download_queue_diagnostics_title)) },
            text = {
                Text(
                    text = report,
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                    modifier =
                        Modifier
                            .fillMaxWidth()
                            .heightIn(max = 440.dp)
                            .verticalScroll(rememberScrollState()),
                )
            },
            confirmButton = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (
                        BuildConfig.IS_DUDU7 &&
                        resolverDiagnostics?.candidateClients?.distinct()?.size?.let { it > 1 } == true &&
                        download.state != Download.STATE_COMPLETED &&
                        download.state != Download.STATE_REMOVING
                    ) {
                        TextButton(
                            onClick = {
                                val next = downloadUtil.rotateDiagnosticStreamClient(download.request.id)
                                if (next != null) {
                                    Toast.makeText(context, "A/B: $next", Toast.LENGTH_SHORT).show()
                                    showDiagnostics = false
                                }
                            },
                        ) {
                            Text("A/B")
                        }
                    }
                    if (BuildConfig.IS_DUDU7 && resolverDiagnostics?.preferredClient != null) {
                        TextButton(
                            onClick = {
                                if (downloadUtil.resetDiagnosticStreamClient(download.request.id)) {
                                    Toast.makeText(context, "A/B: Standard", Toast.LENGTH_SHORT).show()
                                    showDiagnostics = false
                                }
                            },
                        ) {
                            Text("Standard")
                        }
                    }
                    TextButton(
                        onClick = {
                            copyDiagnosticReport(context, report)
                            Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
                        },
                    ) {
                        Text(stringResource(R.string.download_queue_diagnostics_copy))
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { showDiagnostics = false }) {
                    Text(stringResource(R.string.download_queue_diagnostics_close))
                }
            },
        )
    }

    ListItem(
        modifier =
            Modifier
                .fillMaxWidth()
                .heightIn(min = 88.dp),
        headlineContent = {
            Text(
                text = title,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        },
        supportingContent = {
            Column(modifier = Modifier.padding(top = 2.dp)) {
                Text(
                    text = status,
                    color =
                        when (download.state) {
                            Download.STATE_FAILED -> MaterialTheme.colorScheme.error
                            Download.STATE_DOWNLOADING -> MaterialTheme.colorScheme.primary
                            else -> MaterialTheme.colorScheme.onSurfaceVariant
                        },
                )
                progressText?.let {
                    Text(
                        text = it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (download.state == Download.STATE_DOWNLOADING && sampledBytesPerSecond != null) {
                    Text(
                        text =
                            stringResource(
                                R.string.download_queue_current_rate,
                                sampledBytesPerSecond!! / 1_000_000.0,
                            ),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (
                    download.state == Download.STATE_DOWNLOADING ||
                    download.state == Download.STATE_QUEUED ||
                    download.state == Download.STATE_RESTARTING
                ) {
                    Spacer(Modifier.height(6.dp))
                    if (percent >= 0f) {
                        LinearProgressIndicator(
                            progress = { (percent / 100f).coerceIn(0f, 1f) },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    } else {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        },
        trailingContent = {
            Column(horizontalAlignment = Alignment.End) {
                TextButton(
                    onClick = { showDiagnostics = true },
                    modifier = Modifier.heightIn(min = 44.dp),
                ) {
                    Text(stringResource(R.string.download_queue_diagnostics))
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    when (download.state) {
                        Download.STATE_FAILED -> {
                            TextButton(
                                onClick = onRetry,
                                modifier = Modifier.heightIn(min = 48.dp),
                            ) {
                                Text(stringResource(R.string.download_queue_retry))
                            }
                        }
                        Download.STATE_STOPPED -> {
                            TextButton(
                                onClick = onResume,
                                modifier = Modifier.heightIn(min = 48.dp),
                            ) {
                                Text(stringResource(R.string.download_queue_resume))
                            }
                        }
                    }

                    if (
                        download.state == Download.STATE_QUEUED ||
                        download.state == Download.STATE_DOWNLOADING ||
                        download.state == Download.STATE_RESTARTING ||
                        download.state == Download.STATE_STOPPED ||
                        download.state == Download.STATE_FAILED
                    ) {
                        TextButton(
                            onClick = onCancel,
                            modifier = Modifier.heightIn(min = 48.dp),
                        ) {
                            Text(stringResource(R.string.download_queue_cancel))
                        }
                    }
                }
            }
        },
    )
}

private fun buildDownloadDiagnosticReport(
    download: Download,
    title: String,
    notMetRequirements: Int,
    sampledBytesPerSecond: Double?,
    sampleWindowMs: Long?,
    resolverDiagnostics: DownloadResolverDiagnostics?,
    nowMs: Long,
): String {
    val bytesDownloaded = download.bytesDownloaded.coerceAtLeast(0L)
    val endTimeMs =
        if (
            download.state == Download.STATE_COMPLETED ||
            download.state == Download.STATE_FAILED ||
            download.state == Download.STATE_STOPPED
        ) {
            max(download.updateTimeMs, download.startTimeMs)
        } else {
            nowMs
        }
    val lifetimeElapsedMs = (endTimeMs - download.startTimeMs).coerceAtLeast(0L)
    val lifetimeBytesPerSecond =
        if (bytesDownloaded > 0L && lifetimeElapsedMs > 0L) {
            bytesDownloaded * 1000.0 / lifetimeElapsedMs
        } else {
            null
        }
    val contentLength = download.contentLength.takeIf { it > 0L }
    val progress = download.percentDownloaded.takeIf { it >= 0f && it.isFinite() }
    val mimeType = resolverDiagnostics?.mimeType?.let(::sanitizeDiagnosticValue) ?: "not_available"
    val streamClient = resolverDiagnostics?.selectedClient?.let(::sanitizeDiagnosticValue) ?: "not_available"
    val itag = resolverDiagnostics?.itag?.toString() ?: "not_available"
    val nParameter = resolverDiagnostics?.nParameterAfterTransform ?: "not_available"

    return buildString {
        appendLine("MetroList dudu7 download diagnostics")
        appendLine("app_version_name=${sanitizeDiagnosticValue(BuildConfig.VERSION_NAME)}")
        appendLine("app_version_code=${BuildConfig.VERSION_CODE}")
        appendLine(
            "timestamp=${DIAGNOSTIC_TIME_FORMATTER.format(Instant.ofEpochMilli(nowMs).atZone(ZoneId.systemDefault()))}",
        )
        appendLine("media_id=${sanitizeDiagnosticValue(download.request.id)}")
        appendLine("title=${sanitizeDiagnosticValue(title)}")
        appendLine("state=${downloadStateName(download.state)}")
        appendLine("progress_percent=${progress?.let { String.format(Locale.US, "%.1f", it) } ?: "not_available"}")
        appendLine("bytes_downloaded=$bytesDownloaded")
        appendLine("content_length_bytes=${contentLength ?: "not_available"}")
        appendLine("start_time_ms=${download.startTimeMs}")
        appendLine("update_time_ms=${download.updateTimeMs}")
        appendLine("lifetime_elapsed_ms=$lifetimeElapsedMs")
        appendLine("current_rate_MBps=${formatRateMBps(sampledBytesPerSecond)}")
        appendLine("current_rate_Mbps=${formatRateMbps(sampledBytesPerSecond)}")
        appendLine("current_rate_sample_window_ms=${sampleWindowMs ?: "not_available"}")
        appendLine("lifetime_average_MBps=${formatRateMBps(lifetimeBytesPerSecond)}")
        appendLine("not_met_requirements=$notMetRequirements")
        appendLine("failure_reason=${download.failureReason}")
        appendLine("stop_reason=${download.stopReason}")
        appendLine("stream_client=$streamClient")
        appendLine("stream_client_index=${resolverDiagnostics?.selectedClientIndex ?: "not_available"}")
        appendLine("stream_client_override=${resolverDiagnostics?.preferredClient?.let(::sanitizeDiagnosticValue) ?: "default"}")
        appendLine("stream_client_candidates=${resolverDiagnostics?.candidateClients?.joinToString(",") { sanitizeDiagnosticValue(it) } ?: "not_available"}")
        appendLine("resolver_snapshot_age_ms=${resolverDiagnostics?.let { (nowMs - it.resolvedAtMs).coerceAtLeast(0L) } ?: "not_available"}")
        appendLine("itag=$itag")
        appendLine("mime_type=$mimeType")
        appendLine("codec=${resolverDiagnostics?.codec?.let(::sanitizeDiagnosticValue) ?: "not_available"}")
        appendLine("bitrate_bps=${resolverDiagnostics?.bitrate ?: "not_available"}")
        appendLine("resolver_content_length_bytes=${resolverDiagnostics?.contentLength ?: "not_available"}")
        appendLine("n_parameter=$nParameter")
        appendLine("n_parameter_before_transform=${resolverDiagnostics?.nParameterBeforeTransform ?: "not_available"}")
        appendLine("n_parameter_after_transform=${resolverDiagnostics?.nParameterAfterTransform ?: "not_available"}")
        appendLine("n_transform_required=${resolverDiagnostics?.nTransformRequired ?: "not_available"}")
        appendLine("n_transform_attempted=${resolverDiagnostics?.nTransformAttempted ?: "not_available"}")
        appendLine("n_transform_result=${resolverDiagnostics?.nTransformResult?.let(::sanitizeDiagnosticValue) ?: "not_available"}")
        appendLine("potoken_required=${resolverDiagnostics?.poTokenRequired ?: "not_available"}")
        appendLine("potoken_available=${resolverDiagnostics?.poTokenAvailable ?: "not_available"}")
        appendLine("potoken_appended=${resolverDiagnostics?.poTokenAppended ?: "not_available"}")
        appendLine("signature_cipher_present=${resolverDiagnostics?.signatureCipherPresent ?: "not_available"}")
        appendLine("stream_validation=${resolverDiagnostics?.validationResult?.let(::sanitizeDiagnosticValue) ?: "not_available"}")
        appendLine("resolver_recovery_events=${resolverDiagnostics?.resolverRecoveryEvents?.joinToString(",") { sanitizeDiagnosticValue(it) }?.takeIf { it.isNotEmpty() } ?: "none"}")
        appendLine("rate_note=current rate is sampled from Media3 byte progress; lifetime average includes waiting/retry time")
        append("privacy=stream URL, token, signature, cookie and authorization-header values are intentionally excluded")
    }
}

private fun safeQueryParameterPresence(download: Download, name: String): String =
    runCatching {
        if (download.request.uri.queryParameterNames.contains(name)) "present" else "absent"
    }.getOrElse { "unknown" }

private fun safeNumericQueryValue(download: Download, name: String): String? =
    runCatching { download.request.uri.getQueryParameter(name) }
        .getOrNull()
        ?.takeIf { value -> value.length in 1..6 && value.all(Char::isDigit) }

private fun safeWhitelistedQueryValue(download: Download, name: String): String? =
    runCatching { download.request.uri.getQueryParameter(name) }
        .getOrNull()
        ?.takeIf { SAFE_DIAGNOSTIC_QUERY_VALUE.matches(it) }

private fun sanitizeDiagnosticValue(value: String): String =
    value
        .replace('\r', ' ')
        .replace('\n', ' ')
        .replace('\t', ' ')
        .take(240)

private fun formatRateMBps(bytesPerSecond: Double?): String =
    bytesPerSecond?.let { String.format(Locale.US, "%.2f", it / 1_000_000.0) } ?: "not_available"

private fun formatRateMbps(bytesPerSecond: Double?): String =
    bytesPerSecond?.let { String.format(Locale.US, "%.2f", it * 8.0 / 1_000_000.0) } ?: "not_available"

private fun downloadStateName(state: Int): String =
    when (state) {
        Download.STATE_QUEUED -> "QUEUED"
        Download.STATE_STOPPED -> "STOPPED"
        Download.STATE_DOWNLOADING -> "DOWNLOADING"
        Download.STATE_COMPLETED -> "COMPLETED"
        Download.STATE_FAILED -> "FAILED"
        Download.STATE_REMOVING -> "REMOVING"
        Download.STATE_RESTARTING -> "RESTARTING"
        else -> "UNKNOWN($state)"
    }

private fun copyDiagnosticReport(context: Context, report: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
    clipboard.setPrimaryClip(ClipData.newPlainText("MetroList download diagnostics", report))
}

private fun downloadPriority(download: Download): Int =
    when (download.state) {
        Download.STATE_FAILED -> 0
        Download.STATE_DOWNLOADING -> 1
        Download.STATE_QUEUED, Download.STATE_RESTARTING -> 2
        Download.STATE_STOPPED -> 3
        Download.STATE_REMOVING -> 4
        else -> 5
    }

private fun formatBytes(bytes: Long): String {
    val kib = 1024.0
    val mib = kib * 1024.0
    val gib = mib * 1024.0
    return when {
        bytes < 1024L -> "$bytes B"
        bytes < mib -> String.format(Locale.getDefault(), "%.1f KB", bytes / kib)
        bytes < gib -> String.format(Locale.getDefault(), "%.1f MB", bytes / mib)
        else -> String.format(Locale.getDefault(), "%.1f GB", bytes / gib)
    }
}
