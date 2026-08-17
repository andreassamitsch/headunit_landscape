from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'Expected exactly one match in {path}: found {count} for {old[:120]!r}')
    path.write_text(text.replace(old, new, 1), encoding='utf-8')


# 13.7.67
build = ROOT / 'app/build.gradle.kts'
replace_once(build, 'versionCode = 1370075', 'versionCode = 1370076')
replace_once(build, 'versionName = "13.7.66"', 'versionName = "13.7.67"')

# Downloaded songs: the persistent download cache must still be consulted when
# ExoPlayer's first request has LENGTH_UNSET. Keep the HLS/player-cache bypass
# only on the inner transient cache.
music = ROOT / 'app/src/main/kotlin/com/metrolist/music/playback/MusicService.kt'
replace_once(
    music,
    '''            ).setCacheWriteDataSinkFactory(null)\n            .setFlags(FLAG_IGNORE_CACHE_ON_ERROR or FLAG_IGNORE_CACHE_FOR_UNSET_LENGTH_REQUESTS)\n''',
    '''            ).setCacheWriteDataSinkFactory(null)\n            // The outer cache contains completed offline downloads. A normal song's\n            // first DataSpec commonly has LENGTH_UNSET, so ignoring the cache here\n            // defeats offline playback and forces a network resolve. HLS/live safety\n            // remains on the inner playerCache layer above.\n            .setFlags(FLAG_IGNORE_CACHE_ON_ERROR)\n''',
)

# Dudu7 is allowed to request APK installs. Standard flavor stays untouched.
dudu7_manifest = ROOT / 'app/src/dudu7/AndroidManifest.xml'
replace_once(
    dudu7_manifest,
    '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n',
    '    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS" />\n'
    '    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n',
)

# Variant bridge: standard MetroList renders nothing; Dudu7 gets its update center.
standard_bridge = ROOT / 'app/src/standard/kotlin/com/metrolist/music/variant/Dudu7Updater.kt'
standard_bridge.parent.mkdir(parents=True, exist_ok=True)
standard_bridge.write_text('''package com.metrolist.music.variant\n\nimport androidx.compose.runtime.Composable\n\n@Composable\nfun Dudu7UpdaterCard() = Unit\n''', encoding='utf-8')

manager = ROOT / 'app/src/dudu7/kotlin/com/metrolist/music/update/Dudu7UpdateManager.kt'
manager.parent.mkdir(parents=True, exist_ok=True)
manager.write_text(r'''package com.metrolist.music.update

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.content.FileProvider
import com.metrolist.music.BuildConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest
import java.util.Locale
import java.util.concurrent.TimeUnit

internal const val DUDU7_RELEASES_URL =
    "https://api.github.com/repos/andreassamitsch/headunit_landscape/releases?per_page=20"
internal const val DUDU7_RELEASE_TAG_PREFIX = "dudu7-v"
internal const val DUDU7_MANIFEST_ASSET = "dudu7-update.json"

internal data class Dudu7ReleaseDescriptor(
    val tag: String,
    val versionLabel: String,
    val notes: String,
    val publishedAt: String,
    val manifestUrl: String,
    val assets: Map<String, String>,
)

internal data class Dudu7UpdateManifest(
    val versionCode: Long,
    val versionName: String,
    val packageName: String,
    val signerSha256: String,
    val apkAsset: String,
    val sha256: String,
)

internal data class Dudu7UpdateCandidate(
    val release: Dudu7ReleaseDescriptor,
    val manifest: Dudu7UpdateManifest,
    val apkUrl: String,
)

internal enum class Dudu7UpdatePhase {
    IDLE,
    CHECKING,
    CURRENT,
    AVAILABLE,
    DOWNLOADING,
    VERIFYING,
    READY,
    PERMISSION_REQUIRED,
    ERROR,
}

internal data class Dudu7UpdateUiState(
    val phase: Dudu7UpdatePhase = Dudu7UpdatePhase.IDLE,
    val candidate: Dudu7UpdateCandidate? = null,
    val progress: Float = 0f,
    val message: String = "",
    val verifiedFile: File? = null,
)

internal fun selectDudu7Release(json: String): Dudu7ReleaseDescriptor? {
    val releases = JSONArray(json)
    for (index in 0 until releases.length()) {
        val release = releases.getJSONObject(index)
        if (release.optBoolean("draft", false)) continue
        val tag = release.optString("tag_name")
        if (!tag.startsWith(DUDU7_RELEASE_TAG_PREFIX)) continue
        val assetsJson = release.optJSONArray("assets") ?: JSONArray()
        val assets = buildMap {
            for (assetIndex in 0 until assetsJson.length()) {
                val asset = assetsJson.getJSONObject(assetIndex)
                val name = asset.optString("name")
                val url = asset.optString("browser_download_url")
                if (name.isNotBlank() && url.isNotBlank()) put(name, url)
            }
        }
        val manifestUrl = assets[DUDU7_MANIFEST_ASSET] ?: continue
        return Dudu7ReleaseDescriptor(
            tag = tag,
            versionLabel = release.optString("name").ifBlank { tag.removePrefix(DUDU7_RELEASE_TAG_PREFIX) },
            notes = release.optString("body"),
            publishedAt = release.optString("published_at"),
            manifestUrl = manifestUrl,
            assets = assets,
        )
    }
    return null
}

internal fun parseDudu7UpdateManifest(json: String): Dudu7UpdateManifest {
    val value = JSONObject(json)
    return Dudu7UpdateManifest(
        versionCode = value.getLong("versionCode"),
        versionName = value.getString("versionName"),
        packageName = value.getString("packageName"),
        signerSha256 = normalizeSha256(value.getString("signerSha256")),
        apkAsset = value.getString("apkAsset"),
        sha256 = normalizeSha256(value.getString("sha256")),
    )
}

internal fun normalizeSha256(value: String): String =
    value.lowercase(Locale.ROOT).replace(Regex("[^0-9a-f]"), "")

internal fun isDudu7UpdateNewer(installedVersionCode: Long, remoteVersionCode: Long): Boolean =
    remoteVersionCode > installedVersionCode

internal class Dudu7UpdateManager(context: Context) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val client =
        OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(45, TimeUnit.SECONDS)
            .build()
    private val _state = MutableStateFlow(Dudu7UpdateUiState())
    val state: StateFlow<Dudu7UpdateUiState> = _state.asStateFlow()

    fun checkForUpdates() {
        if (_state.value.phase == Dudu7UpdatePhase.CHECKING ||
            _state.value.phase == Dudu7UpdatePhase.DOWNLOADING ||
            _state.value.phase == Dudu7UpdatePhase.VERIFYING
        ) return
        scope.launch {
            _state.value = Dudu7UpdateUiState(
                phase = Dudu7UpdatePhase.CHECKING,
                message = "Dudu7-Entwicklungsstand wird geprüft …",
            )
            runCatching {
                val releaseJson = getText(DUDU7_RELEASES_URL, githubApi = true)
                val release = selectDudu7Release(releaseJson)
                    ?: error("Noch kein Dudu7-Release im Updatekanal gefunden")
                val manifest = parseDudu7UpdateManifest(getText(release.manifestUrl))
                if (manifest.packageName != appContext.packageName) {
                    error("Update gehört zu einem anderen Paket")
                }
                val apkUrl = release.assets[manifest.apkAsset]
                    ?: error("APK ${manifest.apkAsset} fehlt im Release")
                val candidate = Dudu7UpdateCandidate(release, manifest, apkUrl)
                if (isDudu7UpdateNewer(BuildConfig.VERSION_CODE.toLong(), manifest.versionCode)) {
                    Dudu7UpdateUiState(
                        phase = Dudu7UpdatePhase.AVAILABLE,
                        candidate = candidate,
                        message = "Neue Dudu7-Version verfügbar",
                    )
                } else {
                    Dudu7UpdateUiState(
                        phase = Dudu7UpdatePhase.CURRENT,
                        candidate = candidate,
                        message = "Du verwendest den aktuellen Dudu7-Stand",
                    )
                }
            }.onSuccess { _state.value = it }
                .onFailure { error ->
                    _state.value = Dudu7UpdateUiState(
                        phase = Dudu7UpdatePhase.ERROR,
                        message = error.message ?: "Updateprüfung fehlgeschlagen",
                    )
                }
        }
    }

    fun downloadAndVerify() {
        val candidate = _state.value.candidate ?: return
        if (!isDudu7UpdateNewer(BuildConfig.VERSION_CODE.toLong(), candidate.manifest.versionCode)) return
        scope.launch {
            runCatching {
                val updateDir = File(appContext.cacheDir, "dudu7-updates").apply { mkdirs() }
                updateDir.listFiles()?.forEach { it.delete() }
                val target = File(updateDir, candidate.manifest.apkAsset)
                _state.value = _state.value.copy(
                    phase = Dudu7UpdatePhase.DOWNLOADING,
                    progress = 0f,
                    message = "APK wird geladen …",
                    verifiedFile = null,
                )
                download(candidate.apkUrl, target) { progress ->
                    _state.value = _state.value.copy(progress = progress)
                }
                _state.value = _state.value.copy(
                    phase = Dudu7UpdatePhase.VERIFYING,
                    progress = 1f,
                    message = "Prüfsumme, Paket und Signatur werden geprüft …",
                )
                verifyApk(target, candidate.manifest)
                Dudu7UpdateUiState(
                    phase = Dudu7UpdatePhase.READY,
                    candidate = candidate,
                    progress = 1f,
                    message = "Update geprüft und installationsbereit",
                    verifiedFile = target,
                )
            }.onSuccess { _state.value = it }
                .onFailure { error ->
                    _state.value = _state.value.copy(
                        phase = Dudu7UpdatePhase.ERROR,
                        message = error.message ?: "Update konnte nicht vorbereitet werden",
                        verifiedFile = null,
                    )
                }
        }
    }

    fun installVerifiedUpdate() {
        val file = _state.value.verifiedFile?.takeIf(File::isFile) ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !appContext.packageManager.canRequestPackageInstalls()) {
            _state.value = _state.value.copy(
                phase = Dudu7UpdatePhase.PERMISSION_REQUIRED,
                message = "Android muss MetroList die Installation unbekannter Apps erlauben",
            )
            val permissionIntent = Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${appContext.packageName}"),
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            appContext.startActivity(permissionIntent)
            return
        }
        val uri = FileProvider.getUriForFile(
            appContext,
            "${appContext.packageName}.FileProvider",
            file,
        )
        val intent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        appContext.startActivity(intent)
    }

    private fun getText(url: String, githubApi: Boolean = false): String {
        val request = Request.Builder().url(url)
            .header("User-Agent", "Metrolist-dudu7/${BuildConfig.VERSION_NAME}")
            .apply {
                if (githubApi) header("Accept", "application/vnd.github+json")
            }
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code} bei Updateprüfung")
            return response.body?.string() ?: error("Leere Updateantwort")
        }
    }

    private fun download(url: String, file: File, progress: (Float) -> Unit) {
        val request = Request.Builder().url(url)
            .header("User-Agent", "Metrolist-dudu7/${BuildConfig.VERSION_NAME}")
            .build()
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) error("APK-Download fehlgeschlagen: HTTP ${response.code}")
            val body = response.body ?: error("APK-Download ist leer")
            val total = body.contentLength()
            body.byteStream().use { input ->
                file.outputStream().use { output ->
                    val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                    var copied = 0L
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                        copied += count
                        if (total > 0) progress((copied.toFloat() / total.toFloat()).coerceIn(0f, 1f))
                    }
                }
            }
            if (file.length() <= 0L) error("APK-Download ist leer")
        }
    }

    private fun verifyApk(file: File, manifest: Dudu7UpdateManifest) {
        val actualSha = sha256(file)
        if (actualSha != manifest.sha256) error("SHA-256 stimmt nicht – Update verworfen")
        val archive = archivePackageInfo(file) ?: error("APK kann nicht gelesen werden")
        if (archive.packageName != manifest.packageName || archive.packageName != appContext.packageName) {
            error("APK-Paketname stimmt nicht")
        }
        if (!isDudu7UpdateNewer(BuildConfig.VERSION_CODE.toLong(), archive.longVersionCode)) {
            error("APK ist nicht neuer als die installierte Version")
        }
        if (archive.longVersionCode != manifest.versionCode) error("APK-VersionCode weicht vom Release ab")

        val installed = installedPackageInfo()
        val installedSigners = signerDigests(installed)
        val archiveSigners = signerDigests(archive)
        if (installedSigners.isEmpty() || archiveSigners.isEmpty() || installedSigners != archiveSigners) {
            error("APK-Signatur stimmt nicht mit der installierten Dudu7-App überein")
        }
        if (manifest.signerSha256.isNotBlank() && manifest.signerSha256 !in archiveSigners) {
            error("APK-Signatur stimmt nicht mit dem Release-Manifest überein")
        }
    }

    @Suppress("DEPRECATION")
    private fun archivePackageInfo(file: File): PackageInfo? =
        if (Build.VERSION.SDK_INT >= 33) {
            appContext.packageManager.getPackageArchiveInfo(
                file.absolutePath,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
            )
        } else {
            appContext.packageManager.getPackageArchiveInfo(file.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES)
        }

    @Suppress("DEPRECATION")
    private fun installedPackageInfo(): PackageInfo =
        if (Build.VERSION.SDK_INT >= 33) {
            appContext.packageManager.getPackageInfo(
                appContext.packageName,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
            )
        } else {
            appContext.packageManager.getPackageInfo(appContext.packageName, PackageManager.GET_SIGNING_CERTIFICATES)
        }

    @Suppress("DEPRECATION")
    private fun signerDigests(info: PackageInfo): Set<String> {
        val signatures =
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                info.signingInfo?.apkContentsSigners?.toList().orEmpty()
            } else {
                info.signatures?.toList().orEmpty()
            }
        return signatures.map { signature ->
            val digest = MessageDigest.getInstance("SHA-256").digest(signature.toByteArray())
            digest.joinToString("") { byte -> (byte.toInt() and 0xff).toString(16).padStart(2, '0') }
        }.toSet()
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { byte -> (byte.toInt() and 0xff).toString(16).padStart(2, '0') }
    }
}
''', encoding='utf-8')

ui = ROOT / 'app/src/dudu7/kotlin/com/metrolist/music/variant/Dudu7Updater.kt'
ui.parent.mkdir(parents=True, exist_ok=True)
ui.write_text(r'''package com.metrolist.music.variant

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.metrolist.music.BuildConfig
import com.metrolist.music.update.Dudu7UpdateManager
import com.metrolist.music.update.Dudu7UpdatePhase

@Composable
fun Dudu7UpdaterCard() {
    val context = LocalContext.current
    val manager = remember(context.applicationContext) { Dudu7UpdateManager(context.applicationContext) }
    val state by manager.state.collectAsStateWithLifecycle()
    val candidate = state.candidate

    LaunchedEffect(Unit) { manager.checkForUpdates() }

    ElevatedCard(
        shape = RoundedCornerShape(28.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.linearGradient(
                        listOf(
                            MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.72f),
                            MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.38f),
                            MaterialTheme.colorScheme.surfaceContainerHigh,
                        ),
                    ),
                ),
        ) {
            Column(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                modifier = Modifier.fillMaxWidth().padding(20.dp),
            ) {
                Row(
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "Dudu7 Update Center",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Black,
                        )
                        Text(
                            text = "Installiert: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Surface(
                        shape = RoundedCornerShape(50),
                        color = when (state.phase) {
                            Dudu7UpdatePhase.AVAILABLE, Dudu7UpdatePhase.READY -> MaterialTheme.colorScheme.primary
                            Dudu7UpdatePhase.ERROR -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.surfaceContainerHighest
                        },
                    ) {
                        Text(
                            text = when (state.phase) {
                                Dudu7UpdatePhase.AVAILABLE -> "NEU"
                                Dudu7UpdatePhase.READY -> "BEREIT"
                                Dudu7UpdatePhase.CURRENT -> "AKTUELL"
                                Dudu7UpdatePhase.ERROR -> "FEHLER"
                                else -> "DUDU7"
                            },
                            color = when (state.phase) {
                                Dudu7UpdatePhase.AVAILABLE, Dudu7UpdatePhase.READY -> MaterialTheme.colorScheme.onPrimary
                                Dudu7UpdatePhase.ERROR -> MaterialTheme.colorScheme.onError
                                else -> MaterialTheme.colorScheme.onSurfaceVariant
                            },
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                        )
                    }
                }

                if (candidate != null) {
                    Text(
                        text = "Verfügbar: ${candidate.manifest.versionName} (${candidate.manifest.versionCode})",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    if (candidate.release.publishedAt.isNotBlank()) {
                        Text(
                            text = "Veröffentlicht: ${candidate.release.publishedAt.replace('T', ' ').removeSuffix("Z")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    val notes = candidate.release.notes
                        .replace("**", "")
                        .replace(Regex("(?m)^#{1,6}\\s*"), "")
                        .trim()
                    if (notes.isNotBlank()) {
                        Text(
                            text = notes,
                            style = MaterialTheme.typography.bodyMedium,
                            maxLines = 8,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }

                if (state.message.isNotBlank()) {
                    Text(
                        text = state.message,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (state.phase == Dudu7UpdatePhase.ERROR) {
                            MaterialTheme.colorScheme.error
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }

                if (state.phase == Dudu7UpdatePhase.DOWNLOADING || state.phase == Dudu7UpdatePhase.VERIFYING) {
                    LinearProgressIndicator(
                        progress = { state.progress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        text = if (state.phase == Dudu7UpdatePhase.DOWNLOADING) {
                            "${(state.progress * 100).toInt()} %"
                        } else {
                            "Integrität wird geprüft"
                        },
                        style = MaterialTheme.typography.labelMedium,
                    )
                }

                Row(
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    OutlinedButton(
                        onClick = manager::checkForUpdates,
                        enabled = state.phase != Dudu7UpdatePhase.CHECKING &&
                            state.phase != Dudu7UpdatePhase.DOWNLOADING &&
                            state.phase != Dudu7UpdatePhase.VERIFYING,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text(if (state.phase == Dudu7UpdatePhase.CHECKING) "Prüfe …" else "Neu prüfen")
                    }
                    when (state.phase) {
                        Dudu7UpdatePhase.AVAILABLE -> {
                            Button(onClick = manager::downloadAndVerify, modifier = Modifier.weight(1f)) {
                                Text("Laden & prüfen")
                            }
                        }
                        Dudu7UpdatePhase.READY, Dudu7UpdatePhase.PERMISSION_REQUIRED -> {
                            Button(onClick = manager::installVerifiedUpdate, modifier = Modifier.weight(1f)) {
                                Text(if (state.phase == Dudu7UpdatePhase.PERMISSION_REQUIRED) "Installation fortsetzen" else "Installieren")
                            }
                        }
                        else -> Unit
                    }
                }

                Spacer(Modifier.height(1.dp))
                Text(
                    text = "Vor der Installation werden SHA-256, Paketname, VersionCode und App-Signatur geprüft. Android führt die Installation anschließend selbst aus.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
''', encoding='utf-8')

# Add updater card to About screen directly beneath app identity.
about = ROOT / 'app/src/main/kotlin/com/metrolist/music/ui/screens/settings/AboutScreen.kt'
replace_once(
    about,
    'import com.metrolist.music.ui.utils.backToMain\n',
    'import com.metrolist.music.ui.utils.backToMain\nimport com.metrolist.music.variant.Dudu7UpdaterCard\n',
)
replace_once(
    about,
    '''        Spacer(Modifier.height(24.dp))\n\n        // Lead Developer Hero Card\n''',
    '''        Spacer(Modifier.height(20.dp))\n\n        Dudu7UpdaterCard()\n\n        Spacer(Modifier.height(24.dp))\n\n        // Lead Developer Hero Card\n''',
)

# Pure protocol regression tests.
test = ROOT / 'app/src/test/kotlin/com/metrolist/music/update/Dudu7UpdateProtocolTest.kt'
test.parent.mkdir(parents=True, exist_ok=True)
test.write_text(r'''package com.metrolist.music.update

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7UpdateProtocolTest {
    @Test
    fun `selects newest non-draft Dudu7 release with manifest`() {
        val json = """[
          {"tag_name":"other-v9","draft":false,"assets":[]},
          {"tag_name":"dudu7-v13.7.68","name":"13.7.68","draft":false,"prerelease":true,
           "body":"new notes","published_at":"2026-08-17T10:00:00Z","assets":[
             {"name":"dudu7-update.json","browser_download_url":"https://example/manifest"},
             {"name":"Metrolist.apk","browser_download_url":"https://example/apk"}
           ]},
          {"tag_name":"dudu7-v13.7.67","draft":false,"assets":[
             {"name":"dudu7-update.json","browser_download_url":"https://example/old"}
           ]}
        ]"""
        val result = selectDudu7Release(json)
        assertNotNull(result)
        assertEquals("dudu7-v13.7.68", result?.tag)
        assertEquals("https://example/manifest", result?.manifestUrl)
        assertEquals("https://example/apk", result?.assets?.get("Metrolist.apk"))
    }

    @Test
    fun `ignores draft or releases without signed manifest`() {
        val json = """[
          {"tag_name":"dudu7-v99","draft":true,"assets":[{"name":"dudu7-update.json","browser_download_url":"x"}]},
          {"tag_name":"dudu7-v98","draft":false,"assets":[]}
        ]"""
        assertNull(selectDudu7Release(json))
    }

    @Test
    fun `parses and normalizes release manifest`() {
        val manifest = parseDudu7UpdateManifest("""{
          "versionCode":1370077,
          "versionName":"13.7.68",
          "packageName":"com.metrolist.music.dudu7.debug",
          "signerSha256":"AA:BB:CC",
          "apkAsset":"Metrolist.apk",
          "sha256":"11 22 33"
        }""")
        assertEquals(1370077L, manifest.versionCode)
        assertEquals("aabbcc", manifest.signerSha256)
        assertEquals("112233", manifest.sha256)
    }

    @Test
    fun `version comparison uses versionCode only`() {
        assertTrue(isDudu7UpdateNewer(1370076, 1370077))
        assertFalse(isDudu7UpdateNewer(1370076, 1370076))
        assertFalse(isDudu7UpdateNewer(1370076, 1370000))
    }
}
''', encoding='utf-8')

# Guardrails.
assert 'versionCode = 1370076' in build.read_text()
assert 'versionName = "13.7.67"' in build.read_text()
assert 'setFlags(FLAG_IGNORE_CACHE_ON_ERROR)\n' in music.read_text()
assert 'REQUEST_INSTALL_PACKAGES' in dudu7_manifest.read_text()
assert 'Dudu7UpdaterCard()' in about.read_text()
print('Issues #130 and #131 patch applied')
