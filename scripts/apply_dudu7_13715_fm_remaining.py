#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")

def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker missing in {path}: {old[:160]!r}")
    write(path, text.replace(old, new, 1))

replace_once(
    "app/build.gradle.kts",
    '        versionCode = 1370023\n        versionName = "13.7.14"',
    '        versionCode = 1370024\n        versionName = "13.7.15"',
)

replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt",
    "import java.util.Locale\n",
    "import java.util.Locale\nimport timber.log.Timber\n",
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt",
    'object RadioDnsLogoResolver {\n    private const val USER_AGENT',
    'object RadioDnsLogoResolver {\n    private const val TAG = "RadioDNS"\n    private const val USER_AGENT',
)
replace_once(
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt",
    '''            val lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org"
            val authoritative = dnsAnswers(lookup, 5).firstOrNull()?.trimEnd('.') ?: return@withContext emptyList()
            val srv = dnsAnswers("_radioepg._tcp.$authoritative", 33).mapNotNull(::parseSrv).minByOrNull { it.priority }
                ?: return@withContext emptyList()
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            serviceInformationUrls(srv).forEach { siUrl ->
                val xml = download(siUrl) ?: return@forEach
                val logos = parseServiceInformation(xml, siUrl, bearer)
                if (logos.isNotEmpty()) return@withContext logos.sortedByDescending { it.ranking }
            }
            emptyList()
''',
    '''            val lookup = "$frequencyCode.$piHex.$gcc.fm.radiodns.org"
            Timber.tag(TAG).d("lookup=%s PI=%s ECC=%s GCC=%s", lookup, piHex, resolvedEcc, gcc)
            val authoritative = dnsAnswers(lookup, 5).firstOrNull()?.trimEnd('.')
            if (authoritative.isNullOrBlank()) {
                Timber.tag(TAG).d("No CNAME for %s", lookup)
                return@withContext emptyList()
            }
            val srv = dnsAnswers("_radioepg._tcp.$authoritative", 33).mapNotNull(::parseSrv).minByOrNull { it.priority }
            if (srv == null) {
                Timber.tag(TAG).d("No RadioEPG SRV for %s", authoritative)
                return@withContext emptyList()
            }
            val bearer = "fm:$gcc.$piHex.$frequencyCode"
            Timber.tag(TAG).d("CNAME=%s SRV=%s:%d bearer=%s", authoritative, srv.target, srv.port, bearer)
            serviceInformationUrls(srv).forEach { siUrl ->
                val xml = download(siUrl)
                if (xml == null) {
                    Timber.tag(TAG).d("SPI unavailable %s", siUrl)
                    return@forEach
                }
                val logos = parseServiceInformation(xml, siUrl, bearer)
                if (logos.isNotEmpty()) {
                    Timber.tag(TAG).i("Resolved %d logo(s) for %s via %s", logos.size, bearer, siUrl)
                    return@withContext logos.sortedByDescending { it.ranking }
                }
            }
            Timber.tag(TAG).d("No matching multimedia entry for %s", bearer)
            emptyList()
''',
)

path = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
replace_once(path,
'''        val stereo: Boolean?,
        val pi: Int,
        val pty: Int,
''',
'''        val stereo: Boolean?,
        val pi: Int,
        val ecc: String = "",
        val pty: Int,
''')
replace_once(path,
"    private const val AF_POLL_INTERVAL_MS = 6_000L\n",
"    private const val AF_POLL_INTERVAL_MS = 6_000L\n    private const val AF_SWITCH_COOLDOWN_MS = 20_000L\n")
replace_once(path,
'''    private var lastAfAttemptAt = 0L
''',
'''    private var lastAfAttemptAt = 0L
    private var lastAfSwitchAt = 0L
    private var pendingPresetIdentity: Preset? = null
    private var pendingPs = ""
    private var pendingPsCount = 0
''')
replace_once(path,
'''                persistFrequency(target)
                _state.update {
                    it.copy(
                        isActive = true,
                        isMuted = false,
                        isBusy = false,
                        frequency = target,
                        ps = "",
                        rt = "",
                        stereo = null,
                        pi = 0,
                        ecc = "",
                        alternativeFrequencies = emptyList(),
''',
'''                val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }
                pendingPresetIdentity = null
                pendingPs = ""
                pendingPsCount = 0
                persistFrequency(target)
                _state.update {
                    it.copy(
                        isActive = true,
                        isMuted = false,
                        isBusy = false,
                        frequency = target,
                        ps = presetIdentity?.name.orEmpty(),
                        rt = "",
                        stereo = null,
                        pi = presetIdentity?.pi ?: 0,
                        ecc = presetIdentity?.ecc.orEmpty(),
                        alternativeFrequencies = presetIdentity?.alternativeFrequencies.orEmpty(),
''')
replace_once(path,
'''        scope.launch {
            if (_state.value.isScanning) stopAutoScan()
            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    ps = "",
                    rt = "",
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
                    pty = 0,
                )
            }
''',
'''        scope.launch {
            if (_state.value.isScanning) stopAutoScan()
            val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }
            pendingPresetIdentity = null
            pendingPs = ""
            pendingPsCount = 0
            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    ps = presetIdentity?.name.orEmpty(),
                    rt = "",
                    stereo = null,
                    pi = presetIdentity?.pi ?: 0,
                    ecc = presetIdentity?.ecc.orEmpty(),
                    alternativeFrequencies = presetIdentity?.alternativeFrequencies.orEmpty(),
                    pty = 0,
                )
            }
''')
replace_once(path,
'''                            pi = directPi.takeIf { it > 0 } ?: snapshot.pi,
                            pty = snapshot.pty,
''',
'''                            pi = directPi.takeIf { it > 0 } ?: snapshot.pi,
                            ecc = directEcc.ifBlank { snapshot.ecc },
                            pty = snapshot.pty,
''')
replace_once(path,
'''                    pi = it.pi,
                    alternativeFrequencies = it.alternativeFrequencies,
''',
'''                    pi = it.pi,
                    ecc = it.ecc,
                    alternativeFrequencies = it.alternativeFrequencies,
''')
replace_once(path,
'''                val fm = native ?: return@launch
                val before = _state.value
''',
'''                val fm = native ?: return@launch
                val before = _state.value
                if (System.currentTimeMillis() - lastAfSwitchAt < AF_SWITCH_COOLDOWN_MS) return@launch
''')
replace_once(path,
'''                    Timber.tag(TAG).i("AF switched %.1f -> %.1f for PI=%04X", before.frequency, frequency, before.pi)
                    persistFrequency(frequency)
''',
'''                    Timber.tag(TAG).i("AF switched %.1f -> %.1f for PI=%04X", before.frequency, frequency, before.pi)
                    lastAfSwitchAt = System.currentTimeMillis()
                    persistFrequency(frequency)
''')
replace_once(path,
'''    fun tunePreset(preset: Preset) {
        tune(preset.frequency)
    }
''',
'''    fun tunePreset(preset: Preset) {
        pendingPresetIdentity = preset
        tune(preset.frequency)
    }
''')
replace_once(path,
'''        val ps = runCatching { fm.psString }.getOrDefault("")
        val rt = runCatching { fm.radioText }.getOrDefault("")
''',
'''        val rawPs = runCatching { fm.psString }.getOrDefault("").trim()
        val stablePs =
            when {
                rawPs.isBlank() -> _state.value.ps
                rawPs == _state.value.ps -> {
                    pendingPs = ""
                    pendingPsCount = 0
                    rawPs
                }
                rawPs == pendingPs -> {
                    pendingPsCount += 1
                    if (pendingPsCount >= 2) rawPs else _state.value.ps
                }
                else -> {
                    pendingPs = rawPs
                    pendingPsCount = 1
                    _state.value.ps
                }
            }
        val rt = runCatching { fm.radioText }.getOrDefault("")
''')
replace_once(path,
'''                ps = ps.ifBlank { current.ps },
                rt = rt.ifBlank { current.rt },
''',
'''                ps = stablePs.ifBlank { current.ps },
                rt = rt.ifBlank { current.rt },
''')
replace_once(path,
'''            strongest.copy(
                alternativeFrequencies =
''',
'''            strongest.copy(
                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: strongest.ecc,
                alternativeFrequencies =
''')

path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
replace_once(path,
'''    var editingPreset by remember { mutableStateOf<FytPhysicalRadio.Preset?>(null) }
''',
'''    var editingPreset by remember { mutableStateOf<FytPhysicalRadio.Preset?>(null) }
    var logoPickerPreset by remember { mutableStateOf<FytPhysicalRadio.Preset?>(null) }
''')
replace_once(path,
'''            onSave = { name, frequencies ->
                if (radio.updatePreset(preset, name, frequencies)) {
                    editingPreset = null
                }
            },
        )
    }
}
''',
'''            onSave = { name, frequencies ->
                if (radio.updatePreset(preset, name, frequencies)) {
                    editingPreset = null
                }
            },
            onChooseLogo = {
                logoPickerPreset = preset
                editingPreset = null
            },
        )
    }
    logoPickerPreset?.let { preset ->
        FmLogoPickerDialog(preset = preset, onDismiss = { logoPickerPreset = null })
    }
}
''')
replace_once(path,
'''    onDismiss: () -> Unit,
    onSave: (String, List<Float>) -> Unit,
) {
''',
'''    onDismiss: () -> Unit,
    onSave: (String, List<Float>) -> Unit,
    onChooseLogo: () -> Unit,
) {
''')
replace_once(path,
'''                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
''',
'''                FmStationArtwork(
                    stationName = preset.name,
                    frequency = preset.frequency,
                    pi = preset.pi,
                    ecc = preset.ecc,
                    size = 72.dp,
                )
                OutlinedButton(onClick = onChooseLogo, modifier = Modifier.fillMaxWidth()) {
                    Text("SENDERLOGO AUSWÄHLEN")
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
''')
replace_once(path,
'''            pi = pi,
            size = 56.dp,
''',
'''            pi = pi,
            ecc = preset.ecc,
            size = 56.dp,
''')
replace_once(path,
'''            stationName = result.name,
            frequency = result.frequency,
            size = 54.dp,
''',
'''            stationName = result.name,
            frequency = result.frequency,
            pi = result.pi,
            ecc = result.ecc,
            size = 54.dp,
''')
replace_once(path,
'''                    stationName = state.displayStation,
                    frequency = state.frequency,
                    size = 82.dp,
''',
'''                    stationName = state.displayStation,
                    frequency = state.frequency,
                    pi = state.pi,
                    ecc = state.ecc,
                    size = 82.dp,
''')
replace_once(path,
'''        item { RadioStatusLine(state) }
        item {
            Text(
                text =
                    "FYT ${state.platform.ifBlank { "Dudu7" }} • " +
''',
'''        item { RadioStatusLine(state) }
        item { FmRadioDiagnostics(state) }
        item {
            Text(
                text =
                    "FYT ${state.platform.ifBlank { "Dudu7" }} • " +
''')
replace_once(path,
'''                if (state.pi != 0) append("  •  PI ${state.pi.toString(16).uppercase()}")
''',
'''                if (state.pi != 0) append("  •  PI ${state.pi.toString(16).uppercase()}")
                if (state.ecc.isNotBlank()) append("  •  ECC ${state.ecc.uppercase()}")
''')
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt",
'''                    pi = state.pi,
                    size = artworkSize,
''',
'''                    pi = state.pi,
                    ecc = state.ecc,
                    size = artworkSize,
''')

checks = {
    "app/build.gradle.kts": ["versionCode = 1370024", 'versionName = "13.7.15"'],
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt": [
        'val ecc: String = ""', "AF_SWITCH_COOLDOWN_MS", "pendingPresetIdentity", "pendingPsCount",
        "ecc = directEcc.ifBlank { snapshot.ecc }",
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt": [
        "FmLogoPickerDialog", "FmRadioDiagnostics", "ecc = result.ecc", "onChooseLogo",
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt": ["ecc = state.ecc"],
    "app/src/main/kotlin/com/metrolist/music/radio/RadioDnsLogoResolver.kt": [
        'private const val TAG = "RadioDNS"', "No CNAME", "Resolved %d logo(s)",
    ],
}
for file, needles in checks.items():
    text = read(file)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{file}: missing {missing}")

print("Applied Metrolist dudu7 13.7.15 FM integration patch")
