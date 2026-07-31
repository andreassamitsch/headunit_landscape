package com.metrolist.music.playback

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Typeface
import android.os.Bundle
import android.view.Gravity
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.core.content.FileProvider
import com.metrolist.music.BuildConfig

class MediaKeyDiagnosticsActivity : ComponentActivity() {
    private lateinit var logView: TextView
    private lateinit var recordingButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title = "Metrolist Media-Key-Diagnose"
        setContentView(buildContent())
        MediaKeyDiagnostics.record(this, "DIAGNOSTICS", "diagnostics activity opened")
        refresh()
    }

    override fun onResume() {
        super.onResume()
        if (::logView.isInitialized) refresh()
    }

    private fun buildContent(): LinearLayout {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(12), dp(10), dp(12), dp(10))
        }

        val titleView = TextView(this).apply {
            text = "Media-Key-Diagnose"
            textSize = 22f
            setTypeface(typeface, Typeface.BOLD)
        }
        root.addView(titleView)

        root.addView(TextView(this).apply {
            text = "Nach dem Test hier aktualisieren, Text markieren/kopieren oder als TXT teilen."
            textSize = 14f
            setPadding(0, dp(2), 0, dp(8))
        })

        val firstRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        recordingButton = actionButton("AUFZEICHNUNG") {
            MediaKeyDiagnostics.setEnabled(
                this,
                !MediaKeyDiagnostics.isEnabled(this),
            )
            refresh()
        }
        firstRow.addView(recordingButton, weightedParams())
        firstRow.addView(actionButton("AKTUALISIEREN") { refresh() }, weightedParams())
        firstRow.addView(actionButton("ALLES KOPIEREN") { copyAll() }, weightedParams())
        root.addView(firstRow, fullWidthParams())

        val secondRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
        }
        secondRow.addView(actionButton("TXT TEILEN") { shareTxt() }, weightedParams())
        secondRow.addView(actionButton("LOG LÖSCHEN") {
            MediaKeyDiagnostics.clear(this)
            refresh()
        }, weightedParams())
        root.addView(secondRow, fullWidthParams())

        logView = TextView(this).apply {
            textSize = 13f
            typeface = Typeface.MONOSPACE
            setTextIsSelectable(true)
            setPadding(dp(8), dp(8), dp(8), dp(8))
        }
        val scroll = ScrollView(this).apply {
            isFillViewport = true
            addView(
                logView,
                ViewGroup.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                ),
            )
        }
        root.addView(
            scroll,
            LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1f,
            ),
        )
        return root
    }

    private fun refresh() {
        logView.text = MediaKeyDiagnostics.snapshot(this)
        recordingButton.text =
            if (MediaKeyDiagnostics.isEnabled(this)) "AUFZEICHNUNG: EIN" else "AUFZEICHNUNG: AUS"
    }

    private fun copyAll() {
        val text = MediaKeyDiagnostics.snapshot(this)
        val clipboard = getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("Metrolist Media-Key-Diagnose", text))
        Toast.makeText(this, "Diagnose wurde kopiert", Toast.LENGTH_SHORT).show()
    }

    private fun shareTxt() {
        val file = MediaKeyDiagnostics.exportFile(this)
        val uri = FileProvider.getUriForFile(
            this,
            "${BuildConfig.APPLICATION_ID}.FileProvider",
            file,
        )
        val share = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, "Metrolist dudu7 Media-Key-Diagnose")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            clipData = ClipData.newRawUri("Media-Key-Diagnose", uri)
        }
        startActivity(Intent.createChooser(share, "Diagnose teilen"))
    }

    private fun actionButton(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            setOnClickListener { action() }
        }

    private fun weightedParams(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f).apply {
            marginEnd = dp(6)
        }

    private fun fullWidthParams(): LinearLayout.LayoutParams =
        LinearLayout.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT,
        )

    private fun dp(value: Int): Int =
        (value * resources.displayMetrics.density).toInt()
}
