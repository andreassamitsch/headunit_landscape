from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "app/build.gradle.kts"
RADIO = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
RTR = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"


def replace_exact(path: Path, old: str, new: str, expected: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} occurrence(s), found {count}: {old[:160]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    BUILD,
    '        versionCode = 1370032\n        versionName = "13.7.23"',
    '        versionCode = 1370033\n        versionName = "13.7.24"',
)
replace_exact(RTR, 'Metrolist-dudu7/13.7.22', 'Metrolist-dudu7/13.7.24')

replace_exact(
    RADIO,
    '''        val alternativeFrequencies: List<Float> = emptyList(),
    )

    data class State(''',
    '''        val alternativeFrequencies: List<Float> = emptyList(),
        val stationId: String = "",
        val rdsConfirmed: Boolean = false,
    )

    data class State(''',
)

replace_exact(
    RADIO,
    '''        val alternativeFrequencies: List<Float> = emptyList(),
        val pty: Int = 0,''',
    '''        val alternativeFrequencies: List<Float> = emptyList(),
        val rdsConfirmed: Boolean = false,
        val rdsFreshFrequency: Float = 0f,
        val pty: Int = 0,''',
)

replace_exact(
    RADIO,
    '''        val currentPreset: Preset?
            get() = presets.firstOrNull { FytPhysicalRadio.presetMatches(it, frequency, pi) }

        private val resolvedStationIdentity: FmResolvedStationIdentity
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
            }
''',
    '''        val currentPreset: Preset?
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
''',
)

replace_exact(
    RADIO,
    '''    private var pendingPs = ""
    private var pendingPsCount = 0
    private val rssiWindow = ArrayDeque<Int>()''',
    '''    private var pendingPs = ""
    private var pendingPsCount = 0
    private var pendingPi = 0
    private var pendingPiCount = 0
    private var pendingAfFrequencies: List<Float> = emptyList()
    private var pendingAfCount = 0
    private val rssiWindow = ArrayDeque<Int>()''',
)

replace_exact(
    RADIO,
    '''                val openOk = fm.openDev()
                val powerOk = fm.powerUp(target)
                val tuneOk = fm.tune(target)
                fm.setMute(false)''',
    '''                val openOk = fm.openDev()
                val powerOk = fm.powerUp(target)
                runCatching { fm.setRds(false) }
                val tuneOk = fm.tune(target)
                fm.setMute(false)''',
)

replace_exact(
    RADIO,
    '''                pendingPs = ""
                pendingPsCount = 0
                resetAfSampling()''',
    '''                resetPendingRds()
                resetAfSampling()''',
    expected=2,
)

replace_exact(
    RADIO,
    '''                        pi = presetIdentity?.pi ?: 0,
                        ecc = presetIdentity?.ecc.orEmpty(),
                        alternativeFrequencies = presetIdentity?.alternativeFrequencies.orEmpty(),''',
    '''                        pi = 0,
                        ecc = "",
                        alternativeFrequencies = emptyList(),
                        rdsConfirmed = false,
                        rdsFreshFrequency = 0f,''',
    expected=2,
)

replace_exact(
    RADIO,
    '''                    alternativeFrequencies = emptyList(),
                    afAverageRssi = 0,''',
    '''                    alternativeFrequencies = emptyList(),
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
                    afAverageRssi = 0,''',
)

replace_exact(
    RADIO,
    '''        scope.launch {
            if (_state.value.isBusy || _state.value.isScanning) return@launch
            _state.update {''',
    '''        scope.launch {
            if (_state.value.isBusy || _state.value.isScanning) return@launch
            resetPendingRds()
            _state.update {''',
)

replace_exact(
    RADIO,
    '''                    alternativeFrequencies = emptyList(),
                )
            }
            val fm = native''',
    '''                    alternativeFrequencies = emptyList(),
                    rdsConfirmed = false,
                    rdsFreshFrequency = 0f,
                )
            }
            val fm = native''',
)

replace_exact(
    RADIO,
    '''            val success = runCatching { native?.tune(target) == true }.getOrDefault(false)''',
    '''            val success = runCatching {
                native?.let { fm ->
                    runCatching { fm.setRds(false) }
                    val tuned = fm.tune(target)
                    runCatching { fm.setRds(true) }
                    tuned
                } == true
            }.getOrDefault(false)''',
)

replace_exact(
    RADIO,
    '''                val results = mutableListOf<ScanResult>()
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
                            ecc = directEcc.ifBlank { snapshot.ecc },
                            pty = snapshot.pty,
                            tp = snapshot.tp,
                            alternativeFrequencies = afList,
                        )
                    _state.update { it.copy(scanResults = groupScanResults(results)) }
                }
''',
    '''                val results = mutableListOf<ScanResult>()
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
''',
)

replace_exact(
    RADIO,
    '''                runCatching { fm.tune(originalFrequency) }
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
                }''',
    '''                resetPendingRds()
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
                }''',
)

replace_exact(
    RADIO,
    '''                    alternativeFrequencies = it.alternativeFrequencies,
                )''',
    '''                    alternativeFrequencies = it.alternativeFrequencies,
                    stationId = it.stationId,
                )''',
)

replace_exact(
    RADIO,
    '''                val storedFrequencies = preset?.let(::presetFrequencies).orEmpty()
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
                    })''',
    '''                val storedFrequencies = preset?.let(::presetFrequencies).orEmpty()
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
                    })''',
)

replace_exact(
    RADIO,
    '''                    if (tryNativeAfFallback(fm, before, expectedPi, knownFrequencies, manual)) return@launch''',
    '''                    if (tryNativeAfFallback(
                            fm = fm,
                            before = before,
                            expectedPi = expectedPi,
                            knownFrequencies = knownFrequencies,
                            trustedFrequencies = trustedFrequencies,
                            manual = manual,
                        )
                    ) return@launch''',
)

replace_exact(
    RADIO,
    '''    private suspend fun measureAlternativeFrequency(
        fm: FmNative,
        candidate: FmAfCandidate,
    ): FmAfMeasurement? {
        if (!runCatching { fm.tune(candidate.frequency) }.getOrDefault(false)) return null
        delay(240)
        repeat(4) {
            runCatching { fm.readRds() }
            delay(110)
        }
        return FmAfMeasurement(
            frequency = candidate.frequency,
            rssi = runCatching { fm.rssi }.getOrDefault(0),
            pi = runCatching { fm.programIdentifier }.getOrDefault(0),
            trustedPresetFrequency = candidate.trustedPresetFrequency,
            predictedCoverage = candidate.predictedCoverage,
            source = candidate.source,
        )
    }
''',
    '''    private suspend fun measureAlternativeFrequency(
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
''',
)

replace_exact(
    RADIO,
    '''        knownFrequencies: List<Float>,
        manual: Boolean,
    ): Boolean {''',
    '''        knownFrequencies: List<Float>,
        trustedFrequencies: List<Float>,
        manual: Boolean,
    ): Boolean {''',
)

replace_exact(
    RADIO,
    '''        delay(260)
        repeat(4) {
            runCatching { fm.readRds() }
            delay(110)
        }
        val receivedPi = runCatching { fm.programIdentifier }.getOrDefault(0)
        if (expectedPi > 0 && receivedPi > 0 && !samePi(expectedPi, receivedPi)) {''',
    '''        val observation = readFreshRdsObservation(fm, attempts = 6, initialDelayMs = 240)
        val receivedPi = observation.pi
        val targetTrusted = trustedFrequencies.any { abs(it - target) < 0.05f }
        if ((expectedPi > 0 && (receivedPi <= 0 || !samePi(expectedPi, receivedPi))) ||
            (expectedPi <= 0 && !targetTrusted)
        ) {''',
)
replace_exact(
    RADIO,
    '''                    afLastResult = "FYT-AF verworfen: andere PI ${receivedPi.toString(16).uppercase()}",''',
    '''                    afLastResult = if (receivedPi > 0) {
                        "FYT-AF verworfen: andere PI ${receivedPi.toString(16).uppercase()}"
                    } else {
                        "FYT-AF verworfen: Senderidentität nicht bestätigt"
                    },''',
)

replace_exact(
    RADIO,
    '''        lastAfSwitchAt = System.currentTimeMillis()
        persistFrequency(target)
        rssiWindow.clear()
        _state.update {''',
    '''        lastAfSwitchAt = System.currentTimeMillis()
        persistFrequency(target)
        rssiWindow.clear()
        resetPendingRds()
        _state.update {''',
)
replace_exact(
    RADIO,
    '''                pi = targetPi.takeIf { value -> value > 0 } ?: before.pi,
                ecc = before.ecc,
                alternativeFrequencies =
                    normalizeFrequencyList(knownFrequencies + before.frequency)
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
                afAverageRssi = 0,''',
    '''                pi = targetPi.takeIf { value -> value > 0 } ?: 0,
                ecc = "",
                alternativeFrequencies =
                    normalizeFrequencyList(knownFrequencies + before.frequency)
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
                rdsConfirmed = targetPi > 0,
                rdsFreshFrequency = if (targetPi > 0) target else 0f,
                afAverageRssi = 0,''',
)
replace_exact(
    RADIO,
    '''        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)''',
    '''        requestRtrResolution(force = true)
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)''',
)

replace_exact(
    RADIO,
    '''        val candidates =
            normalizeFrequencyList(presetFrequencies(preset) + current.alternativeFrequencies)
        if (candidates.size <= 1) {''',
    '''        val expectedPi = current.pi.takeIf { current.rdsConfirmed && it > 0 } ?: preset.pi
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
        if (candidates.size <= 1) {''',
)

replace_exact(
    RADIO,
    '''            _state.update {
                it.copy(
                    isBusy = true,
                    error = null,
                    frequency = target,
                    ps = preset.name,
                    rt = "",
                    stereo = null,
                    pi = preset.pi.takeIf { value -> value > 0 } ?: before.pi,
                    ecc = preset.ecc.ifBlank { before.ecc },
                    alternativeFrequencies = candidates.filterNot { value -> abs(value - target) < 0.05f },
                    afAverageRssi = 0,
                    afWeakSamples = 0,
                )
            }
            if (!runCatching { fm.tune(target) }.getOrDefault(false)) {''',
    '''            resetPendingRds()
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
            if (!runCatching { fm.tune(target) }.getOrDefault(false)) {''',
)

replace_exact(
    RADIO,
    '''            delay(500)
            repeat(5) {
                runCatching { fm.readRds() }
                delay(150)
            }
            val receivedPi = runCatching { fm.programIdentifier }.getOrDefault(0)
            val expectedPi = before.pi.takeIf { it > 0 } ?: preset.pi
            if (expectedPi > 0 && receivedPi > 0 && !samePi(expectedPi, receivedPi)) {''',
    '''            runCatching { fm.setRds(true) }
            val observation = readFreshRdsObservation(fm, attempts = 7, initialDelayMs = 260)
            val receivedPi = observation.pi
            if ((expectedPi > 0 && (receivedPi <= 0 || !samePi(expectedPi, receivedPi))) ||
                (expectedPi <= 0 && !rtrIdentityTrusted)
            ) {''',
)

replace_exact(
    RADIO,
    '''                    pi = receivedPi.takeIf { value -> value > 0 } ?: expectedPi,
                    alternativeFrequencies = candidates.filterNot { value -> abs(value - target) < 0.05f },
                    afAverageRssi = 0,''',
    '''                    pi = receivedPi.takeIf { value -> value > 0 } ?: 0,
                    ecc = observation.ecc,
                    alternativeFrequencies = candidates.filterNot { value -> abs(value - target) < 0.05f },
                    rdsConfirmed = observation.confirmed,
                    rdsFreshFrequency = if (observation.confirmed) target else 0f,
                    afAverageRssi = 0,''',
)

replace_exact(
    RADIO,
    '''        val preset =
            Preset(
                frequency = snapshot.frequency,
                name = snapshot.displayStation,
                pi = snapshot.pi,
                ecc = snapshot.ecc,
                alternativeFrequencies = normalizeFrequencyList(
                    snapshot.alternativeFrequencies + snapshot.rtrAfPredictions.map(RtrAfPrediction::frequency),
                ),
                stationId = snapshot.rtrStableId,
            )''',
    '''        val currentRtrMatch = snapshot.rtrStableId.isNotBlank() &&
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
            )''',
)

replace_exact(
    RADIO,
    '''                10, 11 -> triggerRdsRead()
                14 -> {
                    _state.update { it.copy(pi = value1 and 0xffff) }
                    updateCurrentPresetIdentity()
                }''',
    '''                10, 11, 14 -> triggerRdsRead()''',
)

start = RADIO.read_text(encoding="utf-8").index("    private fun pollTuner() {")
end = RADIO.read_text(encoding="utf-8").index("\n    private fun resetAfSampling()", start)
text = RADIO.read_text(encoding="utf-8")
new_poll = '''    private fun pollTuner() {
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
'''
RADIO.write_text(text[:start] + new_poll + text[end:], encoding="utf-8")

replace_exact(
    RADIO,
    '''    private fun resetAfSampling() {
        rssiWindow.clear()
        _state.update { it.copy(afAverageRssi = 0, afWeakSamples = 0) }
    }
''',
    '''    private fun resetPendingRds() {
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
''',
)

start = RADIO.read_text(encoding="utf-8").index("    private fun updateCurrentPresetIdentity() {")
end = RADIO.read_text(encoding="utf-8").index("\n    private fun persistPresets", start)
text = RADIO.read_text(encoding="utf-8")
new_update = '''    private fun updateCurrentPresetIdentity() {
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
'''
RADIO.write_text(text[:start] + new_update + text[end:], encoding="utf-8")

replace_exact(
    RADIO,
    '''    fun presetMatches(
        preset: Preset,
        frequency: Float,
        pi: Int,
    ): Boolean =
        presetContainsFrequency(preset, frequency) ||
            (pi > 0 && preset.pi > 0 && samePi(pi, preset.pi))

    fun stablePresetKey(preset: Preset): String =
        preset.stationId.takeIf(String::isNotBlank) ?: FmStationIdentity.resolve(
            rawPs = preset.name,
            storedName = preset.name,
            frequencies = presetFrequencies(preset),
            pi = preset.pi,
            ecc = preset.ecc,
        ).stableId
''',
    '''    fun presetMatches(
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
''',
)

start = RADIO.read_text(encoding="utf-8").index("    private fun groupScanResults(")
end = RADIO.read_text(encoding="utf-8").index("\n    private fun usefulStationIdentity", start)
text = RADIO.read_text(encoding="utf-8")
new_groups = '''    private fun groupScanResults(results: Collection<ScanResult>): List<ScanResult> {
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
'''
RADIO.write_text(text[:start] + new_groups + text[end:], encoding="utf-8")

print("Applied Dudu7 13.7.24 FM identity hardening")
