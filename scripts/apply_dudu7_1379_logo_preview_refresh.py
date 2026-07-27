from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker missing in {path}: {old[:160]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/build.gradle.kts",
    '        versionCode = 167\n        versionName = "13.7.8"',
    '        versionCode = 168\n        versionName = "13.7.9"',
)

store_path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationStore.kt")
store = store_path.read_text(encoding="utf-8")
old_store = '''    @Synchronized
    fun addOrUpdate(station: RadioStation) {
        val list = _stations.value.toMutableList()
        val index = list.indexOfFirst { it.uuid == station.uuid }
        if (index >= 0) {
            val previous = list[index]
            val stableStation =
                when {
                    previous.manualFavicon && previous.favicon.isNotBlank() ->
                        station.copy(favicon = previous.favicon, manualFavicon = true)
                    station.favicon.isBlank() && previous.favicon.isNotBlank() ->
                        station.copy(favicon = previous.favicon)
                    else -> station
                }
            list[index] = stableStation
        } else {
            list.add(station)
        }
        persist(list)
    }
'''
new_store = '''    /** Background catalogue/metadata updates may not replace a fixed user logo. */
    @Synchronized
    fun addOrUpdate(station: RadioStation) {
        addOrUpdateInternal(station, preserveExistingManualLogo = true)
    }

    /** An explicit edit is allowed to replace or clear the previously fixed logo. */
    @Synchronized
    fun replaceFromUser(station: RadioStation) {
        addOrUpdateInternal(station, preserveExistingManualLogo = false)
    }

    private fun addOrUpdateInternal(
        station: RadioStation,
        preserveExistingManualLogo: Boolean,
    ) {
        val list = _stations.value.toMutableList()
        val index = list.indexOfFirst { it.uuid == station.uuid }
        if (index >= 0) {
            val previous = list[index]
            val stableStation =
                when {
                    preserveExistingManualLogo && previous.manualFavicon && previous.favicon.isNotBlank() ->
                        station.copy(favicon = previous.favicon, manualFavicon = true)
                    preserveExistingManualLogo && station.favicon.isBlank() && previous.favicon.isNotBlank() ->
                        station.copy(favicon = previous.favicon)
                    else -> station
                }
            list[index] = stableStation
        } else {
            list.add(station)
        }
        persist(list)
    }
'''
if new_store not in store:
    if old_store not in store:
        raise SystemExit("RadioStationStore addOrUpdate marker missing")
    store_path.write_text(store.replace(old_store, new_store, 1), encoding="utf-8")

cache_content = r'''package com.metrolist.music.radio

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.PorterDuff
import android.graphics.RectF
import android.net.Uri
import coil3.imageLoader
import coil3.request.CachePolicy
import coil3.request.ImageRequest
import coil3.request.SuccessResult
import coil3.request.allowHardware
import coil3.size.Scale
import coil3.toBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.min

/**
 * Decodes and validates station artwork before it is shown or persisted. Every
 * selected logo becomes a new local 512 x 512 PNG URI, so Coil cannot keep
 * displaying an older bitmap under the same file-cache key.
 */
object RadioStationLogoCache {
    private const val TARGET_SIZE = 512
    private const val MIN_SOURCE_SIZE = 24
    private const val MAX_REMOTE_BYTES = 10_000_000
    private const val USER_AGENT = "MetrolistHU/13.7.9 (radio artwork)"
    private const val FINAL_DIRECTORY = "radio_logos"
    private const val PREVIEW_DIRECTORY = "radio_logo_previews"

    suspend fun cache(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? = cacheNormalized(context, FINAL_DIRECTORY, stationUuid, source)

    /** A separate unique file is used for each candidate; failed images never reach the UI. */
    suspend fun cachePreview(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? {
        val sourceKey = source.hashCode().toString().replace('-', 'n')
        return cacheNormalized(context, PREVIEW_DIRECTORY, "${stationUuid}_$sourceKey", source)
    }

    fun clearPreviews(context: Context, stationUuid: String) {
        val prefix = safeKey(stationUuid) + "_"
        File(context.applicationContext.cacheDir, PREVIEW_DIRECTORY)
            .listFiles()
            ?.filter { it.name.startsWith(prefix) }
            ?.forEach(File::delete)
    }

    private suspend fun cacheNormalized(
        context: Context,
        directoryName: String,
        cacheKey: String,
        source: String,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val value = source.trim()
            if (value.isBlank()) return@withContext null
            val root = if (directoryName == PREVIEW_DIRECTORY) appContext.cacheDir else appContext.filesDir
            val directory = File(root, directoryName).apply { mkdirs() }
            val sourceUri = runCatching { Uri.parse(value) }.getOrNull()
            val existingFile =
                sourceUri
                    ?.takeIf { it.scheme.equals("file", ignoreCase = true) }
                    ?.path
                    ?.let(::File)
                    ?.takeIf { it.isFile }
            if (existingFile != null && existingFile.parentFile?.canonicalFile == directory.canonicalFile) {
                return@withContext Uri.fromFile(existingFile).toString()
            }

            val requestData: Any =
                if (value.startsWith("https://", true) || value.startsWith("http://", true)) {
                    download(value) ?: return@withContext null
                } else {
                    value
                }
            val request =
                ImageRequest
                    .Builder(appContext)
                    .data(requestData)
                    .size(TARGET_SIZE, TARGET_SIZE)
                    .scale(Scale.FIT)
                    .allowHardware(false)
                    .memoryCachePolicy(CachePolicy.DISABLED)
                    .diskCachePolicy(CachePolicy.DISABLED)
                    .build()
            val result = appContext.imageLoader.execute(request) as? SuccessResult ?: return@withContext null
            val decoded = runCatching { result.image.toBitmap() }.getOrNull() ?: return@withContext null
            if (decoded.width < MIN_SOURCE_SIZE || decoded.height < MIN_SOURCE_SIZE || !hasVisibleContent(decoded)) {
                return@withContext null
            }

            val square = Bitmap.createBitmap(TARGET_SIZE, TARGET_SIZE, Bitmap.Config.ARGB_8888)
            val canvas = Canvas(square)
            canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)
            val scale = min(TARGET_SIZE.toFloat() / decoded.width, TARGET_SIZE.toFloat() / decoded.height)
            val width = decoded.width * scale
            val height = decoded.height * scale
            val left = (TARGET_SIZE - width) / 2f
            val top = (TARGET_SIZE - height) / 2f
            canvas.drawBitmap(
                decoded,
                null,
                RectF(left, top, left + width, top + height),
                Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG),
            )
            if (!hasVisibleContent(square)) return@withContext null

            val safeKey = safeKey(cacheKey)
            val version = System.currentTimeMillis().toString(36)
            val target = File(directory, "${safeKey}_$version.png")
            val temporary = File(directory, "${safeKey}_$version.png.tmp")
            val written =
                runCatching {
                    temporary.outputStream().buffered().use { output ->
                        square.compress(Bitmap.CompressFormat.PNG, 100, output)
                    }
                }.getOrDefault(false)
            if (!written || temporary.length() <= 0L) {
                temporary.delete()
                return@withContext null
            }
            if (!temporary.renameTo(target)) {
                temporary.copyTo(target, overwrite = true)
                temporary.delete()
            }
            directory
                .listFiles()
                ?.filter { file ->
                    file != target &&
                        (file.name == "$safeKey.png" || file.name.startsWith("${safeKey}_"))
                }?.forEach(File::delete)
            Uri.fromFile(target).toString()
        }

    private fun download(value: String): ByteArray? {
        val connection =
            runCatching {
                (URL(value).openConnection() as HttpURLConnection).apply {
                    connectTimeout = 8_000
                    readTimeout = 12_000
                    instanceFollowRedirects = true
                    setRequestProperty("User-Agent", USER_AGENT)
                    setRequestProperty("Accept", "image/avif,image/webp,image/svg+xml,image/*,*/*;q=0.7")
                }
            }.getOrNull() ?: return null
        return try {
            if (connection.responseCode !in 200..299) return null
            val output = ByteArrayOutputStream()
            connection.inputStream.use { input ->
                val buffer = ByteArray(8192)
                var total = 0
                while (true) {
                    val read = input.read(buffer)
                    if (read <= 0) break
                    total += read
                    if (total > MAX_REMOTE_BYTES) return null
                    output.write(buffer, 0, read)
                }
            }
            output.toByteArray().takeIf { it.isNotEmpty() }
        } catch (_: Exception) {
            null
        } finally {
            connection.disconnect()
        }
    }

    private fun hasVisibleContent(bitmap: Bitmap): Boolean {
        val stepX = maxOf(1, bitmap.width / 64)
        val stepY = maxOf(1, bitmap.height / 64)
        var y = 0
        while (y < bitmap.height) {
            var x = 0
            while (x < bitmap.width) {
                if (Color.alpha(bitmap.getPixel(x, y)) > 12) return true
                x += stepX
            }
            y += stepY
        }
        return false
    }

    private fun safeKey(value: String): String = value.replace(Regex("[^A-Za-z0-9._-]"), "_")

    fun isLocal(value: String): Boolean {
        val scheme = runCatching { Uri.parse(value.trim()).scheme }.getOrNull()
        return scheme.equals("file", ignoreCase = true) || scheme.equals("content", ignoreCase = true)
    }
}
'''
Path("app/src/main/kotlin/com/metrolist/music/radio/RadioStationLogoCache.kt").write_text(cache_content, encoding="utf-8")

screen_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt")
screen = screen_path.read_text(encoding="utf-8")

screen = screen.replace(
    "import kotlinx.coroutines.Job\nimport kotlinx.coroutines.launch\n",
    "import kotlinx.coroutines.Job\nimport kotlinx.coroutines.async\nimport kotlinx.coroutines.awaitAll\nimport kotlinx.coroutines.coroutineScope\nimport kotlinx.coroutines.launch\n",
    1,
)

old_search = '''            RadioStationLogoSearch.search(name.trim(), currentStation)
                .onSuccess { candidates ->
                    logoCandidates = candidates
                    if (logoCandidates.isEmpty()) logoSearchError = "Keine passenden Logos gefunden"
                }.onFailure { logoSearchError = it.message ?: "Logosuche fehlgeschlagen" }
            logoSearchLoading = false
'''
new_search = '''            val candidates =
                RadioStationLogoSearch.search(name.trim(), currentStation).getOrElse { error ->
                    logoSearchError = error.message ?: "Logosuche fehlgeschlagen"
                    logoSearchLoading = false
                    return@launch
                }
            RadioStationLogoCache.clearPreviews(context, stationUuid)
            val validated = mutableListOf<RadioLogoCandidate>()
            candidates.take(30).chunked(6).forEach { batch ->
                validated +=
                    coroutineScope {
                        batch.map { candidate ->
                            async {
                                RadioStationLogoCache
                                    .cachePreview(context, stationUuid, candidate.url)
                                    ?.let { preview -> candidate.copy(url = preview) }
                            }
                        }.awaitAll().filterNotNull()
                    }
            }
            logoCandidates = validated
            if (logoCandidates.isEmpty()) logoSearchError = "Keine darstellbaren Logos gefunden"
            logoSearchLoading = false
'''
if old_search not in screen:
    raise SystemExit("WebRadio logo search marker missing")
screen = screen.replace(old_search, new_search, 1)

old_save = '''                            val station = draft.copy(streamUrl = resolved)
                            store.addOrUpdate(station)
                            showAddDialog = false
'''
new_save = '''                            val station = draft.copy(streamUrl = resolved)
                            store.replaceFromUser(station)
                            val orderedIndex = orderedSavedStations.indexOfFirst { it.uuid == station.uuid }
                            if (orderedIndex >= 0) {
                                orderedSavedStations[orderedIndex] = station
                            } else {
                                orderedSavedStations.add(station)
                            }
                            refreshedFavoriteCache.remove(station.uuid)
                            showAddDialog = false
'''
if old_save not in screen:
    raise SystemExit("WebRadio explicit save marker missing")
screen = screen.replace(old_save, new_save, 1)

screen_path.write_text(screen, encoding="utf-8")
print("Applied Dudu7 13.7.9 logo preview validation and immediate favourite refresh")
