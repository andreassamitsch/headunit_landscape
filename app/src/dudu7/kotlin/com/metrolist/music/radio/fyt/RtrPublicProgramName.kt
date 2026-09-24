package com.metrolist.music.radio.fyt

import java.text.Normalizer
import java.util.Locale

/** Converts administrative RTR labels into the public programme name used for UI and logos. */
object RtrPublicProgramName {
    fun resolve(rawProgram: String, broadcaster: String = "", coverageName: String = ""): String {
        val raw = rawProgram.trim()
        val combined = normalize("$raw $broadcaster $coverageName")
        return when {
            combined.contains("steiermark") && combined.contains("oe2") -> "Radio Steiermark"
            combined.contains("kaernten") && combined.contains("oe2") -> "Radio Kärnten"
            combined.contains("burgenland") && combined.contains("oe2") -> "Radio Burgenland"
            combined.contains("niederoesterreich") && combined.contains("oe2") -> "Radio Niederösterreich"
            combined.contains("oberoesterreich") && combined.contains("oe2") -> "Radio Oberösterreich"
            combined.contains("salzburg") && combined.contains("oe2") -> "Radio Salzburg"
            combined.contains("tirol") && combined.contains("oe2") -> "Radio Tirol"
            combined.contains("vorarlberg") && combined.contains("oe2") -> "Radio Vorarlberg"
            combined.contains("wien") && combined.contains("oe2") -> "Radio Wien"
            else -> raw
        }
    }

    private fun normalize(value: String): String {
        val transliterated = value.lowercase(Locale.GERMAN)
            .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
        return Normalizer.normalize(transliterated, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
    }
}
