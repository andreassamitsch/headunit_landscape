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
import coil3.request.diskCachePolicy
import coil3.request.memoryCachePolicy
import coil3.request.scale
import coil3.request.size
import coil3.size.Scale
import coil3.toBitmap
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.min

/**
 * Validates and normalises every selected station logo into one local 512 x 512
 * PNG. SVG, WebP, AVIF and normal raster images are decoded by Coil first, so a
 * URL is never persisted merely because its HTTP content type looked plausible.
 */
object RadioStationLogoCache {
    private const val TARGET_SIZE = 512
    private const val MIN_SOURCE_SIZE = 24

    suspend fun cache(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val value = source.trim()
            if (value.isBlank()) return@withContext null
            val directory = File(appContext.filesDir, "radio_logos").apply { mkdirs() }
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

            val request =
                ImageRequest
                    .Builder(appContext)
                    .data(value)
                    .size(TARGET_SIZE, TARGET_SIZE)
                    .scale(Scale.FIT)
                    .allowHardware(false)
                    .memoryCachePolicy(CachePolicy.DISABLED)
                    .diskCachePolicy(CachePolicy.DISABLED)
                    .build()
            val result = appContext.imageLoader.execute(request) as? SuccessResult ?: return@withContext null
            val decoded = runCatching { result.image.toBitmap() }.getOrNull() ?: return@withContext null
            if (decoded.width < MIN_SOURCE_SIZE || decoded.height < MIN_SOURCE_SIZE) return@withContext null

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

            val safeUuid = stationUuid.replace(Regex("[^A-Za-z0-9._-]"), "_")
            val target = File(directory, "$safeUuid.png")
            val temporary = File(directory, "$safeUuid.png.tmp")
            directory.listFiles()
                ?.filter { it.name.startsWith("$safeUuid.") && it != temporary && it != target }
                ?.forEach(File::delete)
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
            Uri.fromFile(target).toString()
        }

    fun isLocal(value: String): Boolean {
        val scheme = runCatching { Uri.parse(value.trim()).scheme }.getOrNull()
        return scheme.equals("file", ignoreCase = true) || scheme.equals("content", ignoreCase = true)
    }
}
