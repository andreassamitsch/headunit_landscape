from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1))


# Version 13.7.77.
replace_once(
    "app/build.gradle.kts",
    '        versionCode = 1370085\n        versionName = "13.7.76"',
    '        versionCode = 1370086\n        versionName = "13.7.77"',
)

# Issue #168: show the actual tuned hardware frequency next to FM LIVE.
replace_once(
    "app/src/dudu7/kotlin/com/metrolist/music/variant/PhysicalRadioPlayerPane.kt",
    '                text = if (state.ta && state.taEnabled) "●  TA VERKEHR" else "●  FM LIVE",',
    '                text = if (state.ta && state.taEnabled) "●  TA VERKEHR" else "●  FM ${FytPhysicalRadio.formatFrequency(state.frequency)} LIVE",',
)

fyt = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"

# Multiple samples are used for baseline and each candidate instead of one RSSI read.
replace_once(
    fyt,
    '    private const val AF_RSSI_HYSTERESIS = 3\n    private const val DUDU7_SESSION_PROPAGATION_MS = 150L',
    '    private const val AF_RSSI_HYSTERESIS = 3\n    private const val AF_RSSI_SAMPLE_COUNT = 4\n    private const val AF_RSSI_SAMPLE_INTERVAL_MS = 90L\n    private const val DUDU7_SESSION_PROPAGATION_MS = 150L',
)

# Issue #167: an explicit favourite wins over an ambiguous same-frequency RTR match unless
# fresh RDS proves that the stored identity is outdated.
replace_once(
    fyt,
    '''                val currentRtrMatch = rtrStableId.isNotBlank() && rtrCanonicalName.isNotBlank() &&\n                    kotlin.math.abs(rtrMatchedFrequency - frequency) < 0.05f && rtrMatchConfidence >= 60\n                if (!currentRtrMatch) return baseIdentity\n                val preservedName = currentPreset?.takeIf { it.stationId == rtrStableId }?.name?.trim().orEmpty()''',
    '''                val activePreset = currentPreset?.takeIf { activeFavouriteId.isNotBlank() && it.id == activeFavouriteId }\n                val rdsFresh = rdsConfirmed && kotlin.math.abs(rdsFreshFrequency - frequency) < 0.05f\n                val currentRtrMatch = rtrStableId.isNotBlank() && rtrCanonicalName.isNotBlank() &&\n                    kotlin.math.abs(rtrMatchedFrequency - frequency) < 0.05f && rtrMatchConfidence >= 60\n                val allowRtrOverride =\n                    FmActiveFavouriteIdentityPolicy.allowRtrOverride(\n                        activeFavourite = activePreset != null,\n                        storedStationId = activePreset?.stationId.orEmpty(),\n                        storedPi = activePreset?.pi ?: 0,\n                        currentPi = pi,\n                        rdsFresh = rdsFresh,\n                        rtrStableId = rtrStableId,\n                    )\n                if (!currentRtrMatch || !allowRtrOverride) return baseIdentity\n                val preservedName = currentPreset?.takeIf { it.stationId == rtrStableId }?.name?.trim().orEmpty()''',
)

# Clear the old RTR association immediately when a new favourite/frequency is started.
replace_once(
    fyt,
    '''                        rdsConfirmed = false,\n                        rdsFreshFrequency = 0f,\n                        afAverageRssi = 0,\n                        afWeakSamples = 0,''',
    '''                        rdsConfirmed = false,\n                        rdsFreshFrequency = 0f,\n                        rtrMatchedFrequency = 0f,\n                        rtrStableId = "",\n                        rtrCanonicalName = "",\n                        rtrMatchSource = "",\n                        rtrMatchConfidence = 0,\n                        rtrCoverageStrength = 0,\n                        rtrCoverageName = "",\n                        rtrStationSite = "",\n                        rtrAfPredictions = emptyList(),\n                        afAverageRssi = 0,\n                        afWeakSamples = 0,''',
)
replace_once(
    fyt,
    '''                    alternativeFrequencies = emptyList(),\n                    rdsConfirmed = false,\n                    rdsFreshFrequency = 0f,\n                    pty = 0,''',
    '''                    alternativeFrequencies = emptyList(),\n                    rdsConfirmed = false,\n                    rdsFreshFrequency = 0f,\n                    rtrMatchedFrequency = 0f,\n                    rtrStableId = "",\n                    rtrCanonicalName = "",\n                    rtrMatchSource = "",\n                    rtrMatchConfidence = 0,\n                    rtrCoverageStrength = 0,\n                    rtrCoverageName = "",\n                    rtrStationSite = "",\n                    rtrAfPredictions = emptyList(),\n                    pty = 0,''',
)

# Issue #112: manual AF may obtain a fresh source PI itself; a stored stable RTR programme id
# can anchor the candidate plan while the async current-frequency resolver is still catching up.
replace_once(
    fyt,
    '''                val preset = before.currentPreset\n                val expectedPi = before.pi.takeIf { before.rdsConfirmed && it > 0 } ?: preset?.pi.orZero()\n                val currentRtrMatch =\n                    preset != null &&\n                        before.rtrStableId.isNotBlank() &&\n                        kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f &&\n                        before.rtrMatchConfidence >= 60 &&\n                        (preset.stationId.isBlank() || preset.stationId == before.rtrStableId)\n                val stationId = before.rtrStableId.takeIf { currentRtrMatch }.orEmpty()\n                val regionKey = currentRegionKey()\n                val identityBlock =\n                    when {\n                        preset == null || before.activeFavouriteId != preset.id -> "Kein eindeutig aktiver Favorit"\n                        regionKey == null -> "Aktueller Standort für AF nicht verfügbar"\n                        expectedPi <= 0 -> "Ausgangssender hat keine bestätigte PI"\n                        !currentRtrMatch || stationId.isBlank() -> "Sender ist am aktuellen Standort nicht eindeutig über RTR zugeordnet"\n                        else -> null\n                    }''',
    '''                val preset = before.currentPreset\n                var expectedPi = before.pi.takeIf { before.rdsConfirmed && it > 0 } ?: preset?.pi.orZero()\n                if (manual && preset != null && expectedPi <= 0) {\n                    val sourceObservation = readFreshRdsObservation(fm, attempts = 4, initialDelayMs = 80)\n                    if (sourceObservation.pi > 0) {\n                        expectedPi = sourceObservation.pi\n                        _state.update { current ->\n                            current.copy(\n                                pi = expectedPi,\n                                rdsConfirmed = true,\n                                rdsFreshFrequency = before.frequency,\n                            )\n                        }\n                    }\n                }\n                val currentRtrMatch =\n                    preset != null &&\n                        before.rtrStableId.isNotBlank() &&\n                        kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f &&\n                        before.rtrMatchConfidence >= 60 &&\n                        (preset.stationId.isBlank() || preset.stationId == before.rtrStableId)\n                val stationId =\n                    before.rtrStableId.takeIf { currentRtrMatch }.orEmpty()\n                        .ifBlank { preset?.stationId.orEmpty() }\n                val regionKey = currentRegionKey()\n                val identityBlock =\n                    when {\n                        preset == null || before.activeFavouriteId != preset.id -> "Kein eindeutig aktiver Favorit"\n                        regionKey == null -> "Aktueller Standort für AF nicht verfügbar"\n                        expectedPi <= 0 && !manual -> "Ausgangssender hat keine bestätigte PI"\n                        stationId.isBlank() -> "Sender ist am aktuellen Standort nicht eindeutig über RTR zugeordnet"\n                        else -> null\n                    }''',
)

# Pull local candidates directly from the programme id when necessary, not only from a possibly
# stale current-frequency RTR match.
replace_once(
    fyt,
    '''                val history =\n                    receptionPathStore?.candidatesFor(\n                        favouriteId = activePreset.id,\n                        regionKey = activeRegionKey,\n                        expectedPi = expectedPi,\n                        stationId = stationId,\n                    ).orEmpty()\n                val plan =''',
    '''                val history =\n                    receptionPathStore?.candidatesFor(\n                        favouriteId = activePreset.id,\n                        regionKey = activeRegionKey,\n                        expectedPi = expectedPi,\n                        stationId = stationId,\n                    ).orEmpty()\n                val currentPoint = if (before.geoEnabled) FmGeoLocationProvider.state.value.point else null\n                val rtrPredictions =\n                    if (currentRtrMatch && before.rtrStableId == stationId && before.rtrAfPredictions.isNotEmpty()) {\n                        before.rtrAfPredictions\n                    } else {\n                        rtrRepository?.alternativesForProgram(\n                            stableId = stationId,\n                            currentFrequency = before.frequency,\n                            location = currentPoint,\n                        ).orEmpty()\n                    }\n                val plan =''',
)
replace_once(
    fyt,
    '''                        rtrCandidates =\n                            before.rtrAfPredictions.map {''',
    '''                        rtrCandidates =\n                            rtrPredictions.map {''',
)

replace_once(
    fyt,
    '''                val currentRssi = before.rssi.takeIf { it > 0 } ?: runCatching { fm.rssi }.getOrDefault(0)''',
    '''                val currentRssi =\n                    sampleRssi(fm).takeIf { it > 0 }\n                        ?: before.afAverageRssi.takeIf { it > 0 }\n                        ?: before.rssi''',
)
replace_once(
    fyt,
    '''                    val measurements = candidates.mapNotNull { measureAlternativeFrequency(fm, it) }''',
    '''                    val measurements =\n                        candidates.mapIndexedNotNull { index, candidate ->\n                            measureAlternativeFrequency(\n                                fm = fm,\n                                candidate = candidate,\n                                index = index + 1,\n                                total = candidates.size,\n                            )\n                        }''',
)
replace_once(
    fyt,
    '''                            minimumImprovement = if (manual) 1 else 3,''',
    '''                            minimumImprovement = AF_RSSI_HYSTERESIS,''',
)

# Restore the complete source state if no tested local frequency is measurably better.
replace_once(
    fyt,
    '''                    _state.update {\n                        it.copy(\n                            isBusy = false,\n                            frequency = before.frequency,\n                            activeFavouriteId = activePreset.id,\n                            ps = before.ps,\n                            pi = before.pi,\n                            ecc = before.ecc,\n                            rssi = currentRssi,\n                            alternativeFrequencies = emptyList(),\n                            afLastResult = "Keine stärkere lokale Frequenz mit identischer PI gefunden",\n                        )\n                    }''',
    '''                    _state.update {\n                        it.copy(\n                            isBusy = false,\n                            frequency = before.frequency,\n                            activeFavouriteId = activePreset.id,\n                            ps = before.ps,\n                            rt = before.rt,\n                            stereo = before.stereo,\n                            pi = before.pi,\n                            ecc = before.ecc,\n                            rssi = currentRssi,\n                            alternativeFrequencies = before.alternativeFrequencies,\n                            rdsConfirmed = before.rdsConfirmed,\n                            rdsFreshFrequency = before.rdsFreshFrequency,\n                            afLastResult =\n                                "AF: keine bessere bestätigte Frequenz – zurück auf ${formatFrequency(before.frequency)} MHz",\n                        )\n                    }''',
)

# Replace the single-read candidate probe with a visible probe frequency and averaged RSSI.
replace_once(
    fyt,
    '''    private suspend fun measureAlternativeFrequency(\n        fm: FmNative,\n        candidate: FmAfCandidate,\n    ): FmAfMeasurement? {\n        runCatching { fm.setRds(false) }\n        if (!runCatching { fm.tune(candidate.frequency) }.getOrDefault(false)) return null\n        runCatching { fm.setRds(true) }\n        val observation = readFreshRdsObservation(fm, attempts = 6, initialDelayMs = 220)\n        return FmAfMeasurement(\n            frequency = candidate.frequency,\n            rssi = runCatching { fm.rssi }.getOrDefault(0),\n            pi = observation.pi,\n            trustedPresetFrequency = candidate.trustedPresetFrequency,\n            predictedCoverage = candidate.predictedCoverage,\n            source = candidate.source,\n        )\n    }''',
    '''    private suspend fun sampleRssi(\n        fm: FmNative,\n        samples: Int = AF_RSSI_SAMPLE_COUNT,\n    ): Int {\n        val values = mutableListOf<Int>()\n        repeat(samples.coerceAtLeast(1)) { index ->\n            if (index > 0) delay(AF_RSSI_SAMPLE_INTERVAL_MS)\n            runCatching { fm.rssi }.getOrDefault(0).takeIf { it > 0 }?.let(values::add)\n        }\n        return if (values.isEmpty()) 0 else values.sum() / values.size\n    }\n\n    private suspend fun measureAlternativeFrequency(\n        fm: FmNative,\n        candidate: FmAfCandidate,\n        index: Int,\n        total: Int,\n    ): FmAfMeasurement? {\n        resetPendingRds()\n        _state.update { current ->\n            current.copy(\n                frequency = candidate.frequency,\n                rssi = 0,\n                afLastResult =\n                    "AF prüft ${formatFrequency(candidate.frequency)} MHz ($index/$total) …",\n            )\n        }\n        runCatching { fm.setRds(false) }\n        if (!runCatching { fm.tune(candidate.frequency) }.getOrDefault(false)) {\n            _state.update {\n                it.copy(afLastResult = "AF: ${formatFrequency(candidate.frequency)} MHz konnte nicht eingestellt werden")\n            }\n            return null\n        }\n        runCatching { fm.setRds(true) }\n        val observation = readFreshRdsObservation(fm, attempts = 6, initialDelayMs = 220)\n        val measuredRssi = sampleRssi(fm)\n        _state.update { current ->\n            current.copy(\n                rssi = measuredRssi,\n                afLastResult =\n                    "AF ${formatFrequency(candidate.frequency)} MHz: RSSI $measuredRssi, PI ${observation.pi.toString(16)}",\n            )\n        }\n        appContext?.let { context ->\n            MediaKeyDiagnostics.record(\n                context,\n                "FM_AF_PATH",\n                "decision=measured frequency=${candidate.frequency} rssi=$measuredRssi " +\n                    "pi=${observation.pi.toString(16)} source=${candidate.source} index=$index total=$total",\n            )\n        }\n        return FmAfMeasurement(\n            frequency = candidate.frequency,\n            rssi = measuredRssi,\n            pi = observation.pi,\n            trustedPresetFrequency = candidate.trustedPresetFrequency,\n            predictedCoverage = candidate.predictedCoverage,\n            source = candidate.source,\n        )\n    }''',
)

# Repository helper: use a known stable RTR programme id to build location-aware AF predictions
# even when the current-frequency resolver has not yet produced a safe UI identity.
repo = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/RtrFmRepository.kt"
replace_once(
    repo,
    '''    suspend fun alternatives(\n        match: RtrFmMatch,\n        currentFrequency: Float,\n        location: FmGeoPoint?,\n    ): List<RtrAfPrediction> {\n        val current = refreshIfNeeded() ?: return emptyList()\n        val strengths = if (location == null) emptyMap() else {\n            RtrFmMatcher.candidateCoverageCodesForProgram(current, match.stableId, location)\n                .associateWith { code -> sampleCoverage(current, code, location) }\n        }\n        return RtrFmMatcher.alternatives(current, match, currentFrequency, location, strengths)\n    }\n\n    fun cachedSnapshot(): RtrCatalogSnapshot? = snapshot''',
    '''    suspend fun alternatives(\n        match: RtrFmMatch,\n        currentFrequency: Float,\n        location: FmGeoPoint?,\n    ): List<RtrAfPrediction> {\n        val current = refreshIfNeeded() ?: return emptyList()\n        val strengths = if (location == null) emptyMap() else {\n            RtrFmMatcher.candidateCoverageCodesForProgram(current, match.stableId, location)\n                .associateWith { code -> sampleCoverage(current, code, location) }\n        }\n        return RtrFmMatcher.alternatives(current, match, currentFrequency, location, strengths)\n    }\n\n    suspend fun alternativesForProgram(\n        stableId: String,\n        currentFrequency: Float,\n        location: FmGeoPoint?,\n    ): List<RtrAfPrediction> {\n        if (stableId.isBlank()) return emptyList()\n        val current = refreshIfNeeded() ?: return emptyList()\n        val station = current.stations.firstOrNull { it.stableProgramId == stableId } ?: return emptyList()\n        val strengths = if (location == null) emptyMap() else {\n            RtrFmMatcher.candidateCoverageCodesForProgram(current, stableId, location)\n                .associateWith { code -> sampleCoverage(current, code, location) }\n        }\n        val match =\n            RtrFmMatch(\n                stableId = stableId,\n                canonicalName = station.program,\n                confidence = 100,\n                score = 0,\n                source = "RTR Favorit",\n                stationSite = station.stationName.ifBlank { station.stationLocation },\n                coverageCode = station.coverageCode,\n                coverageName = station.coverageName,\n                coverageStrength = strengths[station.coverageCode] ?: 0,\n                distanceKm = null,\n                frequencies = emptyList(),\n            )\n        return RtrFmMatcher.alternatives(current, match, currentFrequency, location, strengths)\n    }\n\n    fun cachedSnapshot(): RtrCatalogSnapshot? = snapshot''',
)

print("13.7.77 radio product patch applied successfully")
