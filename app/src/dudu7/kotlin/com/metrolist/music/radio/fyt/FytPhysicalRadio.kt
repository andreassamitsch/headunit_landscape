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
import kotlinx.coroutines.flow.collectLatest
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
    private const val KEY_AF_SENSITIVITY = "af_sensitivity"
    private const val KEY_GEO = "rtr_geo_enabled"
    private const val FM_MIN = 87.5f
    private const val FM_MAX = 108.0f
    private const val FM_STEP = 0.1f
    private const val SEEK_RSSI_THRESHOLD = 38
    private const val SCAN_RSSI_THRESHOLD = 36
    private const val AF_POLL_INTERVAL_MS = 6_000L
    private const val AF_SWITCH_COOLDOWN_MS = 20_000L
    private const val DEFAULT_AF_SENSITIVITY = 30
    private const val MIN_AF_SENSITIVITY = 15
    private const val MAX_AF_SENSITIVITY = 50
    private const val AF_RSSI_WINDOW_SIZE = 4
    private const val AF_WEAK_SAMPLE_COUNT = 3
    private const val AF_RSSI_HYSTERESIS = 3

    data class Preset(
        val frequency: Float,
        val name: String,
        val pi: Int = 0,
        val ecc: String = "",
        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
    )

    data class ScanResult(
        val frequency: Float,
        val name: String,
        val rssi: Int,
        val stereo: Boolean?,
        val pi: Int,
        val ecc: String = "",
        val pty: Int,
        val tp: Boolean,
        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
        val rdsConfirmed: Boolean = false,
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
        val rdsConfirmed: Boolean = false,
        val rdsFreshFrequency: Float = 0f,
        val pty: Int = 0,
        val tp: Boolean = false,
        val ta: Boolean = false,
        val afEnabled: Boolean = true,
        val afSensitivity: Int = DEFAULT_AF_SENSITIVITY,
        val afAverageRssi: Int = 0,
        val afWeakSamples: Int = 0,
        val firmwareFmSensitivity: Int? = null,
        val taEnabled: Boolean = true,
        val regEnabled: Boolean = false,
        val afSupported: Boolean = true,
        val afLastResult: String = "",
        val afLastNativeResult: Int? = null,
        val geoEnabled: Boolean = false,
        val geoPermissionGranted: Boolean = false,
        val geoLocationStatus: String = "Standort deaktiviert",
        val geoLatitude: Double? = null,
        val geoLongitude: Double? = null,
        val geoAccuracyMeters: Float? = null,
        val rtrCatalogStatus: String = "Noch nicht geladen",
        val rtrCatalogStations: Int = 0,
        val rtrCatalogUpdatedAt: Long = 0L,
        val rtrCatalogLoading: Boolean = false,
        val rtrMatchedFrequency: Float = 0f,
        val rtrStableId: String = "",
        val rtrCanonicalName: String = "",
        val rtrMatchSource: String = "",
        val rtrMatchConfidence: Int = 0,
        val rtrCoverageStrength: Int = 0,
        val rtrCoverageName: String = "",
        val rtrStationSite: String = "",
        val rtrAfPredictions: List<RtrAfPrediction> = emptyList(),
        val presets: List<Preset> = emptyList(),
        val radioType: String = "",
        val platform: String = "",
        val error: String? = null,
    ) {
        val currentPreset: Preset?
            get() = FytPhysicalRadio.findCurrentPreset(
                presets = presets,
                frequency = frequency,
                pi = pi,
                rdsConfirmed = rdsConfirmed && kotlin.math.abs(rdsFreshFrequency - frequency) < 0.05f,
                stationId = rtrStableId.takeIf {
                    kotlin.math.abs(rtrMatchedFrequency - frequency) < 0.05f && rtrMatchConfidence >= 60
                }.orEmpty(),
            )

        private val resolvedStationIdentity: FmResolvedStationIdentity
            get() {
                val baseIdentity =
                    FmStationIdentity.resolve(
                        rawPs = ps,
                        storedName = currentPreset?.name,
                        frequencies = listOf(frequency) + currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty(),
                        pi = pi.takeIf { rdsConfirmed && kotlin.math.abs(rdsFreshFrequency - frequency) < 0.05f } ?: 0,
                        ecc = ecc,
                    )
                val currentRtrMatch = rtrStableId.isNotBlank() && rtrCanonicalName.isNotBlank() &&
                    kotlin.math.abs(rtrMatchedFrequency - frequency) < 0.05f && rtrMatchConfidence >= 60
                if (!currentRtrMatch) return baseIdentity
                val preservedName = currentPreset?.takeIf { it.stationId == rtrStableId }?.name?.trim().orEmpty()
                return FmResolvedStationIdentity(
                    stableId = rtrStableId,
                    canonicalName = preservedName.ifBlank { rtrCanonicalName },
                    recognized = true,
                    source = rtrMatchSource.ifBlank { "RTR" },
                )
            }

        val displayStation: String
            get() = resolvedStationIdentity.canonicalName

        val stableStationId: String
            get() = resolvedStationIdentity.stableId
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
    private var geoJob: Job? = null
    private var rtrStateJob: Job? = null
    private var rtrMatchJob: Job? = null
    private var rtrRepository: RtrFmRepository? = null
    private var lastRtrResolveKey = ""
    private var audioManager: AudioManager? = null
    private var focusRequest: AudioFocusRequest? = null
    private var lastAfAttemptAt = 0L
    private var lastAfSwitchAt = 0L
    private var pendingPresetIdentity: Preset? = null
    private var pendingPs = ""
    private var pendingPsCount = 0
    private var pendingPi = 0
    private var pendingPiCount = 0
    private var pendingAfFrequencies: List<Float> = emptyList()
    private var pendingAfCount = 0
    private val rssiWindow = ArrayDeque<Int>()

    fun get(context: Context): FytPhysicalRadio {
        initialize(context)
        return this
    }

    fun initialize(context: Context) {
        if (_state.value.initialized) return
        val applicationContext = context.applicationContext
        synchronized(lock) {
            if (_state.value.initialized) return
            appContext = applicationContext
            rtrRepository = RtrFmRepository.get(applicationContext)
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
                    afSensitivity =
                        prefs.getInt(KEY_AF_SENSITIVITY, DEFAULT_AF_SENSITIVITY)
                            .coerceIn(MIN_AF_SENSITIVITY, MAX_AF_SENSITIVITY),
                    firmwareFmSensitivity = systemProperty("ro.fyt.fmsens").toIntOrNull(),
                    taEnabled = prefs.getBoolean(KEY_TA, true),
                    regEnabled = prefs.getBoolean(KEY_REG, false),
                    geoEnabled = prefs.getBoolean(KEY_GEO, false),
                    geoPermissionGranted = FmGeoLocationProvider.hasPermission(applicationContext),
                    geoLocationStatus = if (FmGeoLocationProvider.hasPermission(applicationContext)) {
                        "Standort freigegeben"
                    } else {
                        "Standortberechtigung fehlt"
                    },
                    radioType = systemProperty("sys.fyt.radio_type"),
                    platform = systemProperty("ro.product.board").ifBlank { systemProperty("ro.board.platform") },
                    error = if (FmNative.isLibraryLoaded()) null else "FYT-Firmwarebibliothek libfmjni.so konnte nicht geladen werden",
                )
        }
        startRtrServices(applicationContext)
    }

    private fun startRtrServices(context: Context) {
        val repository = rtrRepository ?: RtrFmRepository.get(context).also { rtrRepository = it }
        if (rtrStateJob == null) {
            rtrStateJob = scope.launch {
                repository.state.collectLatest { rtr ->
                    _state.update { it.copy(
                        rtrCatalogStatus = rtr.status,
                        rtrCatalogStations = rtr.stationCount,
                        rtrCatalogUpdatedAt = rtr.updatedAt,
                        rtrCatalogLoading = rtr.loading,
                    ) }
                }
            }
        }
        if (geoJob == null) {
            geoJob = scope.launch {
                FmGeoLocationProvider.state.collectLatest { geo ->
                    val point = geo.point
                    _state.update { it.copy(
                        geoPermissionGranted = geo.permissionGranted,
                        geoLocationStatus = geo.status,
                        geoLatitude = point?.latitude,
                        geoLongitude = point?.longitude,
                        geoAccuracyMeters = point?.accuracyMeters?.takeIf { accuracy -> accuracy.isFinite() },
                    ) }
                    if (_state.value.geoEnabled && point != null) requestRtrResolution()
                }
            }
        }
        if (_state.value.geoEnabled) FmGeoLocationProvider.start(context)
        scope.launch {
            repository.refreshIfNeeded()
            requestRtrResolution(force = true)
        }
    }

    fun setGeoEnabled(enabled: Boolean) {
        persistBoolean(KEY_GEO, enabled)
        _state.update { it.copy(geoEnabled = enabled) }
        val context = appContext ?: return
        if (enabled) {
            FmGeoLocationProvider.start(context)
        } else {
            FmGeoLocationProvider.stop()
            _state.update { it.copy(
                geoLatitude = null,
                geoLongitude = null,
                geoAccuracyMeters = null,
                geoLocationStatus = "Standort deaktiviert",
            ) }
        }
        requestRtrResolution(force = true)
    }

    fun onLocationPermissionChanged() {
        val context = appContext ?: return
        FmGeoLocationProvider.permissionChanged(context)
        val granted = FmGeoLocationProvider.hasPermission(context)
        _state.update { it.copy(geoPermissionGranted = granted) }
        if (!granted) {
            persistBoolean(KEY_GEO, false)
            _state.update { it.copy(geoEnabled = false) }
        } else if (_state.value.geoEnabled) {
            FmGeoLocationProvider.start(context)
        }
        requestRtrResolution(force = true)
    }

    fun refreshRtrData() {
        scope.launch {
            rtrRepository?.refreshIfNeeded(force = true)
            requestRtrResolution(force = true)
        }
    }

    private fun requestRtrResolution(force: Boolean = false) {
        val repository = rtrRepository ?: return
        val before = _state.value
        val point = if (before.geoEnabled) FmGeoLocationProvider.state.value.point else null
        val pointKey = point?.let {
            "${(it.latitude * 100.0).roundToInt()}:${(it.longitude * 100.0).roundToInt()}"
        } ?: "none"
        val key = "${frequencyKey(before.frequency)}:${before.pi}:${before.ps}:" +
            "${before.currentPreset?.name.orEmpty()}:$pointKey"
        if (!force && key == lastRtrResolveKey) return
        lastRtrResolveKey = key
        rtrMatchJob?.cancel()
        rtrMatchJob = scope.launch {
            val match = repository.resolve(
                frequency = before.frequency,
                rawPs = before.ps,
                storedName = before.currentPreset?.name,
                pi = before.pi,
                location = point,
            )
            val predictions = match?.let {
                repository.alternatives(it, before.frequency, point)
            }.orEmpty()
            if (kotlin.math.abs(_state.value.frequency - before.frequency) >= 0.05f) return@launch
            _state.update { it.copy(
                rtrMatchedFrequency = if (match == null) 0f else before.frequency,
                rtrStableId = match?.stableId.orEmpty(),
                rtrCanonicalName = match?.canonicalName.orEmpty(),
                rtrMatchSource = match?.source.orEmpty(),
                rtrMatchConfidence = match?.confidence ?: 0,
                rtrCoverageStrength = match?.coverageStrength ?: 0,
                rtrCoverageName = match?.coverageName.orEmpty(),
                rtrStationSite = match?.stationSite.orEmpty(),
                rtrAfPredictions = predictions,
            ) }
            if (match != null) updateCurrentPresetIdentity()
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
                runCatching { fm.setRds(false) }
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

                val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }
                pendingPresetIdentity = null
                resetPendingRds()
                resetAfSampling()
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
                        pi = 0,
                        ecc = "",
                        alternativeFrequencies = emptyList(),
                        rdsConfirmed = false,
                        rdsFreshFrequency = 0f,
                        afAverageRssi = 0,
                        afWeakSamples = 0,
                        pty = 0,
                        error = null,
                    )
                }
                startPolling()
                requestRtrResolution(force = true)
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
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
                    afAverageRssi = 0,
                    afWeakSamples = 0,
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
            val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }
            pendingPresetIdentity = null
            resetPendingRds()
            resetAfSampling()
            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    ps = presetIdentity?.name.orEmpty(),
                    rt = "",
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
                    pty = 0,
                )
            }
            val success = runCatching {
                native?.let { fm ->
                    runCatching { fm.setRds(false) }
                    val tuned = fm.tune(target)
                    runCatching { fm.setRds(true) }
                    tuned
                } == true
            }.getOrDefault(false)
            if (success) {
                persistFrequency(target)
                _state.update { it.copy(isBusy = false, frequency = target) }
                triggerRdsRead()
                requestRtrResolution(force = true)
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
            resetPendingRds()
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
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
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
                    resetPendingRds()
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
                            rdsConfirmed = false,
                            rdsFreshFrequency = 0f,
                            pty = 0,
                            tp = false,
                            ta = false,
                        )
                    }
                    runCatching { fm.setRds(false) }
                    if (!fm.tune(frequency)) return@forEachIndexed
                    delay(70)
                    runCatching { fm.setRds(true) }
                    val observation = readFreshRdsObservation(fm, attempts = 7, initialDelayMs = 230)
                    val rssi = runCatching { fm.rssi }.getOrDefault(0)
                    if (rssi < SCAN_RSSI_THRESHOLD) return@forEachIndexed
                    val stereoState = runCatching { fm.stereoState }.getOrDefault(-1)
                    val point = if (_state.value.geoEnabled) FmGeoLocationProvider.state.value.point else null
                    val rtrMatch = rtrRepository?.cachedSnapshot()?.let { catalog ->
                        RtrFmMatcher.resolve(
                            snapshot = catalog,
                            frequency = frequency,
                            rawPs = observation.ps,
                            storedName = null,
                            pi = observation.pi,
                            location = point,
                        )
                    }
                    results +=
                        ScanResult(
                            frequency = frequency,
                            name = rtrMatch?.canonicalName ?: observation.ps.ifBlank { "FM ${formatFrequency(frequency)}" },
                            rssi = rssi,
                            stereo = stereoState.takeIf { it >= 0 }?.let { it == 1 },
                            pi = observation.pi,
                            ecc = observation.ecc,
                            pty = observation.pty,
                            tp = observation.tp,
                            alternativeFrequencies = emptyList(),
                            stationId = rtrMatch?.stableId.orEmpty(),
                            rdsConfirmed = observation.confirmed,
                        )
                    _state.update { it.copy(scanResults = groupScanResults(results)) }
                }

                resetPendingRds()
                runCatching {
                    fm.setRds(false)
                    fm.tune(originalFrequency)
                    fm.setRds(true)
                }
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
                        ps = "",
                        rt = "",
                        pi = 0,
                        ecc = "",
                        alternativeFrequencies = emptyList(),
                        rdsConfirmed = false,
                        rdsFreshFrequency = 0f,
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
                    ecc = it.ecc,
                    alternativeFrequencies = it.alternativeFrequencies,
                    stationId = it.stationId,
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

    fun setAfSensitivity(value: Int) {
        val normalized = value.coerceIn(MIN_AF_SENSITIVITY, MAX_AF_SENSITIVITY)
        persistInt(KEY_AF_SENSITIVITY, normalized)
        _state.update { current ->
            val weakSamples =
                if (current.afAverageRssi > 0 && current.afAverageRssi < normalized) {
                    current.afWeakSamples.coerceAtLeast(1)
                } else {
                    0
                }
            current.copy(afSensitivity = normalized, afWeakSamples = weakSamples)
        }
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
        launchAlternativeFrequencyCheck(manual = true)
    }

    private fun requestAutomaticAlternativeFrequency() {
        launchAlternativeFrequencyCheck(manual = false)
    }

    private fun launchAlternativeFrequencyCheck(manual: Boolean) {
        if (afJob?.isActive == true) {
            _state.update { it.copy(afLastResult = "AF-Prüfung läuft bereits") }
            return
        }
        afJob =
            scope.launch {
                val fm = native
                if (fm == null) {
                    _state.update { it.copy(afLastResult = "FM-Tuner nicht verfügbar") }
                    return@launch
                }
                val before = _state.value
                val now = System.currentTimeMillis()
                val blockedReason =
                    when {
                        !before.isActive -> "FM-Radio ist nicht aktiv"
                        !before.afEnabled -> "AF ist ausgeschaltet"
                        before.isScanning -> "AF während Sendersuchlauf nicht möglich"
                        before.isBusy -> "Radio ist gerade beschäftigt"
                        !manual && now - lastAfSwitchAt < AF_SWITCH_COOLDOWN_MS -> "AF-Umschaltsperre aktiv"
                        !manual &&
                            (before.afAverageRssi <= 0 ||
                                before.afAverageRssi >= before.afSensitivity ||
                                before.afWeakSamples < AF_WEAK_SAMPLE_COUNT) -> "Empfang liegt noch nicht unter der AF-Schwelle"
                        else -> null
                    }
                if (blockedReason != null) {
                    _state.update { it.copy(afLastResult = blockedReason) }
                    return@launch
                }

                val preset = before.currentPreset
                val expectedPi = before.pi.takeIf { it > 0 } ?: preset?.pi.orZero()
                val storedFrequencies = preset?.let(::presetFrequencies).orEmpty()
                val currentRtrMatch = before.rtrStableId.isNotBlank() &&
                    kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f &&
                    before.rtrMatchConfidence >= 60
                val presetTrusted = preset != null && (
                    (currentRtrMatch && preset.stationId.isNotBlank() && preset.stationId == before.rtrStableId) ||
                        (before.rdsConfirmed && expectedPi > 0 && preset.pi > 0 && samePi(expectedPi, preset.pi))
                    )
                val trustedStoredFrequencies = if (presetTrusted) storedFrequencies else emptyList()
                val liveAfFrequencies = if (before.rdsConfirmed) before.alternativeFrequencies else emptyList()
                val nativeFrequencies = if (before.rdsConfirmed) {
                    runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList())
                } else {
                    emptyList()
                }
                val rtrPredictions = before.rtrAfPredictions.takeIf { currentRtrMatch }.orEmpty()
                val rtrFrequencies = rtrPredictions.map(RtrAfPrediction::frequency)
                val knownFrequencies = normalizeFrequencyList(
                    trustedStoredFrequencies + liveAfFrequencies + nativeFrequencies +
                        rtrFrequencies + before.frequency,
                )
                val databaseTrusted = before.rtrMatchConfidence >= 75
                val trustedFrequencies = normalizeFrequencyList(
                    trustedStoredFrequencies + rtrPredictions.filter { databaseTrusted && it.coverageStrength > 0 }
                        .map(RtrAfPrediction::frequency),
                )
                val candidates =
                    (trustedStoredFrequencies.map {
                        FmAfCandidate(it, true, source = "bestätigter Favorit")
                    } + rtrPredictions.map {
                        FmAfCandidate(
                            frequency = it.frequency,
                            trustedPresetFrequency = databaseTrusted && it.coverageStrength > 0,
                            predictedCoverage = it.coverageStrength,
                            source = it.source,
                        )
                    } + (liveAfFrequencies + nativeFrequencies).map {
                        FmAfCandidate(it, false, source = "bestätigtes FYT/RDS-AF")
                    })
                        .filter { abs(it.frequency - before.frequency) >= 0.05f }
                        .distinctBy { frequencyKey(it.frequency) }
                        .sortedWith(compareByDescending<FmAfCandidate> { it.trustedPresetFrequency }
                            .thenByDescending { it.predictedCoverage })
                        .take(16)
                val currentRssi = before.rssi.takeIf { it > 0 } ?: runCatching { fm.rssi }.getOrDefault(0)

                _state.update {
                    it.copy(
                        isBusy = true,
                        error = null,
                        afLastResult = if (candidates.isEmpty()) "FYT-AF wird geprüft …" else "${candidates.size} AF-Frequenz(en) werden gemessen …",
                        afLastNativeResult = null,
                    )
                }
                runCatching { fm.setMute(true) }
                try {
                    val measurements = candidates.mapNotNull { measureAlternativeFrequency(fm, it) }
                    val selected =
                        FmAlternativeFrequencySelector.choose(
                            currentFrequency = before.frequency,
                            currentRssi = currentRssi,
                            expectedPi = expectedPi,
                            measurements = measurements,
                            minimumImprovement = if (manual) 1 else 3,
                        )
                    if (selected != null) {
                        runCatching { fm.tune(selected.frequency) }
                        delay(220)
                        commitAlternativeFrequencySwitch(
                            before = before,
                            target = selected.frequency,
                            targetRssi = selected.rssi,
                            targetPi = selected.pi,
                            knownFrequencies = knownFrequencies,
                            result =
                                "Gewechselt ${formatFrequency(before.frequency)} → ${formatFrequency(selected.frequency)} MHz " +
                                    "(RSSI $currentRssi → ${selected.rssi}; ${selected.source})",
                            nativeResult = null,
                        )
                        return@launch
                    }

                    if (tryNativeAfFallback(
                            fm = fm,
                            before = before,
                            expectedPi = expectedPi,
                            knownFrequencies = knownFrequencies,
                            trustedFrequencies = trustedFrequencies,
                            manual = manual,
                        )
                    ) return@launch

                    runCatching { fm.tune(before.frequency) }
                    delay(180)
                    _state.update {
                        it.copy(
                            isBusy = false,
                            frequency = before.frequency,
                            ps = before.ps,
                            pi = before.pi,
                            ecc = before.ecc,
                            rssi = currentRssi,
                            alternativeFrequencies =
                                knownFrequencies.filterNot { frequency -> abs(frequency - before.frequency) < 0.05f },
                            afLastResult =
                                if (candidates.isEmpty()) "Keine alternative Frequenz verfügbar"
                                else "Keine stärkere passende Frequenz gefunden",
                        )
                    }
                    updateCurrentPresetIdentity()
                    triggerRdsRead()
                } catch (error: Throwable) {
                    Timber.tag(TAG).w(error, "AF candidate check failed")
                    runCatching { fm.tune(before.frequency) }
                    _state.update {
                        it.copy(
                            isBusy = false,
                            frequency = before.frequency,
                            ps = before.ps,
                            pi = before.pi,
                            ecc = before.ecc,
                            afLastResult = "AF-Prüfung fehlgeschlagen: ${error.message ?: error.javaClass.simpleName}",
                        )
                    }
                    triggerRdsRead()
                } finally {
                    runCatching { fm.setMute(before.isMuted) }
                }
            }
    }

    private suspend fun measureAlternativeFrequency(
        fm: FmNative,
        candidate: FmAfCandidate,
    ): FmAfMeasurement? {
        runCatching { fm.setRds(false) }
        if (!runCatching { fm.tune(candidate.frequency) }.getOrDefault(false)) return null
        runCatching { fm.setRds(true) }
        val observation = readFreshRdsObservation(fm, attempts = 6, initialDelayMs = 220)
        return FmAfMeasurement(
            frequency = candidate.frequency,
            rssi = runCatching { fm.rssi }.getOrDefault(0),
            pi = observation.pi,
            trustedPresetFrequency = candidate.trustedPresetFrequency,
            predictedCoverage = candidate.predictedCoverage,
            source = candidate.source,
        )
    }

    private suspend fun tryNativeAfFallback(
        fm: FmNative,
        before: State,
        expectedPi: Int,
        knownFrequencies: List<Float>,
        trustedFrequencies: List<Float>,
        manual: Boolean,
    ): Boolean {
        runCatching { fm.tune(before.frequency) }
        delay(180)
        val raw =
            runCatching { fm.activeAf() }.getOrElse { error ->
                Timber.tag(TAG).w(error, "Native AF request failed")
                _state.update {
                    it.copy(
                        isBusy = false,
                        afSupported = false,
                        afLastResult = "FYT activeAf() nicht unterstützt: ${error.message ?: error.javaClass.simpleName}",
                    )
                }
                return true
            }
        val rawInt = raw.toInt()
        _state.update { it.copy(afLastNativeResult = rawInt) }
        val target = decodeFrequency(raw.toFloat())
        if (target == null || abs(target - before.frequency) < 0.05f) return false

        val observation = readFreshRdsObservation(fm, attempts = 6, initialDelayMs = 240)
        val receivedPi = observation.pi
        val targetTrusted = trustedFrequencies.any { abs(it - target) < 0.05f }
        if ((expectedPi > 0 && (receivedPi <= 0 || !samePi(expectedPi, receivedPi))) ||
            (expectedPi <= 0 && !targetTrusted)
        ) {
            runCatching { fm.tune(before.frequency) }
            _state.update {
                it.copy(
                    isBusy = false,
                    frequency = before.frequency,
                    ps = before.ps,
                    pi = before.pi,
                    ecc = before.ecc,
                    afLastResult = if (receivedPi > 0) {
                        "FYT-AF verworfen: andere PI ${receivedPi.toString(16).uppercase()}"
                    } else {
                        "FYT-AF verworfen: Senderidentität nicht bestätigt"
                    },
                    afLastNativeResult = rawInt,
                )
            }
            triggerRdsRead()
            return true
        }
        val targetRssi = runCatching { fm.rssi }.getOrDefault(before.rssi)
        commitAlternativeFrequencySwitch(
            before = before,
            target = target,
            targetRssi = targetRssi,
            targetPi = receivedPi,
            knownFrequencies = knownFrequencies,
            result =
                "${if (manual) "FYT-AF" else "Automatisches FYT-AF"}: " +
                    "${formatFrequency(before.frequency)} → ${formatFrequency(target)} MHz",
            nativeResult = rawInt,
        )
        return true
    }

    private fun commitAlternativeFrequencySwitch(
        before: State,
        target: Float,
        targetRssi: Int,
        targetPi: Int,
        knownFrequencies: List<Float>,
        result: String,
        nativeResult: Int?,
    ) {
        lastAfSwitchAt = System.currentTimeMillis()
        persistFrequency(target)
        rssiWindow.clear()
        resetPendingRds()
        _state.update {
            it.copy(
                isBusy = false,
                frequency = target,
                ps = before.ps,
                rt = "",
                rssi = targetRssi,
                stereo = null,
                pi = targetPi.takeIf { value -> value > 0 } ?: 0,
                ecc = "",
                alternativeFrequencies =
                    normalizeFrequencyList(knownFrequencies + before.frequency)
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
                rdsConfirmed = targetPi > 0,
                rdsFreshFrequency = if (targetPi > 0) target else 0f,
                afAverageRssi = 0,
                afWeakSamples = 0,
                afLastResult = result,
                afLastNativeResult = nativeResult,
            )
        }
        requestRtrResolution(force = true)
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)
    }

    /**
     * Manual NavRadio+-style AF cycling. A double tap on the active favourite
     * advances to the next known frequency and rejects a confirmed foreign PI.
     */
    fun tuneNextAlternativeFrequency(preset: Preset) {
        val current = _state.value
        if (!current.isActive || !presetMatches(preset, current.frequency, current.pi)) {
            tunePreset(preset)
            return
        }
        val expectedPi = current.pi.takeIf { current.rdsConfirmed && it > 0 } ?: preset.pi
        val rtrIdentityTrusted = current.rtrStableId.isNotBlank() && preset.stationId == current.rtrStableId &&
            kotlin.math.abs(current.rtrMatchedFrequency - current.frequency) < 0.05f && current.rtrMatchConfidence >= 60
        if (expectedPi <= 0 && !rtrIdentityTrusted) {
            requestAlternativeFrequency()
            return
        }
        val candidates =
            normalizeFrequencyList(
                presetFrequencies(preset) + if (current.rdsConfirmed) current.alternativeFrequencies else emptyList(),
            )
        if (candidates.size <= 1) {
            requestAlternativeFrequency()
            return
        }

        scope.launch {
            val before = _state.value
            if (before.isBusy || before.isScanning) return@launch
            val fm = native ?: return@launch
            val currentIndex =
                candidates.indexOfFirst { abs(it - before.frequency) < 0.05f }
                    .takeIf { it >= 0 }
                    ?: 0
            val target = candidates[(currentIndex + 1) % candidates.size]
            if (abs(target - before.frequency) < 0.05f) return@launch

            resetPendingRds()
            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    frequency = target,
                    ps = preset.name,
                    rt = "",
                    stereo = null,
                    pi = 0,
                    ecc = "",
                    alternativeFrequencies = emptyList(),
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
                    afAverageRssi = 0,
                    afWeakSamples = 0,
                )
            }
            runCatching { fm.setRds(false) }
            if (!runCatching { fm.tune(target) }.getOrDefault(false)) {
                _state.value = before.copy(isBusy = false, error = "AF-Frequenz konnte nicht eingestellt werden")
                return@launch
            }

            runCatching { fm.setRds(true) }
            val observation = readFreshRdsObservation(fm, attempts = 7, initialDelayMs = 260)
            val receivedPi = observation.pi
            if ((expectedPi > 0 && (receivedPi <= 0 || !samePi(expectedPi, receivedPi))) ||
                (expectedPi <= 0 && !rtrIdentityTrusted)
            ) {
                Timber.tag(TAG).w(
                    "Manual AF rejected %.1f because PI changed %04X -> %04X",
                    target,
                    expectedPi,
                    receivedPi,
                )
                runCatching { fm.tune(before.frequency) }
                delay(250)
                _state.value = before.copy(
                    isBusy = false,
                    error = "Nächste AF-Frequenz gehört zu einem anderen Sender",
                )
                triggerRdsRead()
                return@launch
            }

            val targetRssi = runCatching { fm.rssi }.getOrDefault(before.rssi)
            lastAfSwitchAt = System.currentTimeMillis()
            persistFrequency(target)
            rssiWindow.clear()
            _state.update {
                it.copy(
                    isBusy = false,
                    frequency = target,
                    rssi = targetRssi,
                    pi = receivedPi.takeIf { value -> value > 0 } ?: 0,
                    ecc = observation.ecc,
                    alternativeFrequencies = candidates.filterNot { value -> abs(value - target) < 0.05f },
                    rdsConfirmed = observation.confirmed,
                    rdsFreshFrequency = if (observation.confirmed) target else 0f,
                    afAverageRssi = 0,
                    afWeakSamples = 0,
                )
            }
            updateCurrentPresetIdentity()
            triggerRdsRead()
            Timber.tag(TAG).i(
                "Manual AF cycle %.1f -> %.1f PI=%04X RSSI=%d",
                before.frequency,
                target,
                receivedPi.takeIf { it > 0 } ?: expectedPi,
                targetRssi,
            )
        }
    }

    fun saveCurrentPreset() {
        val snapshot = _state.value
        val currentRtrMatch = snapshot.rtrStableId.isNotBlank() &&
            kotlin.math.abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f &&
            snapshot.rtrMatchConfidence >= 60
        val preset =
            Preset(
                frequency = snapshot.frequency,
                name = snapshot.displayStation,
                pi = snapshot.pi.takeIf { snapshot.rdsConfirmed } ?: 0,
                ecc = snapshot.ecc.takeIf { snapshot.rdsConfirmed }.orEmpty(),
                alternativeFrequencies = normalizeFrequencyList(
                    (if (snapshot.rdsConfirmed) snapshot.alternativeFrequencies else emptyList()) +
                        if (currentRtrMatch) snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency) else emptyList(),
                ),
                stationId = snapshot.rtrStableId.takeIf { currentRtrMatch }.orEmpty(),
            )
        val updated = mergePresets(snapshot.presets + preset).sortedBy { it.frequency }
        persistPresets(updated)
        _state.update { it.copy(presets = updated) }
    }

    fun tunePreset(preset: Preset) {
        pendingPresetIdentity = preset
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

    fun clearPresets() {
        pendingPresetIdentity = null
        persistPresets(emptyList())
        _state.update {
            it.copy(
                presets = emptyList(),
                alternativeFrequencies = emptyList(),
                rtrAfPredictions = emptyList(),
            )
        }
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
                10, 11, 14 -> triggerRdsRead()
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
                        (snapshot.pi > 0 || snapshot.currentPreset?.let { presetFrequencies(it).size > 1 } == true) &&
                        snapshot.afAverageRssi > 0 &&
                        snapshot.afAverageRssi < snapshot.afSensitivity &&
                        snapshot.afWeakSamples >= AF_WEAK_SAMPLE_COUNT &&
                        !snapshot.isScanning &&
                        !snapshot.isBusy &&
                        now - lastAfAttemptAt >= AF_POLL_INTERVAL_MS
                    ) {
                        lastAfAttemptAt = now
                        requestAutomaticAlternativeFrequency()
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
        if (!_state.value.isActive || _state.value.isScanning || _state.value.isBusy) return
        runCatching { fm.readRds() }
        val rawPs = runCatching { fm.psString }.getOrDefault("").trim()
        if (rawPs.isNotBlank()) {
            if (rawPs == pendingPs) {
                pendingPsCount += 1
            } else {
                pendingPs = rawPs
                pendingPsCount = 1
            }
        }
        val psConfirmedNow = rawPs.isNotBlank() && pendingPsCount >= 2
        val stablePs = if (psConfirmedNow) rawPs else _state.value.ps

        val directPi = runCatching { fm.programIdentifier }.getOrDefault(0) and 0xffff
        if (directPi > 0) {
            if (directPi == pendingPi) {
                pendingPiCount += 1
            } else {
                pendingPi = directPi
                pendingPiCount = 1
            }
        }
        val piConfirmedNow = directPi > 0 && pendingPiCount >= 2
        val stablePi = if (piConfirmedNow) directPi else _state.value.pi
        val freshConfirmed = _state.value.rdsConfirmed || psConfirmedNow || piConfirmedNow

        val rt = runCatching { fm.radioText }.getOrDefault("")
        val rssi = runCatching { fm.rssi }.getOrDefault(_state.value.rssi)
        if (rssi > 0) {
            rssiWindow.addLast(rssi)
            while (rssiWindow.size > AF_RSSI_WINDOW_SIZE) rssiWindow.removeFirst()
        }
        val averageRssi =
            if (rssiWindow.isNotEmpty()) rssiWindow.sum() / rssiWindow.size else _state.value.afAverageRssi
        val weakSamples =
            when {
                averageRssi <= 0 -> 0
                averageRssi < _state.value.afSensitivity -> (_state.value.afWeakSamples + 1).coerceAtMost(AF_WEAK_SAMPLE_COUNT)
                averageRssi >= _state.value.afSensitivity + AF_RSSI_HYSTERESIS -> 0
                else -> (_state.value.afWeakSamples - 1).coerceAtLeast(0)
            }
        val stereoState = runCatching { fm.stereoState }.getOrDefault(-1)
        val directEcc = runCatching { fm.extendedCountryCode }.getOrDefault("")
        val normalizedAf =
            if (piConfirmedNow || (_state.value.rdsConfirmed && stablePi > 0)) {
                normalizeFrequencyList(runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList()))
                    .filterNot { abs(it - _state.value.frequency) < 0.05f }
            } else {
                emptyList()
            }
        if (normalizedAf.isNotEmpty()) {
            if (normalizedAf == pendingAfFrequencies) {
                pendingAfCount += 1
            } else {
                pendingAfFrequencies = normalizedAf
                pendingAfCount = 1
            }
        }
        val stableAf = if (pendingAfCount >= 2) pendingAfFrequencies else _state.value.alternativeFrequencies

        _state.update { current ->
            current.copy(
                ps = stablePs,
                rt = rt.ifBlank { current.rt },
                rssi = rssi,
                afAverageRssi = averageRssi,
                afWeakSamples = weakSamples,
                stereo = stereoState.takeIf { it >= 0 }?.let { it == 1 } ?: current.stereo,
                pi = stablePi,
                ecc = if (piConfirmedNow && directEcc.isNotBlank()) directEcc else current.ecc,
                alternativeFrequencies = stableAf,
                rdsConfirmed = freshConfirmed,
                rdsFreshFrequency = if (freshConfirmed) current.frequency else current.rdsFreshFrequency,
            )
        }
        updateCurrentPresetIdentity()
        requestRtrResolution()
    }

    private fun resetPendingRds() {
        pendingPs = ""
        pendingPsCount = 0
        pendingPi = 0
        pendingPiCount = 0
        pendingAfFrequencies = emptyList()
        pendingAfCount = 0
    }

    private suspend fun readFreshRdsObservation(
        fm: FmNative,
        attempts: Int,
        initialDelayMs: Long,
    ): FmFreshRdsObservation {
        delay(initialDelayMs)
        val samples = mutableListOf<FmRdsSample>()
        repeat(attempts) {
            runCatching { fm.readRds() }
            delay(120)
            samples += FmRdsSample(
                ps = runCatching { fm.psString }.getOrDefault("").trim(),
                pi = runCatching { fm.programIdentifier }.getOrDefault(0),
                ecc = runCatching { fm.extendedCountryCode }.getOrDefault(""),
                pty = _state.value.pty,
                tp = _state.value.tp,
            )
        }
        return FmRdsFreshness.consolidate(samples)
    }

    private fun resetAfSampling() {
        rssiWindow.clear()
        _state.update { it.copy(afAverageRssi = 0, afWeakSamples = 0) }
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

    private fun persistInt(key: String, value: Int) {
        appContext
            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            ?.edit()
            ?.putInt(key, value)
            ?.apply()
    }

    private fun updateCurrentPresetIdentity() {
        val snapshot = _state.value
        val exactIndex = snapshot.presets.indexOfFirst { presetContainsFrequency(it, snapshot.frequency) }
        val currentRtrMatch = snapshot.rtrStableId.isNotBlank() &&
            kotlin.math.abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f &&
            snapshot.rtrMatchConfidence >= 60
        val index = if (exactIndex >= 0) {
            exactIndex
        } else {
            findCurrentPresetIndex(
                presets = snapshot.presets,
                frequency = snapshot.frequency,
                pi = snapshot.pi,
                rdsConfirmed = snapshot.rdsConfirmed,
                stationId = snapshot.rtrStableId.takeIf { currentRtrMatch }.orEmpty(),
            )
        }
        if (index < 0) return
        val current = snapshot.presets[index]
        if (currentRtrMatch && current.stationId.isNotBlank() && current.stationId != snapshot.rtrStableId) return

        val freshRds = snapshot.rdsConfirmed && abs(snapshot.rdsFreshFrequency - snapshot.frequency) < 0.05f
        val rdsCompatible = freshRds && (
            current.pi <= 0 || snapshot.pi <= 0 || samePi(current.pi, snapshot.pi)
            )
        val rtrCompatible = currentRtrMatch && (current.stationId.isBlank() || current.stationId == snapshot.rtrStableId)
        val selectedByIdentityOnly = exactIndex < 0
        if (selectedByIdentityOnly && !rtrCompatible && !(rdsCompatible && current.pi > 0 && snapshot.pi > 0)) return

        val allFrequencies = normalizeFrequencyList(
            presetFrequencies(current) +
                if (rdsCompatible) snapshot.alternativeFrequencies else emptyList() +
                if (rtrCompatible) snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency) else emptyList() +
                if (exactIndex >= 0) listOf(snapshot.frequency) else emptyList(),
        )
        val primary = current.frequency.takeIf { candidate ->
            allFrequencies.any { abs(it - candidate) < 0.05f }
        } ?: allFrequencies.first()
        val name = when {
            rtrCompatible && current.stationId == snapshot.rtrStableId && current.name.isNotBlank() -> current.name
            rtrCompatible -> snapshot.rtrCanonicalName
            rdsCompatible -> snapshot.displayStation
            else -> current.name
        }
        val updatedPreset = current.copy(
            frequency = primary,
            name = name,
            pi = if (rdsCompatible && snapshot.pi > 0) snapshot.pi else current.pi,
            ecc = if (rdsCompatible && snapshot.ecc.isNotBlank()) snapshot.ecc else current.ecc,
            alternativeFrequencies = allFrequencies.filterNot { abs(it - primary) < 0.05f },
            stationId = if (rtrCompatible) snapshot.rtrStableId else current.stationId,
        )
        val changedList = snapshot.presets.toMutableList().apply { this[index] = updatedPreset }
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
                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}\t${preset.pi}\t${preset.ecc}\t$alternatives\t${preset.stationId.replace('\n', ' ').replace('\t', ' ')}"
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
                    val parts = line.split('\t', limit = 6)
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
                        stationId = parts.getOrNull(5).orEmpty(),
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
    ): Boolean = presetContainsFrequency(preset, frequency)

    private fun presetEvidence(preset: Preset): FmStationEvidence =
        FmStationEvidence(
            frequencies = presetFrequencies(preset),
            name = preset.name,
            pi = preset.pi,
            stationId = preset.stationId,
            confirmed = preset.pi > 0 || preset.stationId.isNotBlank(),
        )

    private fun findCurrentPresetIndex(
        presets: List<Preset>,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Int = FmStationAssociation.selectCurrentIndex(
        presets = presets.map(::presetEvidence),
        frequency = frequency,
        pi = pi,
        rdsConfirmed = rdsConfirmed,
        stationId = stationId,
    )

    private fun findCurrentPreset(
        presets: List<Preset>,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Preset? = findCurrentPresetIndex(presets, frequency, pi, rdsConfirmed, stationId)
        .takeIf { it >= 0 }
        ?.let(presets::get)

    fun stablePresetKey(preset: Preset): String {
        preset.stationId.takeIf(String::isNotBlank)?.let { return it }
        val identity = FmStationIdentity.resolve(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        )
        return if (identity.recognized) identity.stableId else "${identity.stableId}:freq${frequencyKey(preset.frequency)}"
    }

    fun presetOrderKeys(preset: Preset): Set<String> = buildSet {
        preset.stationId.takeIf(String::isNotBlank)?.let(::add)
        addAll(FmStationIdentity.orderKeys(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        ))
    }

    fun formatFrequencies(values: List<Float>): String =
        normalizeFrequencyList(values).joinToString(" / ") { "${formatFrequency(it)} MHz" }

    private fun groupScanResults(results: Collection<ScanResult>): List<ScanResult> {
        val groups = mutableListOf<MutableList<ScanResult>>()
        results.forEach { result ->
            val evidence = FmStationEvidence(
                frequencies = scanFrequencies(result),
                name = result.name,
                pi = result.pi,
                stationId = result.stationId,
                confirmed = result.rdsConfirmed || result.stationId.isNotBlank(),
            )
            val group = groups.firstOrNull { existing ->
                val first = existing.first()
                FmStationAssociation.sameStation(
                    FmStationEvidence(
                        frequencies = scanFrequencies(first),
                        name = first.name,
                        pi = first.pi,
                        stationId = first.stationId,
                        confirmed = first.rdsConfirmed || first.stationId.isNotBlank(),
                    ),
                    evidence,
                )
            }
            if (group == null) groups += mutableListOf(result) else group += result
        }
        return groups.map { group ->
            val strongest = group.maxByOrNull { it.rssi } ?: group.first()
            val frequencies = normalizeFrequencyList(group.flatMap(::scanFrequencies))
            strongest.copy(
                name = group.firstOrNull { it.stationId.isNotBlank() }?.name ?: strongest.name,
                pi = group.firstOrNull { it.rdsConfirmed && it.pi > 0 }?.pi ?: strongest.pi,
                ecc = group.firstOrNull { it.rdsConfirmed && it.ecc.isNotBlank() }?.ecc ?: strongest.ecc,
                stationId = group.firstOrNull { it.stationId.isNotBlank() }?.stationId.orEmpty(),
                rdsConfirmed = group.any { it.rdsConfirmed },
                alternativeFrequencies = frequencies.filterNot { abs(it - strongest.frequency) < 0.05f },
                stereo = when {
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
            val normalized = preset.copy(
                frequency = normalizeFrequency(preset.frequency),
                alternativeFrequencies = normalizeFrequencyList(preset.alternativeFrequencies)
                    .filterNot { abs(it - preset.frequency) < 0.05f },
            )
            val group = groups.firstOrNull { existing -> samePresetStation(existing.first(), normalized) }
            if (group == null) groups += mutableListOf(normalized) else group += normalized
        }
        return groups.map { group ->
            val first = group.first()
            val frequencies = normalizeFrequencyList(group.flatMap(::presetFrequencies))
            val primary = first.frequency.takeIf { value ->
                frequencies.any { abs(it - value) < 0.05f }
            } ?: frequencies.first()
            val explicitStationId = group.map { it.stationId }.firstOrNull { it.isNotBlank() }.orEmpty()
            val selectedPi = group.firstOrNull { it.pi > 0 }?.pi ?: first.pi
            val selectedEcc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc
            first.copy(
                frequency = primary,
                name = FmStationIdentity.resolve(
                    rawPs = group.firstOrNull()?.name.orEmpty(),
                    storedName = group.map { it.name.trim() }.firstOrNull { usefulStationIdentity(it).isNotBlank() },
                    frequencies = frequencies,
                    pi = selectedPi,
                    ecc = selectedEcc,
                ).canonicalName,
                pi = selectedPi,
                ecc = selectedEcc,
                stationId = explicitStationId,
                alternativeFrequencies = frequencies.filterNot { abs(it - primary) < 0.05f },
            )
        }
    }

    private fun samePresetStation(first: Preset, second: Preset): Boolean =
        FmStationAssociation.sameStation(presetEvidence(first), presetEvidence(second))

    private fun samePresetRecord(first: Preset, second: Preset): Boolean {
        if (first == second) return true
        if (first.stationId.isNotBlank() && second.stationId.isNotBlank()) return first.stationId == second.stationId
        val samePrimary = abs(first.frequency - second.frequency) < 0.05f
        return samePrimary && FmStationAssociation.compatibleNames(presetEvidence(first), presetEvidence(second))
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

    private fun Int?.orZero(): Int = this ?: 0

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
