package com.metrolist.music.update

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
