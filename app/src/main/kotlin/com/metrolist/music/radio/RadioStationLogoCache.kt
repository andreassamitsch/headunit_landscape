package com.metrolist.music.radio

import android.content.Context
import android.net.Uri
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale

/** Stores station logos locally so playback metadata and network changes cannot remove them. */
object RadioStationLogoCache {
    private const val MAX_LOGO_BYTES = 8 * 1024 * 1024
    private const val USER_AGENT = "MetrolistHU/13.7.5 (station logo cache)"

    suspend fun cache(
        context: Context,
        stationUuid: String,
        source: String,
    ): String? =
        withContext(Dispatchers.IO) {
            val value = source.trim()
            if (value.isBlank()) return@withContext null
            val directory = File(context.applicationContext.filesDir, "radio_logos").apply { mkdirs() }
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

            var connection: HttpURLConnection? = null
            var input: InputStream? = null
            try {
                var contentType: String? = null
                input =
                    when (sourceUri?.scheme?.lowercase(Locale.ROOT)) {
                        "content" -> {
                            contentType = context.contentResolver.getType(sourceUri)
                            context.contentResolver.openInputStream(sourceUri)
                        }
                        "file" -> existingFile?.let(::FileInputStream)
                        "http", "https" -> {
                            connection =
                                (URL(value).openConnection() as HttpURLConnection).apply {
                                    connectTimeout = 8_000
                                    readTimeout = 10_000
                                    instanceFollowRedirects = true
                                    setRequestProperty("User-Agent", USER_AGENT)
                                    setRequestProperty("Accept", "image/avif,image/webp,image/*,*/*;q=0.7")
                                }
                            if (connection!!.responseCode !in 200..299) return@withContext null
                            contentType = connection!!.contentType
                            connection!!.inputStream
                        }
                        else -> null
                    }
                val sourceInput = input ?: return@withContext null
                val extension = extensionFor(value, contentType)
                if (extension == "svg") return@withContext null
                val safeUuid = stationUuid.replace(Regex("[^A-Za-z0-9._-]"), "_")
                val target = File(directory, "$safeUuid.$extension")
                val temporary = File(directory, "$safeUuid.$extension.tmp")
                directory.listFiles()?.filter { it.name.startsWith("$safeUuid.") && it != temporary }?.forEach(File::delete)

                sourceInput.use { sourceStream ->
                    temporary.outputStream().use { output ->
                        val buffer = ByteArray(16 * 1024)
                        var total = 0
                        while (true) {
                            val count = sourceStream.read(buffer)
                            if (count <= 0) break
                            total += count
                            if (total > MAX_LOGO_BYTES) {
                                temporary.delete()
                                return@withContext null
                            }
                            output.write(buffer, 0, count)
                        }
                        if (total == 0) {
                            temporary.delete()
                            return@withContext null
                        }
                    }
                }
                if (!temporary.renameTo(target)) {
                    temporary.copyTo(target, overwrite = true)
                    temporary.delete()
                }
                Uri.fromFile(target).toString()
            } catch (_: Exception) {
                null
            } finally {
                runCatching { input?.close() }
                connection?.disconnect()
            }
        }

    fun isLocal(value: String): Boolean {
        val scheme = runCatching { Uri.parse(value.trim()).scheme }.getOrNull()
        return scheme.equals("file", ignoreCase = true) || scheme.equals("content", ignoreCase = true)
    }

    private fun extensionFor(source: String, contentType: String?): String {
        val mime = contentType.orEmpty().substringBefore(';').lowercase(Locale.ROOT)
        return when {
            "png" in mime -> "png"
            "jpeg" in mime || "jpg" in mime -> "jpg"
            "webp" in mime -> "webp"
            "gif" in mime -> "gif"
            "avif" in mime -> "avif"
            "svg" in mime -> "svg"
            else -> {
                val extension =
                    runCatching { Uri.parse(source).lastPathSegment.orEmpty().substringAfterLast('.', "") }
                        .getOrDefault("")
                        .substringBefore('?')
                        .lowercase(Locale.ROOT)
                extension.takeIf { it in setOf("png", "jpg", "jpeg", "webp", "gif", "avif", "svg") }
                    ?.replace("jpeg", "jpg")
                    ?: "png"
            }
        }
    }
}
