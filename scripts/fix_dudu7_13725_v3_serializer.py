from pathlib import Path

path = Path(__file__).resolve().parents[1] / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
text = path.read_text(encoding="utf-8")
start = text.index("    private fun persistPresets(presets: List<Preset>) {")
end = text.index("    private fun readPresets(value: String?): List<Preset> {", start)
replacement = r'''    private fun persistPresets(presets: List<Preset>) {
        val normalized = normalizePresets(presets)
        val encoded = normalized.joinToString("\n") { preset ->
            listOf(
                "v3",
                preset.id,
                preset.frequency.toString(),
                preset.name.replace('\n', ' ').replace('\t', ' '),
                preset.pi.toString(),
                preset.ecc.replace('\n', ' ').replace('\t', ' '),
                preset.stationId.replace('\n', ' ').replace('\t', ' '),
            ).joinToString("\t")
        }
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putString(KEY_PRESETS, encoded)
            ?.remove(LEGACY_KEY_PRESETS)
            ?.apply()
    }

'''
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
print("Corrected FM V3 serializer escapes")
