package com.metrolist.music.radio

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
