package com.metrolist.music.radio.fyt

import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Handler
import android.os.Looper
import com.android.fmradio.FmNative
import com.android.fmradio.FmService
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import timber.log.Timber
import java.lang.reflect.Method
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Independent physical FM backend for FYT/Dudu7 head units.
 *
 * It talks directly to the firmware-provided libfmjni.so and TWUtil MCU bridge;
 * NavRadio+ is neither referenced nor required at runtime.
 */
object FytPhysicalRadio {
    private const val TAG = "FytPhysicalRadio"
    private const val PREFS = "dudu7_physical_radio"
    private const val KEY_FREQUENCY = "frequency"
    private const val KEY_PRESETS = "presets"
    private const val KEY_AF = "af_enabled"
    private const val KEY_TA = "ta_enabled"
    private const val KEY_REG = "reg_enabled"
    private const val FM_MIN = 87.5f
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

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val lock = Any()
    private val _state = MutableStateFlow(State())
    val state: StateFlow<State> = _state.asStateFlow()

    private var appContext: Context? = null
    private var native: FmNative? = null
    private var twUtil: TwUtilBridge? = null
    private var pollingJob: Job? = null
    private var scanJob: Job? = null
    private var afJob: Job? = null
    private var audioManager: AudioManager? = null
    private var focusRequest: AudioFocusRequest? = null
    private var lastAfAttemptAt = 0L

    fun get(context: Context): FytPhysicalRadio {
        initialize(context)
        return this
    }

    fun initialize(context: Context) {
        if (_state.value.initialized) return
        synchronized(lock) {
            if (_state.value.initialized) return
            val applicationContext = context.applicationContext
            appContext = applicationContext
            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            val frequency = normalizeFrequency(prefs.getFloat(KEY_FREQUENCY, 99.7f))
            native = FmNative.getInstance()
            FmNative.initAudio(applicationContext)
            twUtil = TwUtilBridge()
            audioManager = applicationContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            _state.value =
                State(
                    initialized = true,
                    libraryLoaded = FmNative.isLibraryLoaded(),
                    frequency = frequency,
                    presets = readPresets(prefs.getString(KEY_PRESETS, null)),
                    afEnabled = prefs.getBoolean(KEY_AF, true),
                    taEnabled = prefs.getBoolean(KEY_TA, true),
                    regEnabled = prefs.getBoolean(KEY_REG, false),
                    radioType = systemProperty("sys.fyt.radio_type"),
                    platform = systemProperty("ro.product.board").ifBlank { systemProperty("ro.board.platform") },
                    error = if (FmNative.isLibraryLoaded()) null else "FYT-Firmwarebibliothek libfmjni.so konnte nicht geladen werden",
                )
        }
    }

    fun powerOn(frequency: Float = _state.value.frequency) {
        scope.launch {
            synchronized(lock) {
                if (_state.value.isBusy) return@launch
                _state.update { it.copy(isBusy = true, error = null) }
            }
            val target = normalizeFrequency(frequency)
            val context = appContext
            val fm = native
            if (context == null || fm == null || !FmNative.isLibraryLoaded()) {
                _state.update { it.copy(isBusy = false, error = "FYT-Tuner ist nicht verfügbar") }
                return@launch
            }

            try {
                requestAudioFocus()
                FytAudioRouter.prepare(context)
                installRdsListener()

                twUtil?.open()
                twUtil?.initRadioSequence()
                delay(150)
                twUtil?.radioOnFm()
                delay(100)
                twUtil?.unmute()
                delay(50)

                val openOk = fm.openDev()
                val powerOk = fm.powerUp(target)
                val tuneOk = fm.tune(target)
                fm.setMute(false)
                repeat(3) { index ->
                    twUtil?.setAudioSourceFm()
                    if (index < 2) delay(100)
                }
                FmNative.setFirmwareFmVolumeEnabled(true)
                runCatching { fm.setEuropeArea() }
                runCatching { fm.setRds(true) }
                applyRegionalConfig(fm, _state.value.regEnabled)

                if (!openOk || !powerOk || !tuneOk) {
                    error("Tuner-Initialisierung fehlgeschlagen (open=$openOk, power=$powerOk, tune=$tuneOk)")
                }

                persistFrequency(target)
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
                        pty = 0,
                        error = null,
                    )
                }
                startPolling()
                Timber.tag(TAG).i("Physical FM active at %.1f MHz", target)
            } catch (error: Throwable) {
                Timber.tag(TAG).e(error, "Could not start physical FM")
                cleanupHardware()
                _state.update { it.copy(isActive = false, isBusy = false, error = error.message ?: "Radio konnte nicht gestartet werden") }
            }
        }
    }

    fun powerOff() {
        scope.launch {
            stopAutoScan()
            synchronized(lock) {
                if (_state.value.isBusy && !_state.value.isActive) return@launch
                _state.update { it.copy(isBusy = true) }
            }
            cleanupHardware()
            _state.update {
                it.copy(
                    isActive = false,
                    isMuted = false,
                    isBusy = false,
                    isScanning = false,
                    scanProgress = 0f,
                    ps = "",
                    rt = "",
                    rssi = 0,
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
                    pty = 0,
                    tp = false,
                    ta = false,
                )
            }
            Timber.tag(TAG).i("Physical FM released")
        }
    }

    fun tune(frequency: Float) {
        val target = normalizeFrequency(frequency)
        if (!_state.value.isActive) {
            powerOn(target)
            return
        }
        scope.launch {
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
            val success = runCatching { native?.tune(target) == true }.getOrDefault(false)
            if (success) {
                persistFrequency(target)
                _state.update { it.copy(isBusy = false, frequency = target) }
                triggerRdsRead()
            } else {
                _state.update { it.copy(isBusy = false, error = "Frequenz konnte nicht eingestellt werden") }
            }
        }
    }

    fun step(up: Boolean) {
        val current = _state.value.frequency
        val next =
            if (up) {
                if (current >= FM_MAX) FM_MIN else current + FM_STEP
            } else {
                if (current <= FM_MIN) FM_MAX else current - FM_STEP
            }
        tune(next)
    }

    fun seek(up: Boolean) {
        if (!_state.value.isActive) {
            powerOn()
            return
        }
        scope.launch {
            if (_state.value.isBusy || _state.value.isScanning) return@launch
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
                )
            }
            val fm = native
            if (fm == null) {
                _state.update { it.copy(isBusy = false, error = "Tuner ist nicht verfügbar") }
                return@launch
            }

            val nativeResult = runCatching { fm.seek(_state.value.frequency, up) }.getOrNull()
            val nativeFrequency = nativeResult?.firstOrNull()?.let(::decodeFrequency)
            val found =
                if (nativeFrequency != null && abs(nativeFrequency - _state.value.frequency) >= 0.05f) {
                    normalizeFrequency(nativeFrequency)
                } else {
                    softwareSeek(fm, up)
                }

            if (found != null) {
                persistFrequency(found)
                _state.update { it.copy(isBusy = false, frequency = found) }
                triggerRdsRead()
            } else {
                _state.update { it.copy(isBusy = false, error = "Kein weiterer Sender gefunden") }
            }
        }
    }

    fun startAutoScan() {
        if (_state.value.isScanning) return
        scanJob?.cancel()
        scanJob =
            scope.launch {
                val originalFrequency = _state.value.frequency
                if (!_state.value.isActive) {
                    powerOn(originalFrequency)
                    var attempts = 0
                    while (!_state.value.isActive && _state.value.error == null && attempts < 50) {
                        delay(100)
                        attempts++
                    }
                }
                val fm = native
                if (fm == null || !_state.value.isActive) {
                    _state.update { it.copy(error = "Tuner konnte für den Suchlauf nicht gestartet werden") }
                    return@launch
                }

                _state.update {
                    it.copy(
                        isScanning = true,
                        isBusy = true,
                        scanProgress = 0.01f,
                        scanResults = emptyList(),
                        error = null,
                    )
                }

                val progressJob =
                    launch {
                        var progress = 0.03f
                        while (isActive && _state.value.isScanning && progress < 0.48f) {
                            delay(350)
                            progress = (progress + 0.018f).coerceAtMost(0.48f)
                            _state.update { it.copy(scanProgress = progress) }
                        }
                    }

                val rawDeferred =
                    async(Dispatchers.IO) {
                        runCatching { FmNative.autoScan(0) }
                            .onFailure { Timber.tag(TAG).w(it, "Native autoScan failed") }
                            .getOrDefault(shortArrayOf())
                    }
                val raw =
                    withTimeoutOrNull(18_000) { rawDeferred.await() }
                        ?: run {
                            runCatching { fm.stopScan() }
                            shortArrayOf()
                        }
                progressJob.cancel()

                var frequencies =
                    raw
                        .asSequence()
                        .mapNotNull { decodeFrequency(it.toFloat()) }
                        .distinctBy { (it * 10).roundToInt() }
                        .sorted()
                        .toList()
                if (frequencies.isEmpty()) {
                    frequencies = softwareBandScan(fm)
                }

                val results = mutableListOf<ScanResult>()
                frequencies.forEachIndexed { index, frequency ->
                    if (!isActive || !_state.value.isScanning) return@forEachIndexed
                    _state.update {
                        it.copy(
                            scanProgress = 0.5f + (index.toFloat() / frequencies.size.coerceAtLeast(1)) * 0.48f,
                            frequency = frequency,
                            ps = "",
                            rt = "",
                            stereo = null,
                            pi = 0,
                            ecc = "",
                            alternativeFrequencies = emptyList(),
                            pty = 0,
                            tp = false,
                            ta = false,
                        )
                    }
                    if (!fm.tune(frequency)) return@forEachIndexed
                    delay(420)
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
                }

                runCatching { fm.tune(originalFrequency) }
                persistFrequency(originalFrequency)
                _state.update {
                    it.copy(
                        isScanning = false,
                        isBusy = false,
                        scanProgress = 1f,
                        scanResults =
                            groupScanResults(results)
                                .sortedWith(
                                    compareByDescending<ScanResult> { result -> result.rssi }
                                        .thenBy { result -> result.frequency },
                                ),
                        frequency = originalFrequency,
                    )
                }
                triggerRdsRead()
                Timber.tag(TAG).i("FM scan completed with %d stations", results.size)
            }
    }

    fun stopAutoScan() {
        scanJob?.cancel()
        scanJob = null
        runCatching { native?.stopScan() }
        _state.update { it.copy(isScanning = false, isBusy = false, scanProgress = 0f) }
    }

    fun clearScanResults() {
        _state.update { it.copy(scanResults = emptyList(), scanProgress = 0f) }
    }

    fun saveScanResults(results: Collection<ScanResult>) {
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

    fun toggleMute() {
        setMute(!_state.value.isMuted)
    }

    fun setMute(mute: Boolean) {
        scope.launch {
            if (!_state.value.isActive) return@launch
            val result = runCatching { native?.setMute(mute) }.getOrNull()
            if (mute) twUtil?.mute() else twUtil?.unmute()
            if (result != null) _state.update { it.copy(isMuted = mute) }
        }
    }

    fun enableRds() {
        scope.launch {
            runCatching { native?.setRds(true) }
            triggerRdsRead()
        }
    }

    fun setAfEnabled(enabled: Boolean) {
        persistBoolean(KEY_AF, enabled)
        _state.update { it.copy(afEnabled = enabled) }
        if (enabled) requestAlternativeFrequency()
    }

    fun setTaEnabled(enabled: Boolean) {
        persistBoolean(KEY_TA, enabled)
        _state.update { it.copy(taEnabled = enabled) }
    }

    fun setRegEnabled(enabled: Boolean) {
        persistBoolean(KEY_REG, enabled)
        _state.update { it.copy(regEnabled = enabled) }
        native?.let { applyRegionalConfig(it, enabled) }
    }

    fun requestAlternativeFrequency() {
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

    fun saveCurrentPreset() {
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

    private suspend fun softwareSeek(fm: FmNative, up: Boolean): Float? {
        var candidate = _state.value.frequency
        repeat(((FM_MAX - FM_MIN) / FM_STEP).roundToInt() + 1) {
            candidate =
                if (up) {
                    if (candidate >= FM_MAX) FM_MIN else normalizeFrequency(candidate + FM_STEP)
                } else {
                    if (candidate <= FM_MIN) FM_MAX else normalizeFrequency(candidate - FM_STEP)
                }
            if (!fm.tune(candidate)) return@repeat
            delay(45)
            val rssi = fm.getRssi()
            if (rssi >= SEEK_RSSI_THRESHOLD) return candidate
        }
        return null
    }

    private suspend fun softwareBandScan(fm: FmNative): List<Float> {
        val results = mutableListOf<Float>()
        val steps = ((FM_MAX - FM_MIN) / FM_STEP).roundToInt()
        for (index in 0..steps) {
            if (!_state.value.isScanning) break
            val frequency = normalizeFrequency(FM_MIN + index * FM_STEP)
            if (!fm.tune(frequency)) continue
            delay(58)
            val rssi = fm.getRssi()
            if (rssi >= SCAN_RSSI_THRESHOLD) {
                val previous = results.lastOrNull()
                if (previous == null || abs(previous - frequency) >= 0.15f) {
                    results += frequency
                } else {
                    results[results.lastIndex] = frequency
                }
            }
            _state.update { it.copy(scanProgress = 0.05f + (index.toFloat() / steps.coerceAtLeast(1)) * 0.42f) }
        }
        return results
    }

    private fun installRdsListener() {
        FmService.setRdsListener { eventType, value1, _, _ ->
            when (eventType) {
                0 -> _state.update { it.copy(tp = value1 != 0) }
                2, 7 -> _state.update { it.copy(pty = value1) }
                6 -> _state.update { it.copy(ta = value1 != 0) }
                10, 11 -> triggerRdsRead()
                14 -> {
                    _state.update { it.copy(pi = value1 and 0xffff) }
                    updateCurrentPresetIdentity()
                }
            }
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob =
            scope.launch {
                while (isActive && _state.value.isActive) {
                    pollTuner()
                    val snapshot = _state.value
                    val now = System.currentTimeMillis()
                    if (
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
                    delay(850)
                }
            }
    }

    private fun triggerRdsRead() {
        scope.launch {
            delay(80)
            pollTuner()
        }
    }

    private fun pollTuner() {
        val fm = native ?: return
        if (!_state.value.isActive || _state.value.isScanning) return
        runCatching { fm.readRds() }
        val ps = runCatching { fm.psString }.getOrDefault("")
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
    }

    private fun applyRegionalConfig(fm: FmNative, enabled: Boolean) {
        runCatching {
            val result = fm.setconfig("reg=${if (enabled) 1 else 0}")
            Timber.tag(TAG).d("REG config result=%d enabled=%s", result, enabled)
        }.onFailure { Timber.tag(TAG).w(it, "REG config unavailable") }
    }

    private fun cleanupHardware() {
        pollingJob?.cancel()
        pollingJob = null
        scanJob?.cancel()
        scanJob = null
        FmService.setRdsListener(null)
        runCatching { native?.setMute(true) }
        runCatching { native?.setRds(false) }
        runCatching { native?.powerDown(0) }
        runCatching { native?.closeDev() }
        runCatching { twUtil?.radioOff() }
        runCatching { twUtil?.close() }
        FmNative.setFirmwareFmVolumeEnabled(false)
        appContext?.let(FytAudioRouter::release)
        abandonAudioFocus()
    }

    private fun requestAudioFocus() {
        val manager = audioManager ?: return
        if (focusRequest != null) return
        val request =
            AudioFocusRequest
                .Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(
                    AudioAttributes
                        .Builder()
                        .setUsage(AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                        .build(),
                ).setOnAudioFocusChangeListener(
                    { change ->
                        when (change) {
                            AudioManager.AUDIOFOCUS_LOSS -> powerOff()
                            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> setMute(true)
                            AudioManager.AUDIOFOCUS_GAIN -> if (_state.value.isActive) setMute(false)
                        }
                    },
                    Handler(Looper.getMainLooper()),
                ).build()
        manager.requestAudioFocus(request)
        focusRequest = request
    }

    private fun abandonAudioFocus() {
        val request = focusRequest ?: return
        runCatching { audioManager?.abandonAudioFocusRequest(request) }
        focusRequest = null
    }

    private fun persistFrequency(frequency: Float) {
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putFloat(KEY_FREQUENCY, frequency)
            ?.apply()
    }

    private fun persistBoolean(key: String, value: Boolean) {
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putBoolean(key, value)
            ?.apply()
    }

    private fun updateCurrentPresetIdentity() {
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

    private fun decodeFrequency(value: Float): Float? {
        val decoded =
            when {
                value in FM_MIN..FM_MAX -> value
                value in 875f..1080f -> value / 10f
                value in 8750f..10800f -> value / 100f
                value in 87500f..108000f -> value / 1000f
                else -> return null
            }
        return normalizeFrequency(decoded).takeIf { it in FM_MIN..FM_MAX }
    }

    private fun normalizeFrequency(value: Float): Float =
        ((value.coerceIn(FM_MIN, FM_MAX) * 10f).roundToInt() / 10f)

    private fun systemProperty(name: String): String =
        runCatching {
            val clazz = Class.forName("android.os.SystemProperties")
            val method = clazz.getMethod("get", String::class.java, String::class.java)
            method.invoke(null, name, "") as String
        }.getOrDefault("")

    fun formatFrequency(value: Float): String = String.format(java.util.Locale.GERMANY, "%.1f", value)

    fun ptyLabel(pty: Int): String =
        when (pty) {
            1 -> "Nachrichten"
            2 -> "Aktuelles"
            3 -> "Information"
            4 -> "Sport"
            5 -> "Bildung"
            6 -> "Hörspiel"
            7 -> "Kultur"
            8 -> "Wissenschaft"
            9 -> "Verschiedenes"
            10 -> "Pop"
            11 -> "Rock"
            12 -> "Unterhaltung"
            13 -> "Leichte Klassik"
            14 -> "Klassik"
            15 -> "Sonstige Musik"
            16 -> "Wetter"
            17 -> "Wirtschaft"
            18 -> "Kinder"
            19 -> "Gesellschaft"
            20 -> "Religion"
            21 -> "Telefon"
            22 -> "Reise"
            23 -> "Freizeit"
            24 -> "Jazz"
            25 -> "Country"
            26 -> "Volksmusik"
            27 -> "Oldies"
            28 -> "Folk"
            29 -> "Dokumentation"
            30 -> "Alarmtest"
            31 -> "Alarm"
            else -> ""
        }

    private object FytAudioRouter {
        private const val SYU_MUSIC = "com.syu.music"
        private const val SYU_MS = "com.syu.ms"
        private const val SWITCH_FM = "com.syu.music.switch_fm"
        private const val SWITCH_NONE = "com.syu.music.switch_none"
        private const val FM_SERVICE_ACTION = "com.android.fmradio.IFmRadioService"
        private const val FM_SERVICE_CLASS = "com.android.fmradio.FmService"
        private const val OPEN_RADIO_ACTION = "com.action.ACTION_OPEN_RADIO"

        fun prepare(context: Context) {
            runCatching { context.startService(Intent(SWITCH_FM).setPackage(SYU_MUSIC)) }
                .onFailure { Timber.tag(TAG).w(it, "switch_fm service failed") }
            runCatching { context.startService(Intent(FM_SERVICE_ACTION).setPackage(SYU_MS)) }
            runCatching { context.startService(Intent().setClassName(SYU_MS, FM_SERVICE_CLASS)) }
            runCatching { context.sendBroadcast(Intent(OPEN_RADIO_ACTION)) }
        }

        fun release(context: Context) {
            runCatching { context.startService(Intent(SWITCH_NONE).setPackage(SYU_MUSIC)) }
                .onFailure { Timber.tag(TAG).w(it, "switch_none service failed") }
        }
    }

    private class TwUtilBridge {
        private val clazz = runCatching { Class.forName("android.tw.john.TWUtil") }.getOrNull()
        private var instance: Any? = null
        private var write2: Method? = null
        private var write3: Method? = null

        fun open(): Boolean {
            val type = clazz ?: return false
            if (instance != null) return true
            return runCatching {
                val value = type.getConstructor(Int::class.javaPrimitiveType).newInstance(1)
                val commands =
                    shortArrayOf(
                        0x101,
                        0x102,
                        0x103,
                        0x104,
                        0x105,
                        0x106,
                        0x110,
                        0x111,
                        0x112,
                        0x113,
                        0x114,
                        0x115,
                    )
                val result = type.getMethod("open", ShortArray::class.java).invoke(value, commands) as? Int ?: -1
                if (result != 0) return@runCatching false
                type.getMethod("start").invoke(value)
                instance = value
                write2 = type.getMethod("write", Int::class.javaPrimitiveType, Int::class.javaPrimitiveType)
                write3 =
                    type.getMethod(
                        "write",
                        Int::class.javaPrimitiveType,
                        Int::class.javaPrimitiveType,
                        Int::class.javaPrimitiveType,
                    )
                true
            }.onFailure { Timber.tag(TAG).w(it, "TWUtil open failed") }.getOrDefault(false)
        }

        fun close() {
            val value = instance ?: return
            runCatching { clazz?.getMethod("stop")?.invoke(value) }
            runCatching { clazz?.getMethod("close")?.invoke(value) }
            instance = null
        }

        fun initRadioSequence() {
            write(0x101, 0xFF)
            write(0x102, 0xFF)
            write(0x102, 0xFF, 1)
            write(0x112, 0xFF)
            write(0x102, 0xFF, 0)
            write(0x104, 0xFF)
            write(0x103, 0)
            write(0x105, 0xFF)
            write(0x101, 0xFF)
            write(0x110, 0xFF)
        }

        fun radioOnFm() {
            write(0x101, 1)
            setAudioSourceFm()
        }

        fun radioOff() {
            write(0x101, 0)
        }

        fun setAudioSourceFm() {
            write(0x110, 1)
        }

        fun mute() {
            write(0x105, 1)
        }

        fun unmute() {
            write(0x105, 0)
        }

        private fun write(command: Int, value: Int): Int =
            runCatching { write2?.invoke(instance, command, value) as? Int ?: -1 }.getOrDefault(-1)

        private fun write(command: Int, value1: Int, value2: Int): Int =
            runCatching { write3?.invoke(instance, command, value1, value2) as? Int ?: -1 }.getOrDefault(-1)
    }
}
