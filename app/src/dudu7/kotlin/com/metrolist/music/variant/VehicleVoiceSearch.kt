package com.metrolist.music.variant

import android.app.Activity
import android.content.ActivityNotFoundException
import android.content.Intent
import android.speech.RecognizerIntent
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.platform.LocalContext
import java.util.Locale

@Composable
fun rememberVehicleVoiceSearch(
    onSearch: (String) -> Unit,
    fallback: () -> Unit,
): () -> Unit {
    val context = LocalContext.current
    val currentOnSearch by rememberUpdatedState(onSearch)
    val launcher =
        rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            if (result.resultCode == Activity.RESULT_OK) {
                result.data
                    ?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    ?.firstOrNull()
                    ?.trim()
                    ?.takeIf(String::isNotEmpty)
                    ?.let(currentOnSearch)
            }
        }

    return remember(context, launcher) {
        {
            val language = Locale.getDefault().toLanguageTag()
            val intent =
                Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, language)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_PREFERENCE, language)
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                    putExtra(RecognizerIntent.EXTRA_PROMPT, "Musik suchen")
                }
            try {
                launcher.launch(intent)
            } catch (_: ActivityNotFoundException) {
                Toast.makeText(
                    context,
                    "Keine Spracherkennung auf diesem Gerät verfügbar",
                    Toast.LENGTH_LONG,
                ).show()
            }
        }
    }
}
