#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FYT = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
SCREEN = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
MANIFEST = "app/src/main/AndroidManifest.xml"
BUILD = "app/build.gradle.kts"

def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{relative}: expected one occurrence, found {count}: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1))

def insert_after(relative: str, marker: str, addition: str) -> None:
    replace_once(relative, marker, marker + addition)

replace_once(BUILD, 'versionCode = 1370030\n        versionName = "13.7.21"', 'versionCode = 1370031\n        versionName = "13.7.22"')
insert_after(MANIFEST, '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />\n', '    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />\n    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />\n')
insert_after(FYT, "import kotlinx.coroutines.flow.asStateFlow\n", "import kotlinx.coroutines.flow.collectLatest\n")
insert_after(FYT, '    private const val KEY_AF_SENSITIVITY = "af_sensitivity"\n', '    private const val KEY_GEO = "rtr_geo_enabled"\n')

replace_once(FYT, '''        val ecc: String = "",
        val alternativeFrequencies: List<Float> = emptyList(),
    )''', '''        val ecc: String = "",
        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
    )''')
replace_once(FYT, '''        val afLastResult: String = "",
        val afLastNativeResult: Int? = null,
        val presets: List<Preset> = emptyList(),''', '''        val afLastResult: String = "",
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
        val presets: List<Preset> = emptyList(),''')
replace_once(FYT, '''        private val resolvedStationIdentity: FmResolvedStationIdentity
            get() =
                FmStationIdentity.resolve(
                    rawPs = ps,
                    storedName = currentPreset?.name,
                    frequencies =
                        listOf(frequency) +
                            alternativeFrequencies +
                            currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty(),
                    pi = pi,
                    ecc = ecc,
                )''', '''        private val resolvedStationIdentity: FmResolvedStationIdentity
            get() {
                val baseIdentity =
                    FmStationIdentity.resolve(
                        rawPs = ps,
                        storedName = currentPreset?.name,
                        frequencies = listOf(frequency) + alternativeFrequencies +
                            rtrAfPredictions.map(RtrAfPrediction::frequency) +
                            currentPreset?.let(FytPhysicalRadio::presetFrequencies).orEmpty(),
                        pi = pi,
                        ecc = ecc,
                    )
                val currentRtrMatch = rtrStableId.isNotBlank() && rtrCanonicalName.isNotBlank() &&
                    kotlin.math.abs(rtrMatchedFrequency - frequency) < 0.05f && rtrMatchConfidence >= 60
                if (!currentRtrMatch) return baseIdentity
                val preservedName = currentPreset?.takeIf {
                    it.stationId == rtrStableId ||
                        (it.stationId.isBlank() && baseIdentity.source == "gespeicherter Name")
                }?.name?.trim().orEmpty()
                return FmResolvedStationIdentity(
                    stableId = rtrStableId,
                    canonicalName = preservedName.ifBlank { rtrCanonicalName },
                    recognized = true,
                    source = rtrMatchSource.ifBlank { "RTR" },
                )
            }''')
replace_once(FYT, '''    private var scanJob: Job? = null
    private var afJob: Job? = null
    private var audioManager: AudioManager? = null''', '''    private var scanJob: Job? = null
    private var afJob: Job? = null
    private var geoJob: Job? = null
    private var rtrStateJob: Job? = null
    private var rtrMatchJob: Job? = null
    private var rtrRepository: RtrFmRepository? = null
    private var lastRtrResolveKey = ""
    private var audioManager: AudioManager? = null''')
replace_once(FYT, '''    fun initialize(context: Context) {
        if (_state.value.initialized) return
        synchronized(lock) {
            if (_state.value.initialized) return
            val applicationContext = context.applicationContext
            appContext = applicationContext''', '''    fun initialize(context: Context) {
        if (_state.value.initialized) return
        val applicationContext = context.applicationContext
        synchronized(lock) {
            if (_state.value.initialized) return
            appContext = applicationContext
            rtrRepository = RtrFmRepository.get(applicationContext)''')
replace_once(FYT, '''                    regEnabled = prefs.getBoolean(KEY_REG, false),
                    radioType = systemProperty("sys.fyt.radio_type"),''', '''                    regEnabled = prefs.getBoolean(KEY_REG, false),
                    geoEnabled = prefs.getBoolean(KEY_GEO, false),
                    geoPermissionGranted = FmGeoLocationProvider.hasPermission(applicationContext),
                    geoLocationStatus = if (FmGeoLocationProvider.hasPermission(applicationContext)) {
                        "Standort freigegeben"
                    } else {
                        "Standortberechtigung fehlt"
                    },
                    radioType = systemProperty("sys.fyt.radio_type"),''')

services = '''        startRtrServices(applicationContext)
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

    fun powerOn'''
replace_once(FYT, '''                )
        }
    }

    fun powerOn''', '''                )
        }
''' + services)

replace_once(FYT, '''                startPolling()
                Timber.tag(TAG).i("Physical FM active at %.1f MHz", target)''', '''                startPolling()
                requestRtrResolution(force = true)
                Timber.tag(TAG).i("Physical FM active at %.1f MHz", target)''')
replace_once(FYT, '''                _state.update { it.copy(isBusy = false, frequency = target) }
                triggerRdsRead()''', '''                _state.update { it.copy(isBusy = false, frequency = target) }
                triggerRdsRead()
                requestRtrResolution(force = true)''')
replace_once(FYT, '''        updateCurrentPresetIdentity()
    }

    private fun resetAfSampling()''', '''        updateCurrentPresetIdentity()
        requestRtrResolution()
    }

    private fun resetAfSampling()''')

replace_once(FYT, '''                val storedFrequencies = preset?.let(::presetFrequencies).orEmpty()
                val nativeFrequencies = runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList())
                val knownFrequencies =
                    normalizeFrequencyList(
                        storedFrequencies + before.alternativeFrequencies + nativeFrequencies + before.frequency,
                    )
                val candidates =
                    (storedFrequencies.map { FmAfCandidate(it, true) } +
                        (before.alternativeFrequencies + nativeFrequencies).map { FmAfCandidate(it, false) })
                        .filter { abs(it.frequency - before.frequency) >= 0.05f }
                        .distinctBy { frequencyKey(it.frequency) }
                        .take(12)''', '''                val storedFrequencies = preset?.let(::presetFrequencies).orEmpty()
                val nativeFrequencies = runCatching { fm.alternativeFrequencies.toList() }.getOrDefault(emptyList())
                val rtrPredictions = before.rtrAfPredictions.takeIf {
                    before.rtrStableId.isNotBlank() &&
                        kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f
                }.orEmpty()
                val rtrFrequencies = rtrPredictions.map(RtrAfPrediction::frequency)
                val knownFrequencies = normalizeFrequencyList(
                    storedFrequencies + before.alternativeFrequencies + nativeFrequencies +
                        rtrFrequencies + before.frequency,
                )
                val databaseTrusted = before.rtrMatchConfidence >= 75
                val candidates =
                    (storedFrequencies.map {
                        FmAfCandidate(it, true, source = "gespeicherter Favorit")
                    } + rtrPredictions.map {
                        FmAfCandidate(
                            frequency = it.frequency,
                            trustedPresetFrequency = databaseTrusted && it.coverageStrength > 0,
                            predictedCoverage = it.coverageStrength,
                            source = it.source,
                        )
                    } + (before.alternativeFrequencies + nativeFrequencies).map {
                        FmAfCandidate(it, false, source = "FYT/RDS-AF")
                    })
                        .filter { abs(it.frequency - before.frequency) >= 0.05f }
                        .distinctBy { frequencyKey(it.frequency) }
                        .sortedWith(compareByDescending<FmAfCandidate> { it.trustedPresetFrequency }
                            .thenByDescending { it.predictedCoverage })
                        .take(16)''')
replace_once(FYT, '''                            result =
                                "Gewechselt ${formatFrequency(before.frequency)} → ${formatFrequency(selected.frequency)} MHz " +
                                    "(RSSI $currentRssi → ${selected.rssi})",''', '''                            result =
                                "Gewechselt ${formatFrequency(before.frequency)} → ${formatFrequency(selected.frequency)} MHz " +
                                    "(RSSI $currentRssi → ${selected.rssi}; ${selected.source})",''')
replace_once(FYT, '''            trustedPresetFrequency = candidate.trustedPresetFrequency,
        )''', '''            trustedPresetFrequency = candidate.trustedPresetFrequency,
            predictedCoverage = candidate.predictedCoverage,
            source = candidate.source,
        )''')

replace_once(FYT, '''            Preset(
                frequency = snapshot.frequency,
                name = snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" },
                pi = snapshot.pi,
                ecc = snapshot.ecc,
                alternativeFrequencies = snapshot.alternativeFrequencies,
            )''', '''            Preset(
                frequency = snapshot.frequency,
                name = snapshot.displayStation,
                pi = snapshot.pi,
                ecc = snapshot.ecc,
                alternativeFrequencies = normalizeFrequencyList(
                    snapshot.alternativeFrequencies + snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency),
                ),
                stationId = snapshot.rtrStableId,
            )''')
replace_once(FYT, '''                presetFrequencies(current) +
                    snapshot.alternativeFrequencies +
                    snapshot.frequency,''', '''                presetFrequencies(current) +
                    snapshot.alternativeFrequencies +
                    snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency) +
                    snapshot.frequency,''')
replace_once(FYT, '''                name =
                    FmStationIdentity.resolve(
                        rawPs = snapshot.ps,
                        storedName = current.name,
                        frequencies = allFrequencies,
                        pi = snapshot.pi.takeIf { it > 0 } ?: current.pi,
                        ecc = snapshot.ecc.ifBlank { current.ecc },
                    ).canonicalName,
                pi = snapshot.pi.takeIf { it > 0 } ?: current.pi,''', '''                name = snapshot.displayStation,
                pi = snapshot.pi.takeIf { it > 0 } ?: current.pi,''')
replace_once(FYT, '''                alternativeFrequencies =
                    allFrequencies.filterNot { abs(it - primary) < 0.05f },
            )''', '''                alternativeFrequencies =
                    allFrequencies.filterNot { abs(it - primary) < 0.05f },
                stationId = snapshot.rtrStableId.ifBlank { current.stationId },
            )''')
replace_once(FYT, '''                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}\t${preset.pi}\t${preset.ecc}\t$alternatives"''', '''                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}\t${preset.pi}\t${preset.ecc}\t$alternatives\t${preset.stationId.replace('\n', ' ').replace('\t', ' ')}"''')
replace_once(FYT, "val parts = line.split('\\t', limit = 5)", "val parts = line.split('\\t', limit = 6)")
replace_once(FYT, '''                        ecc = parts.getOrNull(3).orEmpty(),
                        alternativeFrequencies = alternatives,
                    )''', '''                        ecc = parts.getOrNull(3).orEmpty(),
                        alternativeFrequencies = alternatives,
                        stationId = parts.getOrNull(5).orEmpty(),
                    )''')
replace_once(FYT, '''    fun stablePresetKey(preset: Preset): String =
        FmStationIdentity.resolve(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        ).stableId

    fun presetOrderKeys(preset: Preset): Set<String> =
        FmStationIdentity.orderKeys(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        )''', '''    fun stablePresetKey(preset: Preset): String =
        preset.stationId.takeIf(String::isNotBlank) ?: FmStationIdentity.resolve(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        ).stableId

    fun presetOrderKeys(preset: Preset): Set<String> = buildSet {
        preset.stationId.takeIf(String::isNotBlank)?.let(::add)
        addAll(FmStationIdentity.orderKeys(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        ))
    }''')
replace_once(FYT, '''                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
                alternativeFrequencies =''', '''                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
                stationId = group.firstOrNull { it.stationId.isNotBlank() }?.stationId ?: first.stationId,
                alternativeFrequencies =''')
replace_once(FYT, '''        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        return stablePresetKey(first) == stablePresetKey(second)''', '''        if (first.stationId.isNotBlank() && first.stationId == second.stationId) return true
        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        return stablePresetKey(first) == stablePresetKey(second)''')

insert_after(SCREEN, "package com.metrolist.music.ui.screens.radio\n\n", "import android.Manifest\nimport android.content.pm.PackageManager\n")
insert_after(SCREEN, "import androidx.compose.foundation.ExperimentalFoundationApi\n", "import androidx.activity.compose.rememberLauncherForActivityResult\nimport androidx.activity.result.contract.ActivityResultContracts\n")
insert_after(SCREEN, "import androidx.lifecycle.compose.collectAsStateWithLifecycle\n", "import androidx.core.content.ContextCompat\n")
replace_once(SCREEN, '''private fun PhysicalRadioSettingsPanel(radio: FytPhysicalRadio) {
    val state by radio.state.collectAsStateWithLifecycle()

    LazyColumn(''', '''private fun PhysicalRadioSettingsPanel(radio: FytPhysicalRadio) {
    val context = LocalContext.current
    val state by radio.state.collectAsStateWithLifecycle()
    val locationPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions(),
    ) { result ->
        val granted = result.values.any { it }
        radio.setGeoEnabled(granted)
        radio.onLocationPermissionChanged()
    }

    LazyColumn(''')
insert_after(SCREEN, '''        item {
            RadioSettingRow(
                title = "AF – Alternative Frequenzen",
''', '''        item {
            RadioSettingRow(
                title = "GPS-Sendererkennung (RTR)",
                description = when {
                    !state.geoEnabled -> "Aus. Aktivieren lädt das österreichische RTR-Frequenzbuch und nutzt GPS nur lokal im Fahrzeug."
                    !state.geoPermissionGranted -> "Standortberechtigung fehlt. GPS-Daten werden nicht an RTR übertragen."
                    else -> "${state.geoLocationStatus} • ${state.rtrCatalogStatus}"
                },
                checked = state.geoEnabled,
                onCheckedChange = { enabled ->
                    if (!enabled) {
                        radio.setGeoEnabled(false)
                    } else if (
                        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
                        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED
                    ) {
                        radio.setGeoEnabled(true)
                        radio.onLocationPermissionChanged()
                    } else {
                        locationPermissionLauncher.launch(arrayOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        ))
                    }
                },
            )
        }
        item {
            OutlinedButton(
                onClick = radio::refreshRtrData,
                enabled = !state.rtrCatalogLoading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (state.rtrCatalogLoading) "RTR-DATEN WERDEN GELADEN …" else "RTR-FREQUENZDATEN AKTUALISIEREN")
            }
        }
        item {
            RadioSettingRow(
                title = "AF – Alternative Frequenzen",
''')

print("Applied RTR/GPS stage 1+2 integration")
