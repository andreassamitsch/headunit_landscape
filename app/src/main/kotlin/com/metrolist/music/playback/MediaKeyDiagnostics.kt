package com.metrolist.music.playback

import android.content.Context
import android.content.Intent
import android.os.Build
import android.view.KeyEvent
import com.metrolist.music.BuildConfig
import timber.log.Timber
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object MediaKeyDiagnostics {
    private const val TAG = "Dudu7MediaKey"
    private const val PREFS = "media_key_diagnostics"
    private const val KEY_ENABLED = "enabled"
    private const val MAX_BYTES = 256 * 1024L
    private const val MAX_LINES = 1000
    private val lock = Any()

    fun isEnabled(context: Context): Boolean =
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_ENABLED, true)

    fun setEnabled(context: Context, enabled: Boolean) {
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, enabled)
            .apply()
        record(context, "DIAGNOSTICS", "recording=${if (enabled) "enabled" else "disabled"}", force = true)
    }

    fun record(
        context: Context,
        stage: String,
        details: String,
        force: Boolean = false,
    ) {
        val appContext = context.applicationContext
        if (!force && !isEnabled(appContext)) return
        val normalized = details.replace('\n', ' ').replace('\r', ' ').trim()
        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.GERMANY).format(Date())
        val line = "$timestamp | $stage | $normalized"
        synchronized(lock) {
            val file = logFile(appContext)
            file.parentFile?.mkdirs()
            file.appendText(line + "\n", Charsets.UTF_8)
            if (file.length() > MAX_BYTES) {
                val retained = file.readLines(Charsets.UTF_8).takeLast(MAX_LINES)
                file.writeText(retained.joinToString("\n", postfix = "\n"), Charsets.UTF_8)
            }
        }
        Timber.tag(TAG).i("%s | %s", stage, normalized)
    }

    fun recordMediaButton(
        context: Context,
        stage: String,
        intent: Intent,
        details: String = "",
    ) {
        val event = intent.mediaKeyEvent()
        val actionName = when (event?.action) {
            KeyEvent.ACTION_DOWN -> "ACTION_DOWN"
            KeyEvent.ACTION_UP -> "ACTION_UP"
            KeyEvent.ACTION_MULTIPLE -> "ACTION_MULTIPLE"
            null -> "NO_KEY_EVENT"
            else -> "ACTION_${event.action}"
        }
        val eventDetails = buildString {
            append("intent=")
            append(intent.action.orEmpty())
            append(" keyCode=")
            append(event?.keyCode ?: -1)
            append(" keyName=")
            append(event?.let { KeyEvent.keyCodeToString(it.keyCode) } ?: "NONE")
            append(" action=")
            append(actionName)
            append(" scanCode=")
            append(event?.scanCode ?: -1)
            append(" deviceId=")
            append(event?.deviceId ?: -1)
            append(" source=0x")
            append((event?.source ?: 0).toString(16).uppercase(Locale.ROOT))
            append(" repeat=")
            append(event?.repeatCount ?: -1)
            append(" flags=0x")
            append((event?.flags ?: 0).toString(16).uppercase(Locale.ROOT))
            if (details.isNotBlank()) {
                append(" ")
                append(details)
            }
        }
        record(context, stage, eventDetails)
    }

    fun snapshot(context: Context): String = synchronized(lock) {
        val file = logFile(context.applicationContext)
        buildString {
            appendLine("Metrolist dudu7 Media-Key-Diagnose")
            appendLine("Version: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})")
            appendLine("Gerät: ${Build.MANUFACTURER} ${Build.MODEL}")
            appendLine("Android: ${Build.VERSION.RELEASE} / SDK ${Build.VERSION.SDK_INT}")
            appendLine("Aufzeichnung: ${if (isEnabled(context)) "EIN" else "AUS"}")
            appendLine("Keine Cookies, Tokens oder vollständigen Stream-URLs enthalten.")
            appendLine("------------------------------------------------------------")
            if (file.isFile && file.length() > 0L) {
                append(file.readText(Charsets.UTF_8))
            } else {
                appendLine("Noch keine Media-Key-Ereignisse aufgezeichnet.")
            }
        }
    }

    fun clear(context: Context) {
        synchronized(lock) {
            logFile(context.applicationContext).delete()
        }
        record(context, "DIAGNOSTICS", "log cleared", force = true)
    }

    fun exportFile(context: Context): File {
        val timestamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(Date())
        val file = File(context.cacheDir, "metrolist-dudu7-media-keys-$timestamp.txt")
        file.writeText(snapshot(context), Charsets.UTF_8)
        return file
    }

    fun Intent.mediaKeyEvent(): KeyEvent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            getParcelableExtra(Intent.EXTRA_KEY_EVENT, KeyEvent::class.java)
        } else {
            @Suppress("DEPRECATION")
            getParcelableExtra(Intent.EXTRA_KEY_EVENT)
        }

    private fun logFile(context: Context): File =
        File(File(context.filesDir, "diagnostics"), "media_keys.log")
}
