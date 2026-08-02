from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"{label}: start marker missing")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"{label}: end marker missing")
    return text[:start_index] + replacement + text[end_index:]


build = Path("app/build.gradle.kts")
text = build.read_text(encoding="utf-8")
text = replace_once(
    text,
    '        versionCode = 1370054\n        versionName = "13.7.45"',
    '        versionCode = 1370055\n        versionName = "13.7.46"',
    "version",
)
build.write_text(text, encoding="utf-8")

path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
text = path.read_text(encoding="utf-8")

text = replace_once(
    text,
    "        val rtrAfPredictions: List<RtrAfPrediction> = emptyList(),\n        val presets: List<Preset> = emptyList(),",
    "        val rtrAfPredictions: List<RtrAfPrediction> = emptyList(),\n        val activeFavouriteId: String = \"\",\n        val presets: List<Preset> = emptyList(),",
    "state active favourite",
)

text = replace_once(
    text,
    "                presets = presets,\n                frequency = frequency,",
    "                presets = presets,\n                activeId = activeFavouriteId,\n                frequency = frequency,",
    "current preset active id",
)

text = replace_once(
    text,
    "    private var rtrRepository: RtrFmRepository? = null\n    private var lastRtrResolveKey = \"\"",
    "    private var rtrRepository: RtrFmRepository? = null\n    private var receptionPathStore: FmReceptionPathStore? = null\n    private var lastRtrResolveKey = \"\"",
    "path store field",
)

text = replace_once(
    text,
    "            rtrRepository = RtrFmRepository.get(applicationContext)\n            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)",
    "            rtrRepository = RtrFmRepository.get(applicationContext)\n            receptionPathStore = FmReceptionPathStore(applicationContext)\n            val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)",
    "path store init",
)

text = replace_once(
    text,
    "                val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }\n                pendingPresetIdentity = null",
    "                val presetIdentity = pendingPresetIdentity\n                pendingPresetIdentity = null",
    "power on preset identity",
)

text = replace_once(
    text,
    "                        frequency = target,\n                        ps = presetIdentity?.name.orEmpty(),",
    "                        frequency = target,\n                        activeFavouriteId = presetIdentity?.id.orEmpty(),\n                        ps = presetIdentity?.name.orEmpty(),",
    "power on active id",
)

text = replace_once(
    text,
    "    fun tune(frequency: Float) {\n        val target = normalizeFrequency(frequency)\n        Dudu7SyuRadioIpc.onMetroListTuneRequested(\"tune:$target\", target)",
    "    fun tune(frequency: Float) {\n        val target = normalizeFrequency(frequency)\n        val requestedPreset = pendingPresetIdentity\n        _state.update { current ->\n            current.copy(activeFavouriteId = requestedPreset?.id.orEmpty())\n        }\n        Dudu7SyuRadioIpc.onMetroListTuneRequested(\"tune:$target\", target)",
    "tune active id",
)

text = replace_once(
    text,
    "            val presetIdentity = pendingPresetIdentity?.takeIf { presetContainsFrequency(it, target) }\n            pendingPresetIdentity = null",
    "            val presetIdentity = pendingPresetIdentity\n            pendingPresetIdentity = null",
    "tune preset identity",
)

text = replace_once(
    text,
    "                    ps = presetIdentity?.name.orEmpty(),\n                    rt = \"\",",
    "                    activeFavouriteId = presetIdentity?.id.orEmpty(),\n                    ps = presetIdentity?.name.orEmpty(),\n                    rt = \"\",",
    "tune state active id",
)

text = replace_between(
    text,
    "    private fun launchAlternativeFrequencyCheck(manual: Boolean) {",
    "    private suspend fun measureAlternativeFrequency(",
    '''    private fun launchAlternativeFrequencyCheck(manual: Boolean) {
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
                val expectedPi = before.pi.takeIf { before.rdsConfirmed && it > 0 } ?: preset?.pi.orZero()
                val currentRtrMatch =
                    preset != null &&
                        before.rtrStableId.isNotBlank() &&
                        kotlin.math.abs(before.rtrMatchedFrequency - before.frequency) < 0.05f &&
                        before.rtrMatchConfidence >= 60 &&
                        (preset.stationId.isBlank() || preset.stationId == before.rtrStableId)
                val stationId = before.rtrStableId.takeIf { currentRtrMatch }.orEmpty()
                val regionKey = currentRegionKey()
                val identityBlock =
                    when {
                        preset == null || before.activeFavouriteId != preset.id -> "Kein eindeutig aktiver Favorit"
                        regionKey == null -> "Aktueller Standort für AF nicht verfügbar"
                        expectedPi <= 0 -> "Ausgangssender hat keine bestätigte PI"
                        !currentRtrMatch || stationId.isBlank() -> "Sender ist am aktuellen Standort nicht eindeutig über RTR zugeordnet"
                        else -> null
                    }
                if (identityBlock != null) {
                    _state.update { it.copy(afLastResult = identityBlock) }
                    appContext?.let { context ->
                        MediaKeyDiagnostics.record(
                            context,
                            "FM_AF_PATH",
                            "decision=blocked reason=$identityBlock favourite=${preset?.id.orEmpty()} " +
                                "region=${regionKey.orEmpty()} expectedPi=${expectedPi.toString(16)}",
                        )
                    }
                    return@launch
                }

                Dudu7SyuRadioIpc.resetFrequencyAnchor(
                    reason = "afCheck:${if (manual) "manual" else "automatic"}",
                    baselineFrequency = null,
                )
                val history =
                    receptionPathStore?.candidatesFor(
                        favouriteId = preset.id,
                        regionKey = regionKey,
                        expectedPi = expectedPi,
                        stationId = stationId,
                    ).orEmpty()
                val plan =
                    FmLocalAfPlanner.plan(
                        favouriteId = preset.id,
                        currentFrequency = before.frequency,
                        expectedPi = expectedPi,
                        stationId = stationId,
                        regionKey = regionKey,
                        history = history,
                        rtrCandidates =
                            before.rtrAfPredictions.map {
                                FmRtrLocalCandidate(
                                    frequency = it.frequency,
                                    coverageStrength = it.coverageStrength,
                                    source = it.source,
                                )
                            },
                    )
                val candidates =
                    plan.map {
                        FmAfCandidate(
                            frequency = it.frequency,
                            trustedPresetFrequency = it.cachedPath,
                            predictedCoverage = it.predictedCoverage,
                            source = it.source,
                        )
                    }
                if (candidates.isEmpty()) {
                    _state.update { it.copy(afLastResult = "Keine lokal mögliche RTR-Frequenz verfügbar") }
                    appContext?.let { context ->
                        MediaKeyDiagnostics.record(
                            context,
                            "FM_AF_PATH",
                            "decision=no_candidates favourite=${preset.id} region=$regionKey stationId=$stationId",
                        )
                    }
                    return@launch
                }

                val currentRssi = before.rssi.takeIf { it > 0 } ?: runCatching { fm.rssi }.getOrDefault(0)
                _state.update {
                    it.copy(
                        isBusy = true,
                        error = null,
                        afLastResult = "${candidates.size} lokale AF-Frequenz(en) werden mit PI geprüft …",
                        afLastNativeResult = null,
                    )
                }
                runCatching { fm.setMute(true) }
                try {
                    appContext?.let { context ->
                        MediaKeyDiagnostics.record(
                            context,
                            "FM_AF_PATH",
                            "decision=plan favourite=${preset.id} region=$regionKey stationId=$stationId " +
                                "expectedPi=${expectedPi.toString(16)} candidates=${candidates.joinToString { formatFrequency(it.frequency) }}",
                        )
                    }
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
                            favouriteId = preset.id,
                            regionKey = regionKey,
                            stationId = stationId,
                            target = selected.frequency,
                            targetRssi = selected.rssi,
                            targetPi = selected.pi,
                            knownFrequencies = listOf(before.frequency) + candidates.map(FmAfCandidate::frequency),
                            result =
                                "Gewechselt ${formatFrequency(before.frequency)} → ${formatFrequency(selected.frequency)} MHz " +
                                    "(PI bestätigt; RSSI $currentRssi → ${selected.rssi}; ${selected.source})",
                            nativeResult = null,
                            predictedCoverage = selected.predictedCoverage,
                        )
                        return@launch
                    }

                    runCatching { fm.tune(before.frequency) }
                    delay(180)
                    _state.update {
                        it.copy(
                            isBusy = false,
                            frequency = before.frequency,
                            activeFavouriteId = preset.id,
                            ps = before.ps,
                            pi = before.pi,
                            ecc = before.ecc,
                            rssi = currentRssi,
                            alternativeFrequencies = emptyList(),
                            afLastResult = "Keine stärkere lokale Frequenz mit identischer PI gefunden",
                        )
                    }
                    appContext?.let { context ->
                        val summary = measurements.joinToString { measurement ->
                            "${formatFrequency(measurement.frequency)}:${measurement.pi.toString(16)}"
                        }
                        MediaKeyDiagnostics.record(
                            context,
                            "FM_AF_PATH",
                            "decision=rejected_identity favourite=${preset.id} expectedPi=${expectedPi.toString(16)} measured=$summary",
                        )
                    }
                    triggerRdsRead()
                } catch (error: Throwable) {
                    Timber.tag(TAG).w(error, "Local RTR AF candidate check failed")
                    runCatching { fm.tune(before.frequency) }
                    _state.update {
                        before.copy(
                            isBusy = false,
                            afLastResult = "AF-Prüfung fehlgeschlagen: ${error.message ?: error.javaClass.simpleName}",
                        )
                    }
                    triggerRdsRead()
                } finally {
                    Dudu7SyuRadioIpc.resetFrequencyAnchor("afComplete", _state.value.frequency)
                    runCatching { fm.setMute(before.isMuted) }
                }
            }
    }

''',
    "local AF flow",
)

text = replace_between(
    text,
    "    private fun commitAlternativeFrequencySwitch(",
    "    /**\n     * Manual NavRadio+-style AF cycling.",
    '''    private fun commitAlternativeFrequencySwitch(
        before: State,
        favouriteId: String,
        regionKey: String,
        stationId: String,
        target: Float,
        targetRssi: Int,
        targetPi: Int,
        knownFrequencies: List<Float>,
        result: String,
        nativeResult: Int?,
        predictedCoverage: Int,
    ) {
        lastAfSwitchAt = System.currentTimeMillis()
        persistFrequency(target)
        rssiWindow.clear()
        resetPendingRds()
        _state.update {
            it.copy(
                isBusy = false,
                frequency = target,
                activeFavouriteId = favouriteId,
                ps = before.ps,
                rt = "",
                rssi = targetRssi,
                stereo = null,
                pi = targetPi,
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
        val stored =
            receptionPathStore?.rememberConfirmed(
                favouriteId = favouriteId,
                frequency = target,
                regionKey = regionKey,
                pi = targetPi,
                stationId = stationId,
                rssi = targetRssi,
                coverageStrength = predictedCoverage,
            ) == true
        appContext?.let { context ->
            MediaKeyDiagnostics.record(
                context,
                "FM_AF_PATH",
                "decision=accepted favourite=$favouriteId region=$regionKey frequency=$target " +
                    "pi=${targetPi.toString(16)} stationId=$stationId cached=$stored",
            )
        }
        requestRtrResolution(force = true)
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s favourite=%s stableId=%s", result, favouriteId, _state.value.stableStationId)
    }

''',
    "AF commit",
)

text = replace_between(
    text,
    "    fun tuneNextAlternativeFrequency(preset: Preset) {",
    "    fun saveCurrentPreset() {",
    '''    fun tuneNextAlternativeFrequency(preset: Preset) {
        val current = _state.value
        if (!current.isActive || current.activeFavouriteId != preset.id) {
            tunePreset(preset)
            return
        }
        requestAlternativeFrequency()
    }

''',
    "manual AF cycle",
)

text = replace_between(
    text,
    "    fun tunePreset(preset: Preset) {",
    "    fun updatePreset(",
    '''    fun tunePreset(preset: Preset) {
        rememberFmFavouriteSelection(preset.id)
        val regionKey = currentRegionKey()
        val cached =
            receptionPathStore?.bestFor(
                favouriteId = preset.id,
                regionKey = regionKey,
                expectedPi = preset.pi,
                stationId = preset.stationId,
            )
        val target = cached?.frequency ?: preset.frequency
        pendingPresetIdentity = preset
        _state.update { it.copy(activeFavouriteId = preset.id) }
        appContext?.let { context ->
            MediaKeyDiagnostics.record(
                context,
                "FM_RECEPTION_PATH",
                "favourite=${preset.id} region=${regionKey.orEmpty()} target=$target " +
                    "source=${if (cached == null) "preset" else "local_cache"} pi=${preset.pi.toString(16)}",
            )
        }
        tune(target)
    }

''',
    "tune preset local path",
)

text = replace_once(
    text,
    "    fun removePreset(preset: Preset) {\n        val updated = _state.value.presets.filterNot { it.id == preset.id }\n        persistPresets(updated)\n        _state.update { it.copy(presets = updated) }\n    }",
    "    fun removePreset(preset: Preset) {\n        val updated = _state.value.presets.filterNot { it.id == preset.id }\n        receptionPathStore?.removeFavourite(preset.id)\n        persistPresets(updated)\n        _state.update { current ->\n            current.copy(\n                presets = updated,\n                activeFavouriteId = current.activeFavouriteId.takeUnless { it == preset.id }.orEmpty(),\n            )\n        }\n    }",
    "remove preset paths",
)

text = replace_once(
    text,
    "        pendingPresetIdentity = null\n        rememberFmFavouriteSelection(null)\n        persistPresets(emptyList())",
    "        pendingPresetIdentity = null\n        rememberFmFavouriteSelection(null)\n        receptionPathStore?.clear()\n        persistPresets(emptyList())",
    "clear preset paths",
)

text = replace_once(
    text,
    "                presets = emptyList(),\n                alternativeFrequencies = emptyList(),",
    "                presets = emptyList(),\n                activeFavouriteId = \"\",\n                alternativeFrequencies = emptyList(),",
    "clear active id",
)

text = replace_between(
    text,
    "    private fun updateCurrentPresetIdentity() {",
    "    private fun updatePresetLastFrequency(",
    '''    private fun updateCurrentPresetIdentity() {
        val snapshot = _state.value
        val activeId = snapshot.activeFavouriteId
        val index = snapshot.presets.indexOfFirst { it.id == activeId }
            .takeIf { it >= 0 }
            ?: findCurrentPresetIndex(
                presets = snapshot.presets,
                activeId = activeId,
                frequency = snapshot.frequency,
                pi = snapshot.pi,
                rdsConfirmed = snapshot.rdsConfirmed,
                stationId = snapshot.rtrStableId,
            )
        if (index < 0) return
        val current = snapshot.presets[index]
        val currentRtrMatch =
            snapshot.rtrStableId.isNotBlank() &&
                kotlin.math.abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f &&
                snapshot.rtrMatchConfidence >= 60
        if (currentRtrMatch && current.stationId.isNotBlank() && current.stationId != snapshot.rtrStableId) return
        val freshRds = snapshot.rdsConfirmed && abs(snapshot.rdsFreshFrequency - snapshot.frequency) < 0.05f
        val rdsCompatible = freshRds && (current.pi <= 0 || snapshot.pi <= 0 || samePi(current.pi, snapshot.pi))
        val rtrCompatible = currentRtrMatch && (current.stationId.isBlank() || current.stationId == snapshot.rtrStableId)
        val updatedPreset =
            current.copy(
                name = when {
                    rtrCompatible && current.stationId == snapshot.rtrStableId && current.name.isNotBlank() -> current.name
                    rtrCompatible -> snapshot.rtrCanonicalName
                    rdsCompatible -> snapshot.displayStation
                    else -> current.name
                },
                pi = if (rdsCompatible && snapshot.pi > 0) snapshot.pi else current.pi,
                ecc = if (rdsCompatible && snapshot.ecc.isNotBlank()) snapshot.ecc else current.ecc,
                alternativeFrequencies = emptyList(),
                stationId = if (rtrCompatible) snapshot.rtrStableId else current.stationId,
            )
        if (updatedPreset != current) {
            val updated = snapshot.presets.toMutableList().apply { this[index] = updatedPreset }
            persistPresets(updated)
            _state.update { it.copy(presets = updated, activeFavouriteId = updatedPreset.id) }
        }

        val effectivePi = snapshot.pi.takeIf { freshRds && it > 0 } ?: return
        val effectiveStationId =
            snapshot.rtrStableId.takeIf { rtrCompatible }.orEmpty().ifBlank { updatedPreset.stationId }
        if (effectiveStationId.isBlank()) return
        if (updatedPreset.pi > 0 && !samePi(updatedPreset.pi, effectivePi)) return
        val regionKey = currentRegionKey() ?: return
        receptionPathStore?.rememberConfirmed(
            favouriteId = updatedPreset.id,
            frequency = snapshot.frequency,
            regionKey = regionKey,
            pi = effectivePi,
            stationId = effectiveStationId,
            rssi = snapshot.rssi,
            coverageStrength = snapshot.rtrCoverageStrength,
        )
    }

''',
    "current preset identity",
)

text = replace_between(
    text,
    "    private fun updatePresetLastFrequency(",
    "    private fun persistPresets(",
    "",
    "remove automatic preset frequency rewrite",
)

text = replace_between(
    text,
    "    private fun findCurrentPresetIndex(",
    "    fun stablePresetKey(preset: Preset): String = preset.id",
    '''    private fun findCurrentPresetIndex(
        presets: List<Preset>,
        activeId: String,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Int =
        FmFavouriteModel.resolveCurrentIndex(
            favourites = presets.map(::presetRef),
            activeId = activeId,
            frequency = frequency,
            stationId = stationId,
            pi = pi,
            rdsConfirmed = rdsConfirmed,
        )

    private fun findCurrentPreset(
        presets: List<Preset>,
        activeId: String,
        frequency: Float,
        pi: Int,
        rdsConfirmed: Boolean,
        stationId: String,
    ): Preset? =
        findCurrentPresetIndex(presets, activeId, frequency, pi, rdsConfirmed, stationId)
            .takeIf { it >= 0 }
            ?.let(presets::get)

''',
    "favourite resolver",
)

text = replace_once(
    text,
    "    private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()",
    "    private fun currentRegionKey(): String? =\n        FmReceptionRegion.key(_state.value.geoLatitude, _state.value.geoLongitude)\n\n    private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()",
    "region key helper",
)

path.write_text(text, encoding="utf-8")

# Extend favourite resolution tests without relying on Android hardware.
test_path = Path("app/src/test/kotlin/com/metrolist/music/radio/fyt/FmFavouriteModelTest.kt")
if test_path.exists():
    test_text = test_path.read_text(encoding="utf-8")
    insertion = '''
    @org.junit.Test
    fun `active favourite id wins when two regional paths share one frequency`() {
        val favourites =
            listOf(
                FmFavouriteRef("home", "rtr:home", 99.7f, 0xA101),
                FmFavouriteRef("travel", "rtr:travel", 99.7f, 0xB202),
            )
        val index =
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = "travel",
                frequency = 99.7f,
                stationId = "rtr:home",
                pi = 0xA101,
                rdsConfirmed = true,
            )
        org.junit.Assert.assertEquals(1, index)
    }
'''
    marker = "\n}"
    pos = test_text.rfind(marker)
    if pos < 0:
        raise SystemExit("FmFavouriteModelTest closing brace missing")
    test_path.write_text(test_text[:pos] + insertion + test_text[pos:], encoding="utf-8")
