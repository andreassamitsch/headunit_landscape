/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.ui.screens.library

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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.media3.common.util.Util
import androidx.media3.exoplayer.offline.Download
import androidx.media3.exoplayer.offline.DownloadService
import com.metrolist.music.LocalDownloadUtil
import com.metrolist.music.LocalPlayerAwareWindowInsets
import com.metrolist.music.R
import com.metrolist.music.playback.ExoDownloadService
import kotlinx.coroutines.delay
import java.util.Locale
import kotlin.math.roundToInt

private const val PROGRESS_REFRESH_MS = 750L
private const val RECENT_COMPLETED_LIMIT = 5

@Composable
fun DownloadQueueScreen(onBack: () -> Unit) {
    BackHandler(onBack = onBack)

    val context = LocalContext.current
    val downloadUtil = LocalDownloadUtil.current
    val downloads by downloadUtil.downloads.collectAsStateWithLifecycle()

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
    notMetRequirements: Int,
    refreshToken: Long,
    onRetry: () -> Unit,
    onResume: () -> Unit,
    onCancel: () -> Unit,
) {
    // Reading refreshToken makes progress-only Media3 changes observable to this row.
    @Suppress("UNUSED_VARIABLE")
    val progressRefresh = refreshToken

    val title = remember(download.request.id, download.request.data.contentHashCode()) {
        if (download.request.data.isNotEmpty()) {
            Util.fromUtf8Bytes(download.request.data)
        } else {
            download.request.id
        }
    }
    val percent = download.percentDownloaded
    val bytesDownloaded = download.bytesDownloaded.coerceAtLeast(0L)
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
        },
    )
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
