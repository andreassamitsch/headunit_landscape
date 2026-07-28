#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def update(path: str, transform) -> None:
    target = ROOT / path
    original = target.read_text(encoding="utf-8")
    changed = transform(original)
    if changed == original:
        print(f"No change required: {path}")
    else:
        target.write_text(changed, encoding="utf-8")
        print(f"Updated: {path}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source marker, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_pos = text.find(start)
    if start_pos < 0:
        if replacement in text:
            return text
        raise SystemExit(f"{label}: start marker missing")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise SystemExit(f"{label}: end marker missing")
    return text[:start_pos] + replacement + text[end_pos:]


def patch_fyt(text: str) -> str:
    text = replace_once(
        text,
        '''        val afSupported: Boolean = true,
        val presets: List<Preset> = emptyList(),
''',
        '''        val afSupported: Boolean = true,
        val afLastResult: String = "",
        val afLastNativeResult: Int? = null,
        val presets: List<Preset> = emptyList(),
''',
        "AF state fields",
    )
    text = replace_once(
        text,
        '''    ) {
        val displayStation: String
            get() = ps.ifBlank { "FM ${formatFrequency(frequency)} MHz" }
    }
''',
        '''    ) {
        val currentPreset: Preset?
            get() = presets.firstOrNull { FytPhysicalRadio.presetMatches(it, frequency, pi) }

        private val resolvedStationIdentity: FmResolvedStationIdentity
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
                )

        val displayStation: String
            get() = resolvedStationIdentity.canonicalName

        val stableStationId: String
            get() = resolvedStationIdentity.stableId
    }
''',
        "state station identity",
    )

    af_block = r'''    private fun launchAlternativeFrequencyCheck(manual: Boolean) {
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
                        .take(12)
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
                                    "(RSSI $currentRssi → ${selected.rssi})",
                            nativeResult = null,
                        )
                        return@launch
                    }

                    if (tryNativeAfFallback(fm, before, expectedPi, knownFrequencies, manual)) return@launch

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
        )
    }

    private suspend fun tryNativeAfFallback(
        fm: FmNative,
        before: State,
        expectedPi: Int,
        knownFrequencies: List<Float>,
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

        delay(260)
        repeat(4) {
            runCatching { fm.readRds() }
            delay(110)
        }
        val receivedPi = runCatching { fm.programIdentifier }.getOrDefault(0)
        if (expectedPi > 0 && receivedPi > 0 && !samePi(expectedPi, receivedPi)) {
            runCatching { fm.tune(before.frequency) }
            _state.update {
                it.copy(
                    isBusy = false,
                    frequency = before.frequency,
                    ps = before.ps,
                    pi = before.pi,
                    ecc = before.ecc,
                    afLastResult = "FYT-AF verworfen: andere PI ${receivedPi.toString(16).uppercase()}",
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
        _state.update {
            it.copy(
                isBusy = false,
                frequency = target,
                ps = before.ps,
                rt = "",
                rssi = targetRssi,
                stereo = null,
                pi = targetPi.takeIf { value -> value > 0 } ?: before.pi,
                ecc = before.ecc,
                alternativeFrequencies =
                    normalizeFrequencyList(knownFrequencies + before.frequency)
                        .filterNot { frequency -> abs(frequency - target) < 0.05f },
                afAverageRssi = 0,
                afWeakSamples = 0,
                afLastResult = result,
                afLastNativeResult = nativeResult,
            )
        }
        updateCurrentPresetIdentity()
        triggerRdsRead()
        Timber.tag(TAG).i("%s stableId=%s", result, _state.value.stableStationId)
    }

'''
    text = replace_between(
        text,
        "    private fun launchAlternativeFrequencyCheck(manual: Boolean) {",
        "    /**\n     * Manual NavRadio+-style AF cycling.",
        af_block,
        "hybrid AF engine",
    )
    text = replace_once(
        text,
        '''                        snapshot.pi > 0 &&
                        snapshot.afAverageRssi > 0 &&
''',
        '''                        (snapshot.pi > 0 || snapshot.currentPreset?.let { presetFrequencies(it).size > 1 } == true) &&
                        snapshot.afAverageRssi > 0 &&
''',
        "automatic AF identity gate",
    )
    text = replace_once(
        text,
        '''        if (!_state.value.isActive || _state.value.isScanning) return
''',
        '''        if (!_state.value.isActive || _state.value.isScanning || _state.value.isBusy) return
''',
        "poll busy guard",
    )
    text = replace_once(
        text,
        '''                name = snapshot.ps.trim().takeIf { it.isNotBlank() } ?: current.name,
''',
        '''                name =
                    FmStationIdentity.resolve(
                        rawPs = snapshot.ps,
                        storedName = current.name,
                        frequencies = allFrequencies,
                        pi = snapshot.pi.takeIf { it > 0 } ?: current.pi,
                        ecc = snapshot.ecc.ifBlank { current.ecc },
                    ).canonicalName,
''',
        "canonical preset name",
    )
    text = replace_once(
        text,
        '''    fun stablePresetKey(preset: Preset): String =
        when {
            preset.pi > 0 -> "pi:${(preset.pi and 0xffff).toString(16).padStart(4, '0')}"
            usefulStationIdentity(preset.name).isNotBlank() -> "name:${usefulStationIdentity(preset.name)}"
            else -> "freq:${frequencyKey(preset.frequency)}"
        }
''',
        '''    fun stablePresetKey(preset: Preset): String =
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
        )
''',
        "stable preset identity",
    )
    text = replace_once(
        text,
        '''                name =
                    group
                        .map { it.name.trim() }
                        .firstOrNull { usefulStationIdentity(it).isNotBlank() }
                        ?: first.name,
                pi = group.firstOrNull { it.pi > 0 }?.pi ?: first.pi,
                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
''',
        '''                name =
                    FmStationIdentity.resolve(
                        rawPs = group.firstOrNull()?.name.orEmpty(),
                        storedName = group.map { it.name.trim() }.firstOrNull { usefulStationIdentity(it).isNotBlank() },
                        frequencies = frequencies,
                        pi = group.firstOrNull { it.pi > 0 }?.pi ?: first.pi,
                        ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
                    ).canonicalName,
                pi = group.firstOrNull { it.pi > 0 }?.pi ?: first.pi,
                ecc = group.firstOrNull { it.ecc.isNotBlank() }?.ecc ?: first.ecc,
''',
        "merge canonical station name",
    )
    text = replace_once(
        text,
        '''        val left = usefulStationIdentity(first.name)
        val right = usefulStationIdentity(second.name)
        return left.isNotBlank() && left == right
    }

    private fun samePresetRecord(
''',
        '''        return stablePresetKey(first) == stablePresetKey(second)
    }

    private fun samePresetRecord(
''',
        "same preset station",
    )
    text = replace_once(
        text,
        '''    private fun sameScanStation(
        first: ScanResult,
        second: ScanResult,
    ): Boolean {
        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        val left = usefulStationIdentity(first.name)
        val right = usefulStationIdentity(second.name)
        return left.isNotBlank() && left == right
    }
''',
        '''    private fun sameScanStation(
        first: ScanResult,
        second: ScanResult,
    ): Boolean {
        if (first.pi > 0 && second.pi > 0) return samePi(first.pi, second.pi)
        val firstIdentity = FmStationIdentity.resolve(first.name, null, scanFrequencies(first), first.pi, first.ecc)
        val secondIdentity = FmStationIdentity.resolve(second.name, null, scanFrequencies(second), second.pi, second.ecc)
        return firstIdentity.stableId != "unknown" && firstIdentity.stableId == secondIdentity.stableId
    }
''',
        "same scan identity",
    )
    text = replace_once(
        text,
        '''    private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()
''',
        '''    private fun Int?.orZero(): Int = this ?: 0

    private fun frequencyKey(value: Float): Int = (normalizeFrequency(value) * 10f).roundToInt()
''',
        "nullable PI helper",
    )
    return text


def patch_order_store(text: str) -> str:
    text = replace_once(
        text,
        '''                FytPhysicalRadio.stablePresetKey(it) == key && ordered.none { existing -> samePreset(existing, it) }
''',
        '''                key in FytPhysicalRadio.presetOrderKeys(it) && ordered.none { existing -> samePreset(existing, it) }
''',
        "order alias matching",
    )
    return text


def patch_logo_resolver(text: str) -> str:
    text = replace_once(
        text,
        '''            val identity = AustrianFmStationCatalog.identify(stationName, frequencies)
            if (pi <= 0 && identity == null && !isSafeAutomaticName(stationName)) return@withContext cached
''',
        '''            val resolvedStation = FmStationIdentity.resolve(stationName, null, frequencies, pi, ecc)
            val identity = AustrianFmStationCatalog.identify(resolvedStation.canonicalName, frequencies)
            if (pi <= 0 && identity == null && !isSafeAutomaticName(resolvedStation.canonicalName)) return@withContext cached
''',
        "logo resolved station identity",
    )
    text = replace_once(
        text,
        '''            val exactLocal = exactLocalMatch(identity?.canonicalName ?: stationName, RadioStationStore.get(appContext).stations.value)
''',
        '''            val exactLocal = exactLocalMatch(identity?.canonicalName ?: resolvedStation.canonicalName, RadioStationStore.get(appContext).stations.value)
''',
        "logo local canonical query",
    )
    text = replace_once(
        text,
        '''            val identity = AustrianFmStationCatalog.identify(stationName, frequencies)
            val query = identity?.canonicalName ?: stationName
''',
        '''            val resolvedStation = FmStationIdentity.resolve(stationName, null, frequencies, pi, ecc)
            val identity = AustrianFmStationCatalog.identify(resolvedStation.canonicalName, frequencies)
            val query = identity?.canonicalName ?: resolvedStation.canonicalName
''',
        "manual logo canonical query",
    )
    old_cache = '''    private fun cacheKey(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int,
        ecc: String?,
    ): String {
        if (pi > 0) {
            val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
            val resolvedEcc = normaliseEcc(ecc) ?: RadioDnsLogoResolver.defaultEcc(context)
            val gcc = resolvedEcc?.let { "${piHex.first()}$it" } ?: "unknown"
            return "gcc_${gcc}_pi_$piHex"
        }
        val identity = normalizeAlias(stationName).ifBlank { "unknown" }.replace(' ', '_')
        return "name_${identity}_${(frequency * 100f).roundToInt()}"
    }
'''
    new_cache = '''    private fun cacheKey(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int,
        ecc: String?,
    ): String {
        val resolved = FmStationIdentity.resolve(stationName, null, listOf(frequency), pi, ecc)
        if (resolved.recognized) return "station_${resolved.stableId.replace(':', '_')}"
        if (pi > 0) {
            val piHex = (pi and 0xffff).toString(16).padStart(4, '0')
            val resolvedEcc = normaliseEcc(ecc) ?: RadioDnsLogoResolver.defaultEcc(context)
            val gcc = resolvedEcc?.let { "${piHex.first()}$it" } ?: "unknown"
            return "gcc_${gcc}_pi_$piHex"
        }
        val identity = normalizeAlias(resolved.canonicalName).ifBlank { "unknown" }.replace(' ', '_')
        return "name_${identity}_${(frequency * 100f).roundToInt()}"
    }
'''
    return replace_once(text, old_cache, new_cache, "stable logo cache key")


def patch_version(text: str) -> str:
    text = replace_once(text, "versionCode = 1370029", "versionCode = 1370030", "versionCode")
    text = replace_once(text, 'versionName = "13.7.20"', 'versionName = "13.7.21"', "versionName")
    return text


update("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt", patch_fyt)
update("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt", patch_order_store)
update("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/ReliableFmStationLogoResolver.kt", patch_logo_resolver)
update("app/build.gradle.kts", patch_version)

checks = {
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt": [
        "stableStationId",
        "measureAlternativeFrequency",
        "tryNativeAfFallback",
        "Keine stärkere passende Frequenz gefunden",
        "snapshot.currentPreset?.let { presetFrequencies(it).size > 1 }",
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt": [
        "key in FytPhysicalRadio.presetOrderKeys(it)",
    ],
    "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/ReliableFmStationLogoResolver.kt": [
        "station_${resolved.stableId.replace(':', '_')}",
    ],
    "app/build.gradle.kts": ["versionCode = 1370030", 'versionName = "13.7.21"'],
}
for path, markers in checks.items():
    source = (ROOT / path).read_text(encoding="utf-8")
    for marker in markers:
        if marker not in source:
            raise SystemExit(f"Missing marker in {path}: {marker}")

print("Applied stable FM identity, favourite-order migration and hybrid AF selection for 13.7.21")
