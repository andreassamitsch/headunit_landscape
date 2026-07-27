from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"Patch marker missing in {path}: {old[:180]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/build.gradle.kts",
    '        versionCode = 168\n        versionName = "13.7.9"',
    '        versionCode = 169\n        versionName = "13.7.10"',
)

# ---------------------------------------------------------------------------
# FYT native bridge: use the actual native stereo/RSSI/RDS/AF methods exposed by
# the firmware libfmjni contract. Unknown native methods are always guarded.
# ---------------------------------------------------------------------------
native_path = Path("app/src/dudu7/java/com/android/fmradio/FmNative.java")
native_text = native_path.read_text(encoding="utf-8")

native_declarations_old = '''    public native int setmonostero(int mode);
    public native int getmonostero(int mode);
    public native int switchAntenna(int antenna);
    public native short activeAf();
    public native int setconfig(String config);
'''
native_declarations_new = '''    public native int setmonostero(int mode);
    public native int getmonostero(int mode);
    public native boolean stereoMono();
    public native int readRssi();
    public native short getPI();
    public native byte getECC();
    public native short[] getAFList();
    public native int switchAntenna(int antenna);
    public native short activeAf();
    public native int setconfig(String config);
'''
if native_declarations_new not in native_text:
    if native_declarations_old not in native_text:
        raise SystemExit("FmNative declaration marker missing")
    native_text = native_text.replace(native_declarations_old, native_declarations_new, 1)

get_rssi_old = '''    public int getRssi() {
        if (!libraryLoaded) return 0;
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_RSSI, new Bundle(), output);
            if (result == 0) return output.getInt("rssilevel", 0);
        } catch (Throwable error) {
            Log.d(TAG, "RSSI command unavailable", error);
        }
        return 0;
    }
'''
get_rssi_new = '''    public int getRssi() {
        if (!libraryLoaded) return 0;
        try {
            int direct = readRssi();
            if (direct != 0) return direct;
        } catch (Throwable error) {
            Log.d(TAG, "Direct RSSI command unavailable", error);
        }
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_RSSI, new Bundle(), output);
            if (result == 0 && output.containsKey("rssilevel")) {
                return output.getInt("rssilevel");
            }
        } catch (Throwable error) {
            Log.d(TAG, "RSSI bundle command unavailable", error);
        }
        return 0;
    }
'''
if get_rssi_new not in native_text:
    if get_rssi_old not in native_text:
        raise SystemExit("FmNative getRssi marker missing")
    native_text = native_text.replace(get_rssi_old, get_rssi_new, 1)

stereo_old = '''    public boolean isStereoReceiving() {
        if (!libraryLoaded) return false;
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_MONO_STEREO, new Bundle(), output);
            if (result == 0) {
                return output.getInt("status", output.getInt("value", 0)) == 1;
            }
        } catch (Throwable error) {
            Log.d(TAG, "Stereo command unavailable", error);
        }
        return false;
    }
'''
stereo_new = '''    /**
     * @return 1 for stereo, 0 for confirmed mono, -1 when the firmware exposes
     *         no reliable stereo state. Unknown must never be rendered as Mono.
     */
    public int getStereoState() {
        if (!libraryLoaded) return -1;
        try {
            return stereoMono() ? 1 : 0;
        } catch (Throwable error) {
            Log.d(TAG, "Direct stereoMono command unavailable", error);
        }
        try {
            Bundle output = new Bundle();
            int result = fmsyu_jni(CMD_GET_MONO_STEREO, new Bundle(), output);
            if (result == 0) {
                String[] keys = {"stereo", "isStereo", "monoStereo", "monostereo", "value"};
                for (String key : keys) {
                    if (!output.containsKey(key)) continue;
                    Object raw = output.get(key);
                    if (raw instanceof Boolean) return ((Boolean) raw) ? 1 : 0;
                    if (raw instanceof Number) {
                        int value = ((Number) raw).intValue();
                        if (value == 0 || value == 1) return value;
                        if (value == 2) return 1;
                    }
                }
            }
        } catch (Throwable error) {
            Log.d(TAG, "Stereo bundle command unavailable", error);
        }
        try {
            int value = getmonostero(0);
            if (value == 0 || value == 1) return value;
            if (value == 2) return 1;
        } catch (Throwable error) {
            Log.d(TAG, "Legacy mono/stereo command unavailable", error);
        }
        return -1;
    }

    public boolean isStereoReceiving() {
        return getStereoState() == 1;
    }

    public int getProgramIdentifier() {
        if (!libraryLoaded) return 0;
        try {
            return getPI() & 0xffff;
        } catch (Throwable error) {
            Log.d(TAG, "Direct PI command unavailable", error);
            return 0;
        }
    }

    public String getExtendedCountryCode() {
        if (!libraryLoaded) return "";
        try {
            int value = getECC() & 0xff;
            return value == 0 ? "" : String.format(java.util.Locale.ROOT, "%02x", value);
        } catch (Throwable error) {
            Log.d(TAG, "Direct ECC command unavailable", error);
            return "";
        }
    }

    public float[] getAlternativeFrequencies() {
        if (!libraryLoaded) return new float[0];
        try {
            short[] raw = getAFList();
            if (raw == null || raw.length == 0) return new float[0];
            java.util.ArrayList<Float> values = new java.util.ArrayList<>();
            for (short item : raw) {
                float value = item & 0xffff;
                float decoded;
                if (value >= 875f && value <= 1080f) {
                    decoded = value / 10f;
                } else if (value >= 8750f && value <= 10800f) {
                    decoded = value / 100f;
                } else if (value >= 87500f && value <= 108000f) {
                    decoded = value / 1000f;
                } else {
                    continue;
                }
                if (decoded >= 87.5f && decoded <= 108.0f && !values.contains(decoded)) {
                    values.add(decoded);
                }
            }
            float[] result = new float[values.size()];
            for (int index = 0; index < values.size(); index++) result[index] = values.get(index);
            return result;
        } catch (Throwable error) {
            Log.d(TAG, "AF list command unavailable", error);
            return new float[0];
        }
    }
'''
if stereo_new not in native_text:
    if stereo_old not in native_text:
        raise SystemExit("FmNative stereo marker missing")
    native_text = native_text.replace(stereo_old, stereo_new, 1)

native_path.write_text(native_text, encoding="utf-8")

# ---------------------------------------------------------------------------
# FM backend: tri-state stereo, PI-based station groups, persisted alternative
# frequencies and native AF polling without a guessed RSSI scale.
# ---------------------------------------------------------------------------
radio_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
radio = radio_path.read_text(encoding="utf-8")

model_old = '''    private const val FM_MIN = 87.5f
    private const val FM_MAX = 108.0f
    private const val FM_STEP = 0.1f
    private const val SEEK_RSSI_THRESHOLD = 38
    private const val SCAN_RSSI_THRESHOLD = 36

    data class Preset(
        val frequency: Float,
        val name: String,
        val pi: Int = 0,
        val ecc: String = "",
    )

    data class ScanResult(
        val frequency: Float,
        val name: String,
        val rssi: Int,
        val stereo: Boolean,
        val pi: Int,
        val pty: Int,
        val tp: Boolean,
    )

    data class State(
        val initialized: Boolean = false,
        val libraryLoaded: Boolean = false,
        val isActive: Boolean = false,
        val isMuted: Boolean = false,
        val isBusy: Boolean = false,
        val isScanning: Boolean = false,
        val scanProgress: Float = 0f,
        val scanResults: List<ScanResult> = emptyList(),
        val frequency: Float = 99.7f,
        val ps: String = "",
        val rt: String = "",
        val rssi: Int = 0,
        val stereo: Boolean = false,
        val pi: Int = 0,
        val pty: Int = 0,
        val tp: Boolean = false,
        val ta: Boolean = false,
        val afEnabled: Boolean = true,
        val taEnabled: Boolean = true,
        val regEnabled: Boolean = false,
        val afSupported: Boolean = true,
        val presets: List<Preset> = emptyList(),
        val radioType: String = "",
        val platform: String = "",
        val error: String? = null,
    ) {
        val displayStation: String
            get() = ps.ifBlank { "FM ${formatFrequency(frequency)} MHz" }
    }
'''
model_new = '''    private const val FM_MIN = 87.5f
    private const val FM_MAX = 108.0f
    private const val FM_STEP = 0.1f
    private const val SEEK_RSSI_THRESHOLD = 38
    private const val SCAN_RSSI_THRESHOLD = 36
    private const val AF_POLL_INTERVAL_MS = 6_000L

    data class Preset(
        val frequency: Float,
        val name: String,
        val pi: Int = 0,
        val ecc: String = "",
        val alternativeFrequencies: List<Float> = emptyList(),
    )

    data class ScanResult(
        val frequency: Float,
        val name: String,
        val rssi: Int,
        val stereo: Boolean?,
        val pi: Int,
        val pty: Int,
        val tp: Boolean,
        val alternativeFrequencies: List<Float> = emptyList(),
    )

    data class State(
        val initialized: Boolean = false,
        val libraryLoaded: Boolean = false,
        val isActive: Boolean = false,
        val isMuted: Boolean = false,
        val isBusy: Boolean = false,
        val isScanning: Boolean = false,
        val scanProgress: Float = 0f,
        val scanResults: List<ScanResult> = emptyList(),
        val frequency: Float = 99.7f,
        val ps: String = "",
        val rt: String = "",
        val rssi: Int = 0,
        val stereo: Boolean? = null,
        val pi: Int = 0,
        val ecc: String = "",
        val alternativeFrequencies: List<Float> = emptyList(),
        val pty: Int = 0,
        val tp: Boolean = false,
        val ta: Boolean = false,
        val afEnabled: Boolean = true,
        val taEnabled: Boolean = true,
        val regEnabled: Boolean = false,
        val afSupported: Boolean = true,
        val presets: List<Preset> = emptyList(),
        val radioType: String = "",
        val platform: String = "",
        val error: String? = null,
    ) {
        val displayStation: String
            get() = ps.ifBlank { "FM ${formatFrequency(frequency)} MHz" }
    }
'''
if model_new not in radio:
    if model_old not in radio:
        raise SystemExit("FytPhysicalRadio model marker missing")
    radio = radio.replace(model_old, model_new, 1)

radio = radio.replace(
    "    private var scanJob: Job? = null\n",
    "    private var scanJob: Job? = null\n    private var afJob: Job? = null\n",
    1,
)

radio = radio.replace(
    '''                        frequency = target,
                        ps = "",
                        rt = "",
                        pi = 0,
                        pty = 0,
''',
    '''                        frequency = target,
                        ps = "",
                        rt = "",
                        stereo = null,
                        pi = 0,
                        ecc = "",
                        alternativeFrequencies = emptyList(),
                        pty = 0,
''',
    1,
)

radio = radio.replace(
    '''                    rssi = 0,
                    stereo = false,
                    pi = 0,
''',
    '''                    rssi = 0,
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
''',
    1,
)

radio = radio.replace(
    '''            _state.update { it.copy(isBusy = true, error = null, ps = "", rt = "", pi = 0, pty = 0) }
''',
    '''            _state.update {
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
    1,
)

radio = radio.replace(
    '''            _state.update { it.copy(isBusy = true, error = null, ps = "", rt = "") }
''',
    '''            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    ps = "",
                    rt = "",
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
                )
            }
''',
    1,
)

scan_reset_old = '''                            ps = "",
                            rt = "",
                            pi = 0,
                            pty = 0,
                            tp = false,
'''
scan_reset_new = '''                            ps = "",
                            rt = "",
                            stereo = null,
                            pi = 0,
                            ecc = "",
                            alternativeFrequencies = emptyList(),
                            pty = 0,
                            tp = false,
'''
if scan_reset_new not in radio:
    if scan_reset_old not in radio:
        raise SystemExit("scan reset marker missing")
    radio = radio.replace(scan_reset_old, scan_reset_new, 1)

scan_sample_old = '''                    delay(520)
                    repeat(2) {
                        runCatching { fm.readRds() }
                        delay(90)
                    }
                    val name = runCatching { fm.psString }.getOrDefault("").trim()
                    val rssi = runCatching { fm.rssi }.getOrDefault(0)
                    val stereo = runCatching { fm.isStereoReceiving }.getOrDefault(false)
                    val snapshot = _state.value
                    results +=
                        ScanResult(
                            frequency = frequency,
                            name = name.ifBlank { "FM ${formatFrequency(frequency)}" },
                            rssi = rssi,
                            stereo = stereo,
                            pi = snapshot.pi,
                            pty = snapshot.pty,
                            tp = snapshot.tp,
                        )
                    _state.update { it.copy(scanResults = results.toList()) }
'''
scan_sample_new = '''                    delay(420)
                    repeat(5) {
                        runCatching { fm.readRds() }
                        delay(100)
                    }
                    val name = runCatching { fm.psString }.getOrDefault("").trim()
                    val rssi = runCatching { fm.rssi }.getOrDefault(0)
                    val stereoState = runCatching { fm.stereoState }.getOrDefault(-1)
                    val directPi = runCatching { fm.programIdentifier }.getOrDefault(0)
                    val directEcc = runCatching { fm.extendedCountryCode }.getOrDefault("")
                    val afList =
                        runCatching { fm.alternativeFrequencies.toList() }
                            .getOrDefault(emptyList())
                    val snapshot = _state.value
                    results +=
                        ScanResult(
                            frequency = frequency,
                            name = name.ifBlank { "FM ${formatFrequency(frequency)}" },
                            rssi = rssi,
                            stereo = stereoState.takeIf { it >= 0 }?.let { it == 1 },
                            pi = directPi.takeIf { it > 0 } ?: snapshot.pi,
                            pty = snapshot.pty,
                            tp = snapshot.tp,
                            alternativeFrequencies = afList,
                        )
                    _state.update { it.copy(scanResults = groupScanResults(results)) }
'''
if scan_sample_new not in radio:
    if scan_sample_old not in radio:
        raise SystemExit("scan sample marker missing")
    radio = radio.replace(scan_sample_old, scan_sample_new, 1)

scan_finish_old = '''                        scanResults = results
                            .distinctBy { result -> (result.frequency * 10).roundToInt() }
                            .sortedWith(compareByDescending<ScanResult> { result -> result.rssi }.thenBy { result -> result.frequency }),
'''
scan_finish_new = '''                        scanResults =
                            groupScanResults(results)
                                .sortedWith(
                                    compareByDescending<ScanResult> { result -> result.rssi }
                                        .thenBy { result -> result.frequency },
                                ),
'''
if scan_finish_new not in radio:
    if scan_finish_old not in radio:
        raise SystemExit("scan finish marker missing")
    radio = radio.replace(scan_finish_old, scan_finish_new, 1)

save_scan_old = '''    fun saveScanResults(results: Collection<ScanResult>) {
        if (results.isEmpty()) return
        val additions = results.map { Preset(it.frequency, it.name, it.pi) }
        val updated =
            (_state.value.presets + additions)
                .distinctBy { (it.frequency * 10).roundToInt() }
                .sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }
'''
save_scan_new = '''    fun saveScanResults(results: Collection<ScanResult>) {
        if (results.isEmpty()) return
        val additions =
            results.map {
                Preset(
                    frequency = it.frequency,
                    name = it.name,
                    pi = it.pi,
                    alternativeFrequencies = it.alternativeFrequencies,
                )
            }
        val updated = mergePresets(_state.value.presets + additions).sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }
'''
if save_scan_new not in radio:
    if save_scan_old not in radio:
        raise SystemExit("save scan marker missing")
    radio = radio.replace(save_scan_old, save_scan_new, 1)

af_old = '''    fun requestAlternativeFrequency() {
        scope.launch {
            val fm = native ?: return@launch
            if (!_state.value.isActive || !_state.value.afEnabled || _state.value.isScanning) return@launch
            val raw = runCatching { fm.activeAf() }.getOrElse {
                Timber.tag(TAG).w(it, "AF request failed")
                _state.update { state -> state.copy(afSupported = false) }
                return@launch
            }
            val frequency = decodeFrequency(raw.toFloat())
            if (frequency != null && abs(frequency - _state.value.frequency) >= 0.05f) {
                Timber.tag(TAG).i("AF switched %.1f -> %.1f", _state.value.frequency, frequency)
                persistFrequency(frequency)
                _state.update {
                    it.copy(
                        frequency = frequency,
                        ps = "",
                        rt = "",
                        pi = 0,
                        pty = 0,
                    )
                }
                triggerRdsRead()
            }
        }
    }
'''
af_new = '''    fun requestAlternativeFrequency() {
        if (afJob?.isActive == true) return
        afJob =
            scope.launch {
                val fm = native ?: return@launch
                val before = _state.value
                if (
                    !before.isActive ||
                    !before.afEnabled ||
                    before.isScanning ||
                    before.isBusy ||
                    before.pi <= 0
                ) {
                    return@launch
                }
                val knownAlternatives =
                    runCatching { fm.alternativeFrequencies.toList() }
                        .getOrDefault(emptyList())
                val raw = runCatching { fm.activeAf() }.getOrElse {
                    Timber.tag(TAG).w(it, "AF request failed")
                    _state.update { state -> state.copy(afSupported = false) }
                    return@launch
                }
                val frequency = decodeFrequency(raw.toFloat())
                if (frequency != null && abs(frequency - before.frequency) >= 0.05f) {
                    Timber.tag(TAG).i("AF switched %.1f -> %.1f for PI=%04X", before.frequency, frequency, before.pi)
                    persistFrequency(frequency)
                    _state.update {
                        it.copy(
                            frequency = frequency,
                            rt = "",
                            stereo = null,
                            pi = before.pi,
                            ecc = before.ecc,
                            alternativeFrequencies =
                                normalizeFrequencyList(
                                    before.alternativeFrequencies + knownAlternatives + before.frequency,
                                ),
                        )
                    }
                    updateCurrentPresetIdentity()
                    triggerRdsRead()
                } else if (knownAlternatives.isNotEmpty()) {
                    _state.update {
                        it.copy(
                            alternativeFrequencies =
                                normalizeFrequencyList(it.alternativeFrequencies + knownAlternatives),
                        )
                    }
                    updateCurrentPresetIdentity()
                }
            }
    }
'''
if af_new not in radio:
    if af_old not in radio:
        raise SystemExit("AF marker missing")
    radio = radio.replace(af_old, af_new, 1)

preset_ops_old = '''    fun saveCurrentPreset() {
        val snapshot = _state.value
        val preset = Preset(snapshot.frequency, snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" }, snapshot.pi)
        val updated =
            (snapshot.presets.filterNot { abs(it.frequency - preset.frequency) < 0.05f } + preset)
                .sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    fun removePreset(frequency: Float) {
        val updated = _state.value.presets.filterNot { abs(it.frequency - frequency) < 0.05f }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }
'''
preset_ops_new = '''    fun saveCurrentPreset() {
        val snapshot = _state.value
        val preset =
            Preset(
                frequency = snapshot.frequency,
                name = snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" },
                pi = snapshot.pi,
                ecc = snapshot.ecc,
                alternativeFrequencies = snapshot.alternativeFrequencies,
            )
        val updated = mergePresets(snapshot.presets + preset).sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    fun tunePreset(preset: Preset) {
        tune(preset.frequency)
    }

    fun updatePreset(
        original: Preset,
        name: String,
        frequencies: List<Float>,
    ): Boolean {
        val normalized = normalizeFrequencyList(frequencies)
        if (normalized.isEmpty()) return false
        val replacement =
            original.copy(
                frequency = normalized.first(),
                name = name.trim().ifBlank { original.name },
                alternativeFrequencies = normalized.drop(1),
            )
        val remaining = _state.value.presets.filterNot { samePresetRecord(it, original) }
        val updated = mergePresets(remaining + replacement).sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
        return true
    }

    fun removePreset(preset: Preset) {
        val updated = _state.value.presets.filterNot { samePresetRecord(it, preset) }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    fun removePreset(frequency: Float) {
        val matching = _state.value.presets.firstOrNull { presetContainsFrequency(it, frequency) }
        if (matching != null) {
            removePreset(matching)
        }
    }
'''
if preset_ops_new not in radio:
    if preset_ops_old not in radio:
        raise SystemExit("preset operations marker missing")
    radio = radio.replace(preset_ops_old, preset_ops_new, 1)

poll_condition_old = '''                    if (
                        snapshot.afEnabled &&
                        !snapshot.isScanning &&
                        snapshot.rssi in 1..29 &&
                        now - lastAfAttemptAt >= 8_000
                    ) {
                        lastAfAttemptAt = now
                        requestAlternativeFrequency()
                    }
'''
poll_condition_new = '''                    if (
                        snapshot.afEnabled &&
                        snapshot.pi > 0 &&
                        !snapshot.isScanning &&
                        !snapshot.isBusy &&
                        now - lastAfAttemptAt >= AF_POLL_INTERVAL_MS
                    ) {
                        // activeAf() performs the actual field-strength and PI
                        // validation inside the tuner driver. Do not guess the
                        // vendor-specific RSSI scale in the app.
                        lastAfAttemptAt = now
                        requestAlternativeFrequency()
                    }
'''
if poll_condition_new not in radio:
    if poll_condition_old not in radio:
        raise SystemExit("poll AF marker missing")
    radio = radio.replace(poll_condition_old, poll_condition_new, 1)

poll_tuner_old = '''        val ps = runCatching { fm.psString }.getOrDefault("")
        val rt = runCatching { fm.radioText }.getOrDefault("")
        val rssi = runCatching { fm.rssi }.getOrDefault(_state.value.rssi)
        val stereo = runCatching { fm.isStereoReceiving }.getOrDefault(_state.value.stereo)
        _state.update { current ->
            current.copy(
                ps = ps.ifBlank { current.ps },
                rt = rt.ifBlank { current.rt },
                rssi = rssi,
                stereo = stereo,
            )
        }
        updateCurrentPresetIdentity()
'''
poll_tuner_new = '''        val ps = runCatching { fm.psString }.getOrDefault("")
        val rt = runCatching { fm.radioText }.getOrDefault("")
        val rssi = runCatching { fm.rssi }.getOrDefault(_state.value.rssi)
        val stereoState = runCatching { fm.stereoState }.getOrDefault(-1)
        val directPi = runCatching { fm.programIdentifier }.getOrDefault(0)
        val directEcc = runCatching { fm.extendedCountryCode }.getOrDefault("")
        val afList =
            runCatching { fm.alternativeFrequencies.toList() }
                .getOrDefault(emptyList())
        _state.update { current ->
            current.copy(
                ps = ps.ifBlank { current.ps },
                rt = rt.ifBlank { current.rt },
                rssi = rssi,
                stereo = stereoState.takeIf { it >= 0 }?.let { it == 1 } ?: current.stereo,
                pi = directPi.takeIf { it > 0 } ?: current.pi,
                ecc = directEcc.ifBlank { current.ecc },
                alternativeFrequencies =
                    if (afList.isNotEmpty()) {
                        normalizeFrequencyList(current.alternativeFrequencies + afList)
                    } else {
                        current.alternativeFrequencies
                    },
            )
        }
        updateCurrentPresetIdentity()
'''
if poll_tuner_new not in radio:
    if poll_tuner_old not in radio:
        raise SystemExit("poll tuner marker missing")
    radio = radio.replace(poll_tuner_old, poll_tuner_new, 1)

identity_old = '''    private fun updateCurrentPresetIdentity() {
        val snapshot = _state.value
        if (snapshot.pi <= 0) return
        var changed = false
        val updated =
            snapshot.presets.map { preset ->
                if (abs(preset.frequency - snapshot.frequency) >= 0.05f) {
                    preset
                } else {
                    val updatedName = snapshot.ps.trim().takeIf { it.isNotBlank() } ?: preset.name
                    val updatedPreset = preset.copy(name = updatedName, pi = snapshot.pi)
                    if (updatedPreset != preset) changed = true
                    updatedPreset
                }
            }
        if (changed) {
            persistPresets(updated)
            _state.update { it.copy(presets = updated) }
        }
    }

    private fun persistPresets(presets: List<Preset>) {
        val encoded =
            presets.joinToString("\n") { preset ->
                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}\t${preset.pi}\t${preset.ecc}"
            }
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putString(KEY_PRESETS, encoded)
            ?.apply()
    }

    private fun readPresets(value: String?): List<Preset> =
        value
            .orEmpty()
            .lineSequence()
            .mapNotNull { line ->
                val parts = line.split('\t', limit = 4)
                val frequency = parts.firstOrNull()?.toFloatOrNull() ?: return@mapNotNull null
                Preset(
                    frequency = normalizeFrequency(frequency),
                    name = parts.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" },
                    pi = parts.getOrNull(2)?.toIntOrNull() ?: 0,
                    ecc = parts.getOrNull(3).orEmpty(),
                )
            }.distinctBy { it.frequency }
            .sortedBy { it.frequency }
            .toList()
'''
identity_new = '''    private fun updateCurrentPresetIdentity() {
        val snapshot = _state.value
        val index =
            snapshot.presets.indexOfFirst {
                presetMatches(it, snapshot.frequency, snapshot.pi)
            }
        if (index < 0) return
        val current = snapshot.presets[index]
        val allFrequencies =
            normalizeFrequencyList(
                presetFrequencies(current) +
                    snapshot.alternativeFrequencies +
                    snapshot.frequency,
            )
        val primary =
            current.frequency.takeIf { candidate ->
                allFrequencies.any { abs(it - candidate) < 0.05f }
            } ?: allFrequencies.first()
        val updatedPreset =
            current.copy(
                frequency = primary,
                name = snapshot.ps.trim().takeIf { it.isNotBlank() } ?: current.name,
                pi = snapshot.pi.takeIf { it > 0 } ?: current.pi,
                ecc = snapshot.ecc.ifBlank { current.ecc },
                alternativeFrequencies =
                    allFrequencies.filterNot { abs(it - primary) < 0.05f },
            )
        val changedList =
            snapshot.presets.toMutableList().apply {
                this[index] = updatedPreset
            }
        val updated = mergePresets(changedList).sortedBy { it.frequency }
        if (updated != snapshot.presets) {
            persistPresets(updated)
            _state.update { it.copy(presets = updated) }
        }
    }

    private fun persistPresets(presets: List<Preset>) {
        val encoded =
            mergePresets(presets).joinToString("\n") { preset ->
                val alternatives =
                    preset.alternativeFrequencies.joinToString(",") { formatFrequency(it) }
                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}\t${preset.pi}\t${preset.ecc}\t$alternatives"
            }
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putString(KEY_PRESETS, encoded)
            ?.apply()
    }

    private fun readPresets(value: String?): List<Preset> =
        mergePresets(
            value
                .orEmpty()
                .lineSequence()
                .mapNotNull { line ->
                    val parts = line.split('\t', limit = 5)
                    val frequency = parts.firstOrNull()?.toFloatOrNull() ?: return@mapNotNull null
                    val alternatives =
                        parts
                            .getOrNull(4)
                            .orEmpty()
                            .split(',')
                            .mapNotNull(String::toFloatOrNull)
                    Preset(
                        frequency = normalizeFrequency(frequency),
                        name = parts.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" },
                        pi = parts.getOrNull(2)?.toIntOrNull() ?: 0,
                        ecc = parts.getOrNull(3).orEmpty(),
                        alternativeFrequencies = alternatives,
                    )
                }.toList(),
        ).sortedBy { it.frequency }

    fun presetFrequencies(preset: Preset): List<Float> =
        normalizeFrequencyList(listOf(preset.frequency) + preset.alternativeFrequencies)

    fun scanFrequencies(result: ScanResult): List<Float> =
        normalizeFrequencyList(listOf(result.frequency) + result.alternativeFrequencies)

    fun presetContainsFrequency(
        preset: Preset,
        frequency: Float,
    ): Boolean = presetFrequencies(preset).any { abs(it - frequency) < 0.05f }

    fun presetMatches(
        preset: Preset,
        frequency: Float,
        pi: Int,
    ): Boolean =
        presetContainsFrequency(preset, frequency) ||
            (pi > 0 && preset.pi > 0 && samePi(pi, preset.pi))

    fun stablePresetKey(preset: Preset): String =
        when {
            preset.pi > 0 -> "pi:${(preset.pi and 0xffff).toString(16).padStart(4, '0')}"
            usefulStationIdentity(preset.name).isNotBlank() -> "name:${usefulStationIdentity(preset.name)}"
            else -> "freq:${frequencyKey(preset.frequency)}"
        }

    fun formatFrequencies(values: List<Float>): String =
        normalizeFrequencyList(values).joinToString(" / ") { "${formatFrequency(it)} MHz" }

    private fun groupScanResults(results: Collection<ScanResult>): List<ScanResult> {
        val groups = mutableListOf<MutableList<ScanResult>>()
        results.forEach { result ->
            val group =
                groups.firstOrNull { existing ->
                    sameScanStation(existing.first(), result)
                }
            if (group == null) {
                groups += mutableListOf(result)
            } else {
                group += result
            }
        }
        return groups.map { group ->
            val strongest = group.maxByOrNull { it.rssi } ?: group.first()
            val frequencies =
                normalizeFrequencyList(
                    group.flatMap(::scanFrequencies),
                )
            strongest.copy(
                alternativeFrequencies =
                    frequencies.filterNot { abs(it - strongest.frequency) < 0.05f },
                stereo =
                    when {
                        group.any { it.stereo == true } -> true
                        group.any { it.stereo == false } -> false
                        else -> null
                    },
            )
        }
    }

    private fun mergePresets(presets: Collection<Preset>): List<Preset> {
        val groups = mutableListOf<MutableList<Preset>>()
        presets.forEach { preset ->
            val normalized =
                preset.copy(
                    frequency = normalizeFrequency(preset.frequency),
                    alternativeFrequencies =
                        normalizeFrequencyList(preset.alternativeFrequencies)
                            .filterNot { abs(it - preset.frequency) < 0.05f },
                )
            val group = groups.firstOrNull { existing -> samePresetStation(existing.first(), normalized) }
            if (group == null) {
                groups += mutableListOf(normalized)
            } else {
                group += normalized
            }
        }
        return groups.map { group ->
            val first = group.first()
            val frequencies = normalizeFrequencyList(group.flatMap(::presetFrequencies))
            val primary =
                first.frequency.takeIf { value ->
                    frequencies.any { abs(it - value) < 0.05f }
                } ?: frequencies.first()
            first.copy(
                frequency = primary,
                name =
                    group
                        .map { it.name.trim() }
                        .firstOrNull { usefulStationIdentity(it).isNotBlank() }
                        ?: first.name,
                pi = group.firstOrNull { it.pi > 0 }?.pi ?: first.pi,
                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
                alternativeFrequencies =
                    frequencies.filterNot { abs(it - primary) < 0.05f },
            )
        }
    }

    private fun samePresetStation(
        first: Preset,
        second: Preset,
    ): Boolean {
        if (presetFrequencies(first).any { firstFrequency ->
                presetFrequencies(second).any { secondFrequency -> abs(firstFrequency - secondFrequency) < 0.05f }
            }
        ) {
            return true
        }
        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        val left = usefulStationIdentity(first.name)
        val right = usefulStationIdentity(second.name)
        return left.isNotBlank() && left == right
    }

    private fun samePresetRecord(
        first: Preset,
        second: Preset,
    ): Boolean =
        stablePresetKey(first) == stablePresetKey(second) ||
            presetFrequencies(first).any { frequency -> presetContainsFrequency(second, frequency) }

    private fun sameScanStation(
        first: ScanResult,
        second: ScanResult,
    ): Boolean {
        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        val left = usefulStationIdentity(first.name)
        val right = usefulStationIdentity(second.name)
        return left.isNotBlank() && left == right
    }

    private fun usefulStationIdentity(value: String): String {
        val normalized =
            java.text.Normalizer
                .normalize(value, java.text.Normalizer.Form.NFD)
                .replace(Regex("\\p{Mn}+"), "")
                .lowercase(java.util.Locale.ROOT)
                .replace("&", " and ")
                .replace(Regex("[^a-z0-9]+"), " ")
                .trim()
        if (normalized.isBlank()) return ""
        if (normalized.matches(Regex("fm \\d{2,3}(?: \\d)?"))) return ""
        return normalized.takeUnless {
            it in setOf("fm", "radio", "antennenempfang", "physischer antennenempfang")
        }.orEmpty()
    }

    private fun samePi(
        first: Int,
        second: Int,
    ): Boolean = (first and 0xffff) == (second and 0xffff)

    private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()

    private fun normalizeFrequencyList(values: Collection<Float>): List<Float> =
        values
            .asSequence()
            .filter { it.isFinite() && it in FM_MIN..FM_MAX }
            .map(::normalizeFrequency)
            .distinctBy(::frequencyKey)
            .sorted()
            .toList()
'''
if identity_new not in radio:
    if identity_old not in radio:
        raise SystemExit("identity/persistence marker missing")
    radio = radio.replace(identity_old, identity_new, 1)

radio = radio.replace(
    '''                14 -> {
                    _state.update { it.copy(pi = value1) }
                    updateCurrentPresetIdentity()
                }
''',
    '''                14 -> {
                    _state.update { it.copy(pi = value1 and 0xffff) }
                    updateCurrentPresetIdentity()
                }
''',
    1,
)

radio_path.write_text(radio, encoding="utf-8")

# ---------------------------------------------------------------------------
# Stable favourite ordering by station identity instead of one frequency.
# ---------------------------------------------------------------------------
order_content = r'''package com.metrolist.music.radio.fyt

import android.content.Context
import kotlin.math.abs
import kotlin.math.roundToInt

/** Keeps FM-favourite order stable while AF changes the currently used frequency. */
object FmPresetOrderStore {
    private const val PREFS = "dudu7_physical_radio"
    private const val KEY_ORDER = "preset_order_v2"
    private const val LEGACY_KEY_ORDER = "preset_order"

    fun ordered(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ): List<FytPhysicalRadio.Preset> {
        if (presets.isEmpty()) return emptyList()
        val preferences = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val storedKeys =
            preferences
                .getString(KEY_ORDER, null)
                .orEmpty()
                .lineSequence()
                .map(String::trim)
                .filter(String::isNotBlank)
                .distinct()
                .toList()
        val legacyFrequencies =
            preferences
                .getString(LEGACY_KEY_ORDER, null)
                .orEmpty()
                .split(',')
                .mapNotNull(String::toIntOrNull)
                .distinct()

        val ordered = mutableListOf<FytPhysicalRadio.Preset>()
        storedKeys.forEach { key ->
            presets.firstOrNull {
                FytPhysicalRadio.stablePresetKey(it) == key && ordered.none { existing -> samePreset(existing, it) }
            }?.let(ordered::add)
        }
        legacyFrequencies.forEach { key ->
            presets.firstOrNull {
                frequencyKey(it.frequency) == key && ordered.none { existing -> samePreset(existing, it) }
            }?.let(ordered::add)
        }
        val missing = presets.filterNot { preset -> ordered.any { samePreset(it, preset) } }
        return ordered + missing
    }

    fun persist(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ) {
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ORDER, presets.joinToString("\n") { FytPhysicalRadio.stablePresetKey(it) })
            .remove(LEGACY_KEY_ORDER)
            .apply()
    }

    fun remove(
        context: Context,
        preset: FytPhysicalRadio.Preset,
        remainingPresets: List<FytPhysicalRadio.Preset>,
    ) {
        persist(context, remainingPresets.filterNot { samePreset(it, preset) })
    }

    private fun samePreset(
        first: FytPhysicalRadio.Preset,
        second: FytPhysicalRadio.Preset,
    ): Boolean =
        FytPhysicalRadio.stablePresetKey(first) == FytPhysicalRadio.stablePresetKey(second) ||
            FytPhysicalRadio.presetFrequencies(first).any { frequency ->
                FytPhysicalRadio.presetContainsFrequency(second, frequency)
            }

    private fun frequencyKey(value: Float): Int = (value * 10f).roundToInt()

    fun sameFrequency(
        first: Float,
        second: Float,
    ): Boolean = abs(first - second) < 0.05f
}

fun FytPhysicalRadio.tuneAdjacentFavourite(
    context: Context,
    next: Boolean,
) {
    val snapshot = state.value
    val favourites = FmPresetOrderStore.ordered(context, snapshot.presets)
    if (favourites.isEmpty()) {
        seek(next)
        return
    }

    val currentIndex =
        favourites.indexOfFirst {
            FytPhysicalRadio.presetMatches(it, snapshot.frequency, snapshot.pi)
        }
    val targetIndex =
        when {
            currentIndex < 0 && next -> 0
            currentIndex < 0 -> favourites.lastIndex
            next -> (currentIndex + 1) % favourites.size
            else -> (currentIndex - 1 + favourites.size) % favourites.size
        }
    tunePreset(favourites[targetIndex])
}
'''
Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt").write_text(
    order_content,
    encoding="utf-8",
)

# ---------------------------------------------------------------------------
# FM logo identity follows PI across AF changes.
# ---------------------------------------------------------------------------
art_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmStationArtwork.kt")
art = art_path.read_text(encoding="utf-8")
art = art.replace(
    '''    private fun cacheKey(stationName: String, frequency: Float, pi: Int): String {
        val identity = if (pi > 0) "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}" else normalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }
''',
    '''    private fun cacheKey(stationName: String, frequency: Float, pi: Int): String {
        if (pi > 0) return "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}"
        val identity = normalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }
''',
    1,
)
art = art.replace(
    '''    val artworkKey = remember(stationName, frequency, pi) { "${stationName.trim()}-${(frequency * 100f).roundToInt()}-$pi" }
''',
    '''    val artworkKey =
        remember(stationName, frequency, pi) {
            if (pi > 0) {
                "pi-${(pi and 0xffff).toString(16)}"
            } else {
                "${stationName.trim()}-${(frequency * 100f).roundToInt()}"
            }
        }
''',
    1,
)
art_path.write_text(art, encoding="utf-8")

# ---------------------------------------------------------------------------
# FM screen: long-press edits favourites; no user-facing mute; grouped station
# frequencies are visible and editable.
# ---------------------------------------------------------------------------
screen_path = Path("app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt")
screen = screen_path.read_text(encoding="utf-8")

screen = screen.replace(
    "import androidx.compose.material3.Button\n",
    "import androidx.compose.material3.AlertDialog\nimport androidx.compose.material3.Button\n",
    1,
)
screen = screen.replace(
    '''    var section by remember { mutableStateOf(PhysicalRadioSection.FAVOURITES) }
    var frequencyInput by remember { mutableStateOf(FytPhysicalRadio.formatFrequency(state.frequency)) }
''',
    '''    var section by remember { mutableStateOf(PhysicalRadioSection.FAVOURITES) }
    var frequencyInput by remember { mutableStateOf(FytPhysicalRadio.formatFrequency(state.frequency)) }
    var editingPreset by remember { mutableStateOf<FytPhysicalRadio.Preset?>(null) }
''',
    1,
)

screen = screen.replace(
    '''            if (orderedPresets.map { it.frequency } != ordered.map { it.frequency }) {
''',
    '''            if (orderedPresets != ordered) {
''',
    1,
)

screen = screen.replace(
    '''                            key = { _, preset -> "fm-${(preset.frequency * 10).toInt()}" },
                        ) { _, preset ->
                            ReorderableItem(reorderState, key = "fm-${(preset.frequency * 10).toInt()}") {
                                val isActive =
                                    state.isActive &&
                                        FmPresetOrderStore.sameFrequency(state.frequency, preset.frequency)
''',
    '''                            key = { _, preset -> FytPhysicalRadio.stablePresetKey(preset) },
                        ) { _, preset ->
                            ReorderableItem(reorderState, key = FytPhysicalRadio.stablePresetKey(preset)) {
                                val isActive =
                                    state.isActive &&
                                        FytPhysicalRadio.presetMatches(preset, state.frequency, state.pi)
''',
    1,
)

screen = screen.replace(
    '''                                    isActive = isActive,
                                    isMuted = isActive && state.isMuted,
                                    onPlay = {
                                        if (isActive) {
                                            radio.toggleMute()
                                        } else {
                                            playerConnection?.pause()
                                            radio.tune(preset.frequency)
                                        }
                                    },
                                    onDelete = {
                                        val remaining =
                                            orderedPresets.filterNot {
                                                FmPresetOrderStore.sameFrequency(it.frequency, preset.frequency)
                                            }
                                        orderedPresets.clear()
                                        orderedPresets.addAll(remaining)
                                        FmPresetOrderStore.persist(context, remaining)
                                        radio.removePreset(preset.frequency)
                                    },
''',
    '''                                    isActive = isActive,
                                    onPlay = {
                                        if (!isActive) {
                                            playerConnection?.pause()
                                            radio.tunePreset(preset)
                                        }
                                    },
                                    onEdit = { editingPreset = preset },
                                    onDelete = {
                                        val remaining = orderedPresets.filterNot { it == preset }
                                        orderedPresets.clear()
                                        orderedPresets.addAll(remaining)
                                        FmPresetOrderStore.persist(context, remaining)
                                        radio.removePreset(preset)
                                    },
''',
    1,
)

screen = screen.replace(
    '''        }
    }
}

@Composable
private fun EmptyFmFavourites''',
    '''        }
    }

    editingPreset?.let { preset ->
        FmPresetEditorDialog(
            preset = preset,
            onDismiss = { editingPreset = null },
            onSave = { name, frequencies ->
                if (radio.updatePreset(preset, name, frequencies)) {
                    editingPreset = null
                }
            },
        )
    }
}

@Composable
private fun EmptyFmFavourites''',
    1,
)

screen = screen.replace(
    '''    isActive: Boolean,
    isMuted: Boolean,
    onPlay: () -> Unit,
    onDelete: () -> Unit,
''',
    '''    isActive: Boolean,
    onPlay: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
''',
    1,
)
screen = screen.replace(
    '''                ).combinedClickable(onClick = onPlay, onLongClick = onPlay)
''',
    '''                ).combinedClickable(onClick = onPlay, onLongClick = onEdit)
''',
    1,
)
screen = screen.replace(
    '''            Text(
                text = "${FytPhysicalRadio.formatFrequency(preset.frequency)} MHz",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
''',
    '''            Text(
                text = FytPhysicalRadio.formatFrequencies(FytPhysicalRadio.presetFrequencies(preset)),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
''',
    1,
)
screen = screen.replace(
    '''                text = if (isMuted) "STUMM" else "● LÄUFT",
''',
    '''                text = "● LÄUFT",
''',
    1,
)

screen = screen.replace(
    '''                    append("${FytPhysicalRadio.formatFrequency(result.frequency)} MHz")
                    append("  •  RSSI ${result.rssi}")
                    append(if (result.stereo) "  •  Stereo" else "  •  Mono")
''',
    '''                    append(FytPhysicalRadio.formatFrequencies(FytPhysicalRadio.scanFrequencies(result)))
                    append("  •  RSSI ${result.rssi}")
                    result.stereo?.let { append(if (it) "  •  Stereo" else "  •  Mono") }
''',
    1,
)

screen = screen.replace(
    '''    val isFavourite =
        state.presets.any { FmPresetOrderStore.sameFrequency(it.frequency, state.frequency) }
''',
    '''    val currentPreset =
        state.presets.firstOrNull {
            FytPhysicalRadio.presetMatches(it, state.frequency, state.pi)
        }
    val isFavourite = currentPreset != null
''',
    1,
)

mute_button = '''                OutlinedButton(
                    onClick = radio::toggleMute,
                    enabled = state.isActive && !state.isBusy,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(
                        painter = painterResource(if (state.isMuted) R.drawable.volume_off else R.drawable.volume_up),
                        contentDescription = null,
                    )
                    Text(if (state.isMuted) "STUMM" else "TON", modifier = Modifier.padding(start = 6.dp))
                }
'''
if mute_button in screen:
    screen = screen.replace(mute_button, "", 1)

screen = screen.replace(
    '''                        if (isFavourite) {
                            val remaining =
                                state.presets.filterNot {
                                    FmPresetOrderStore.sameFrequency(it.frequency, state.frequency)
                                }
                            radio.removePreset(state.frequency)
                            FmPresetOrderStore.persist(context, remaining)
                        } else {
''',
    '''                        if (isFavourite) {
                            val preset = currentPreset ?: return@OutlinedButton
                            val remaining = state.presets.filterNot { it == preset }
                            radio.removePreset(preset)
                            FmPresetOrderStore.persist(context, remaining)
                        } else {
''',
    1,
)

screen = screen.replace(
    '''                append(if (state.stereo) "  •  Stereo" else "  •  Mono")
''',
    '''                state.stereo?.let { append(if (it) "  •  Stereo" else "  •  Mono") }
''',
    1,
)

editor_dialog = r'''
@Composable
private fun FmPresetEditorDialog(
    preset: FytPhysicalRadio.Preset,
    onDismiss: () -> Unit,
    onSave: (String, List<Float>) -> Unit,
) {
    var name by remember(preset) { mutableStateOf(preset.name) }
    var frequencies by
        remember(preset) {
            mutableStateOf(
                FytPhysicalRadio
                    .presetFrequencies(preset)
                    .joinToString("; ") { FytPhysicalRadio.formatFrequency(it) },
            )
        }
    var error by remember(preset) { mutableStateOf<String?>(null) }

    fun submit() {
        val tokens =
            frequencies
                .split(';', ',')
                .map(String::trim)
                .filter(String::isNotBlank)
        val parsed = tokens.mapNotNull { value -> value.replace(',', '.').toFloatOrNull() }
        when {
            name.isBlank() -> error = "Sendername fehlt"
            parsed.size != tokens.size -> error = "Mindestens eine Frequenz ist ungültig"
            parsed.isEmpty() -> error = "Mindestens eine Frequenz angeben"
            parsed.any { it !in 87.5f..108.0f } -> error = "Frequenzen müssen zwischen 87,5 und 108,0 MHz liegen"
            else -> onSave(name.trim(), parsed)
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("FM-Favorit bearbeiten") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Sendername") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = frequencies,
                    onValueChange = { frequencies = it },
                    label = { Text("Frequenzen, durch Semikolon getrennt") },
                    supportingText = { Text("Beispiel: 99,4; 103,2") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(),
                )
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = { Button(onClick = ::submit) { Text("Speichern") } },
        dismissButton = { OutlinedButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

'''
marker = "@Composable\nprivate fun EmptyFmFavourites"
if "private fun FmPresetEditorDialog(" not in screen:
    if marker not in screen:
        raise SystemExit("FM editor insertion marker missing")
    screen = screen.replace(marker, editor_dialog + marker, 1)

screen_path.write_text(screen, encoding="utf-8")

# ---------------------------------------------------------------------------
# Main FM player: play/power-off instead of fake mute, remove ±0.1 controls,
# and only display mono/stereo when the native state is known.
# ---------------------------------------------------------------------------
pane_path = Path("app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt")
pane = pane_path.read_text(encoding="utf-8")

pane = pane.replace(
    '''    val isStationFavourite =
        remember(state.frequency, state.presets) {
            state.presets.any { FmPresetOrderStore.sameFrequency(it.frequency, state.frequency) }
        }
''',
    '''    val currentPreset =
        remember(state.frequency, state.pi, state.presets) {
            state.presets.firstOrNull {
                FytPhysicalRadio.presetMatches(it, state.frequency, state.pi)
            }
        }
    val isStationFavourite = currentPreset != null
''',
    1,
)

pane = pane.replace(
    '''                    } else {
                        radio.toggleMute()
                    }
''',
    '''                    } else {
                        radio.powerOff()
                    }
''',
    1,
)

pane = pane.replace(
    '''                            when {
                                !state.isActive -> R.drawable.play
                                state.isMuted -> R.drawable.volume_off
                                else -> R.drawable.pause
                            },
                        ),
                    contentDescription = if (state.isMuted) "Radio einschalten" else "Radio stummschalten",
''',
    '''                            if (!state.isActive) R.drawable.play else R.drawable.pause,
                        ),
                    contentDescription = if (state.isActive) "FM-Radio ausschalten" else "FM-Radio einschalten",
''',
    1,
)

pane = pane.replace(
    '''            IconButton(onClick = { radio.step(false) }, enabled = !state.isBusy) {
                Text("−0,1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
''',
    "",
    1,
)
pane = pane.replace(
    '''            IconButton(onClick = { radio.step(true) }, enabled = !state.isBusy) {
                Text("+0,1", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            }
''',
    "",
    1,
)

pane = pane.replace(
    '''                    if (isStationFavourite) {
                        val remaining = state.presets.filterNot {
                            FmPresetOrderStore.sameFrequency(it.frequency, state.frequency)
                        }
                        radio.removePreset(state.frequency)
                        FmPresetOrderStore.persist(context, remaining)
                    } else {
''',
    '''                    if (isStationFavourite) {
                        val preset = currentPreset ?: return@IconButton
                        val remaining = state.presets.filterNot { it == preset }
                        radio.removePreset(preset)
                        FmPresetOrderStore.persist(context, remaining)
                    } else {
''',
    1,
)

pane = pane.replace(
    '''                    append(if (state.stereo) " • Stereo" else " • Mono")
''',
    '''                    state.stereo?.let { append(if (it) " • Stereo" else " • Mono") }
''',
    1,
)

pane_path.write_text(pane, encoding="utf-8")

print("Applied Dudu7 13.7.10 FM favourite editing, stereo, PI grouping and AF fixes")
