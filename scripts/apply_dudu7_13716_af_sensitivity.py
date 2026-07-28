#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f"Missing marker for {label}")
    return text.replace(old, new, 1)


# Version bump.
build_path = "app/build.gradle.kts"
build = read(build_path)
build = replace_once(build, "versionCode = 1370024", "versionCode = 1370025", "versionCode")
build = replace_once(build, 'versionName = "13.7.15"', 'versionName = "13.7.16"', "versionName")
write(build_path, build)


# Native FM backend: NavRadio+-style RSSI thresholding and manual AF cycling.
radio_path = "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
radio = read(radio_path)
radio = replace_once(
    radio,
    "    private const val KEY_REG = \"reg_enabled\"\n",
    "    private const val KEY_REG = \"reg_enabled\"\n"
    "    private const val KEY_AF_SENSITIVITY = \"af_sensitivity\"\n",
    "AF preference key",
)
radio = replace_once(
    radio,
    "    private const val AF_SWITCH_COOLDOWN_MS = 20_000L\n",
    "    private const val AF_SWITCH_COOLDOWN_MS = 20_000L\n"
    "    private const val DEFAULT_AF_SENSITIVITY = 30\n"
    "    private const val MIN_AF_SENSITIVITY = 15\n"
    "    private const val MAX_AF_SENSITIVITY = 50\n"
    "    private const val AF_RSSI_WINDOW_SIZE = 4\n"
    "    private const val AF_WEAK_SAMPLE_COUNT = 3\n"
    "    private const val AF_RSSI_HYSTERESIS = 3\n",
    "AF constants",
)
radio = replace_once(
    radio,
    "        val afEnabled: Boolean = true,\n        val taEnabled: Boolean = true,\n",
    "        val afEnabled: Boolean = true,\n"
    "        val afSensitivity: Int = DEFAULT_AF_SENSITIVITY,\n"
    "        val afAverageRssi: Int = 0,\n"
    "        val afWeakSamples: Int = 0,\n"
    "        val firmwareFmSensitivity: Int? = null,\n"
    "        val taEnabled: Boolean = true,\n",
    "AF state",
)
radio = replace_once(
    radio,
    "    private var pendingPsCount = 0\n",
    "    private var pendingPsCount = 0\n"
    "    private val rssiWindow = ArrayDeque<Int>()\n",
    "RSSI window",
)
radio = replace_once(
    radio,
    "                    afEnabled = prefs.getBoolean(KEY_AF, true),\n                    taEnabled = prefs.getBoolean(KEY_TA, true),\n",
    "                    afEnabled = prefs.getBoolean(KEY_AF, true),\n"
    "                    afSensitivity =\n"
    "                        prefs.getInt(KEY_AF_SENSITIVITY, DEFAULT_AF_SENSITIVITY)\n"
    "                            .coerceIn(MIN_AF_SENSITIVITY, MAX_AF_SENSITIVITY),\n"
    "                    firmwareFmSensitivity = systemProperty(\"ro.fyt.fmsens\").toIntOrNull(),\n"
    "                    taEnabled = prefs.getBoolean(KEY_TA, true),\n",
    "AF initialization",
)

# Reset sampling when a station/frequency context changes.
radio = radio.replace(
    "                pendingPsCount = 0\n                persistFrequency(target)\n",
    "                pendingPsCount = 0\n                resetAfSampling()\n                persistFrequency(target)\n",
    1,
)
radio = radio.replace(
    "            pendingPsCount = 0\n            _state.update {\n",
    "            pendingPsCount = 0\n            resetAfSampling()\n            _state.update {\n",
    1,
)
radio = radio.replace(
    "                        alternativeFrequencies = presetIdentity?.alternativeFrequencies.orEmpty(),\n                        pty = 0,\n",
    "                        alternativeFrequencies = presetIdentity?.alternativeFrequencies.orEmpty(),\n"
    "                        afAverageRssi = 0,\n"
    "                        afWeakSamples = 0,\n"
    "                        pty = 0,\n",
    2,
)
radio = replace_once(
    radio,
    "                    alternativeFrequencies = emptyList(),\n                    pty = 0,\n                    tp = false,\n",
    "                    alternativeFrequencies = emptyList(),\n"
    "                    afAverageRssi = 0,\n"
    "                    afWeakSamples = 0,\n"
    "                    pty = 0,\n"
    "                    tp = false,\n",
    "power-off AF reset",
)

radio = replace_once(
    radio,
    "    fun setTaEnabled(enabled: Boolean) {\n",
    "    fun setAfSensitivity(value: Int) {\n"
    "        val normalized = value.coerceIn(MIN_AF_SENSITIVITY, MAX_AF_SENSITIVITY)\n"
    "        persistInt(KEY_AF_SENSITIVITY, normalized)\n"
    "        _state.update { current ->\n"
    "            val weakSamples =\n"
    "                if (current.afAverageRssi > 0 && current.afAverageRssi < normalized) {\n"
    "                    current.afWeakSamples.coerceAtLeast(1)\n"
    "                } else {\n"
    "                    0\n"
    "                }\n"
    "            current.copy(afSensitivity = normalized, afWeakSamples = weakSamples)\n"
    "        }\n"
    "    }\n\n"
    "    fun setTaEnabled(enabled: Boolean) {\n",
    "AF sensitivity setter",
)

start = radio.index("    fun requestAlternativeFrequency() {")
end = radio.index("    fun saveCurrentPreset() {", start)
new_af_block = '''    fun requestAlternativeFrequency() {
        launchAlternativeFrequencyCheck(manual = true)
    }

    private fun requestAutomaticAlternativeFrequency() {
        launchAlternativeFrequencyCheck(manual = false)
    }

    private fun launchAlternativeFrequencyCheck(manual: Boolean) {
        if (afJob?.isActive == true) return
        afJob =
            scope.launch {
                val fm = native ?: return@launch
                val before = _state.value
                val now = System.currentTimeMillis()
                if (!manual && now - lastAfSwitchAt < AF_SWITCH_COOLDOWN_MS) return@launch
                if (
                    !before.isActive ||
                    !before.afEnabled ||
                    before.isScanning ||
                    before.isBusy ||
                    before.pi <= 0
                ) {
                    return@launch
                }
                if (
                    !manual &&
                    (before.afAverageRssi <= 0 ||
                        before.afAverageRssi >= before.afSensitivity ||
                        before.afWeakSamples < AF_WEAK_SAMPLE_COUNT)
                ) {
                    return@launch
                }

                Timber.tag(TAG).d(
                    "AF check manual=%s RSSI=%d average=%d threshold=%d weakSamples=%d PI=%04X",
                    manual,
                    before.rssi,
                    before.afAverageRssi,
                    before.afSensitivity,
                    before.afWeakSamples,
                    before.pi,
                )
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
                    Timber.tag(TAG).i(
                        "AF switched %.1f -> %.1f for PI=%04X manual=%s averageRSSI=%d threshold=%d",
                        before.frequency,
                        frequency,
                        before.pi,
                        manual,
                        before.afAverageRssi,
                        before.afSensitivity,
                    )
                    lastAfSwitchAt = System.currentTimeMillis()
                    persistFrequency(frequency)
                    rssiWindow.clear()
                    _state.update {
                        it.copy(
                            frequency = frequency,
                            rt = "",
                            stereo = null,
                            pi = before.pi,
                            ecc = before.ecc,
                            afAverageRssi = 0,
                            afWeakSamples = 0,
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
        val candidates =
            normalizeFrequencyList(presetFrequencies(preset) + current.alternativeFrequencies)
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

            _state.update {
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
            if (!runCatching { fm.tune(target) }.getOrDefault(false)) {
                _state.value = before.copy(isBusy = false, error = "AF-Frequenz konnte nicht eingestellt werden")
                return@launch
            }

            delay(500)
            repeat(5) {
                runCatching { fm.readRds() }
                delay(150)
            }
            val receivedPi = runCatching { fm.programIdentifier }.getOrDefault(0)
            val expectedPi = before.pi.takeIf { it > 0 } ?: preset.pi
            if (expectedPi > 0 && receivedPi > 0 && !samePi(expectedPi, receivedPi)) {
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
                    pi = receivedPi.takeIf { value -> value > 0 } ?: expectedPi,
                    alternativeFrequencies = candidates.filterNot { value -> abs(value - target) < 0.05f },
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

'''
radio = radio[:start] + new_af_block + radio[end:]

old_poll = '''                    if (
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
new_poll = '''                    if (
                        snapshot.afEnabled &&
                        snapshot.pi > 0 &&
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
'''
radio = replace_once(radio, old_poll, new_poll, "automatic AF polling")

radio = replace_once(
    radio,
    "        val rssi = runCatching { fm.rssi }.getOrDefault(_state.value.rssi)\n        val stereoState =",
    "        val rssi = runCatching { fm.rssi }.getOrDefault(_state.value.rssi)\n"
    "        if (rssi > 0) {\n"
    "            rssiWindow.addLast(rssi)\n"
    "            while (rssiWindow.size > AF_RSSI_WINDOW_SIZE) rssiWindow.removeFirst()\n"
    "        }\n"
    "        val averageRssi =\n"
    "            if (rssiWindow.isNotEmpty()) rssiWindow.sum() / rssiWindow.size else _state.value.afAverageRssi\n"
    "        val weakSamples =\n"
    "            when {\n"
    "                averageRssi <= 0 -> 0\n"
    "                averageRssi < _state.value.afSensitivity -> (_state.value.afWeakSamples + 1).coerceAtMost(AF_WEAK_SAMPLE_COUNT)\n"
    "                averageRssi >= _state.value.afSensitivity + AF_RSSI_HYSTERESIS -> 0\n"
    "                else -> (_state.value.afWeakSamples - 1).coerceAtLeast(0)\n"
    "            }\n"
    "        val stereoState =",
    "RSSI averaging",
)
radio = replace_once(
    radio,
    "                rssi = rssi,\n                stereo = stereoState.takeIf",
    "                rssi = rssi,\n"
    "                afAverageRssi = averageRssi,\n"
    "                afWeakSamples = weakSamples,\n"
    "                stereo = stereoState.takeIf",
    "RSSI state update",
)
radio = replace_once(
    radio,
    "    private fun applyRegionalConfig(fm: FmNative, enabled: Boolean) {\n",
    "    private fun resetAfSampling() {\n"
    "        rssiWindow.clear()\n"
    "        _state.update { it.copy(afAverageRssi = 0, afWeakSamples = 0) }\n"
    "    }\n\n"
    "    private fun applyRegionalConfig(fm: FmNative, enabled: Boolean) {\n",
    "AF reset helper",
)
radio = replace_once(
    radio,
    "    private fun updateCurrentPresetIdentity() {\n",
    "    private fun persistInt(key: String, value: Int) {\n"
    "        appContext\n"
    "            ?.getSharedPreferences(PREFS, Context.MODE_PRIVATE)\n"
    "            ?.edit()\n"
    "            ?.putInt(key, value)\n"
    "            ?.apply()\n"
    "    }\n\n"
    "    private fun updateCurrentPresetIdentity() {\n",
    "integer preference helper",
)
write(radio_path, radio)


# FM UI: slider and double-tap gesture.
screen_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/PhysicalRadioScreen.kt"
screen = read(screen_path)
screen = replace_once(
    screen,
    "import androidx.compose.material3.OutlinedTextField\n",
    "import androidx.compose.material3.OutlinedTextField\nimport androidx.compose.material3.Slider\n",
    "Slider import",
)
screen = replace_once(
    screen,
    "                                    onEdit = { editingPreset = preset },\n",
    "                                    onNextAf = {\n"
    "                                        if (isActive) {\n"
    "                                            radio.tuneNextAlternativeFrequency(preset)\n"
    "                                        } else {\n"
    "                                            playerConnection?.pause()\n"
    "                                            radio.tunePreset(preset)\n"
    "                                        }\n"
    "                                    },\n"
    "                                    onEdit = { editingPreset = preset },\n",
    "double-tap callback",
)
screen = replace_once(
    screen,
    "    onPlay: () -> Unit,\n    onEdit: () -> Unit,\n",
    "    onPlay: () -> Unit,\n    onNextAf: () -> Unit,\n    onEdit: () -> Unit,\n",
    "favourite callback parameter",
)
screen = replace_once(
    screen,
    "                ).combinedClickable(onClick = onPlay, onLongClick = onEdit)\n",
    "                ).combinedClickable(\n"
    "                    onClick = onPlay,\n"
    "                    onDoubleClick = onNextAf,\n"
    "                    onLongClick = onEdit,\n"
    "                )\n",
    "double-tap gesture",
)

sensitivity_item = '''        item {
            Column(
                verticalArrangement = Arrangement.spacedBy(4.dp),
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f))
                        .padding(horizontal = 12.dp, vertical = 10.dp),
            ) {
                Text(
                    "AF-Sensitivität: ${state.afSensitivity}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "Höher bedeutet einen früheren Wechsel. Aktueller geglätteter Empfang: " +
                        if (state.afAverageRssi > 0) state.afAverageRssi.toString() else "–",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Slider(
                    value = state.afSensitivity.toFloat(),
                    onValueChange = { radio.setAfSensitivity(it.roundToInt()) },
                    valueRange = 15f..50f,
                    steps = 34,
                )
                Text(
                    "Automatisches AF startet nach drei schwachen Messungen. Doppeltipp auf den laufenden Favoriten wechselt sofort zur nächsten gespeicherten AF-Frequenz.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
'''
af_item = '''        item {
            RadioSettingRow(
                title = "AF – Alternative Frequenzen",
                description = "Bei schwachem Empfang nach einer stärkeren Frequenz desselben Senders suchen.",
                checked = state.afEnabled,
                onCheckedChange = radio::setAfEnabled,
            )
        }
'''
screen = replace_once(screen, af_item, af_item + sensitivity_item, "AF sensitivity UI")
write(screen_path, screen)


# Diagnostics: expose the effective and firmware thresholds.
diag_path = "app/src/dudu7/kotlin/com/metrolist/music/ui/screens/radio/FmRadioDiagnostics.kt"
diag = read(diag_path)
diag = replace_once(
    diag,
    "        Text(\n            \"AF: ${if (state.alternativeFrequencies.isEmpty()) \"–\" else FytPhysicalRadio.formatFrequencies(state.alternativeFrequencies)}\",\n        )\n",
    "        Text(\n"
    "            \"AF: ${if (state.alternativeFrequencies.isEmpty()) \"–\" else FytPhysicalRadio.formatFrequencies(state.alternativeFrequencies)}\",\n"
    "        )\n"
    "        Text(\n"
    "            \"RSSI: aktuell ${state.rssi}  •  Mittel ${state.afAverageRssi.takeIf { it > 0 } ?: \"–\"}  •  \" +\n"
    "                \"Schwelle ${state.afSensitivity}  •  schwach ${state.afWeakSamples}/3\",\n"
    "        )\n"
    "        Text(\n"
    "            \"FYT ro.fyt.fmsens: ${state.firmwareFmSensitivity ?: \"–\"}\",\n"
    "            style = MaterialTheme.typography.bodySmall,\n"
    "        )\n",
    "AF diagnostics",
)
write(diag_path, diag)


checks = {
    build_path: ["versionCode = 1370025", 'versionName = "13.7.16"'],
    radio_path: [
        "KEY_AF_SENSITIVITY",
        "afSensitivity: Int",
        "AF_WEAK_SAMPLE_COUNT",
        "requestAutomaticAlternativeFrequency",
        "tuneNextAlternativeFrequency",
        "ro.fyt.fmsens",
        "averageRssi < snapshot.afSensitivity",
    ],
    screen_path: [
        "AF-Sensitivität:",
        "onDoubleClick = onNextAf",
        "radio.tuneNextAlternativeFrequency(preset)",
    ],
    diag_path: ["Schwelle ${state.afSensitivity}", "ro.fyt.fmsens"],
}
for path, needles in checks.items():
    text = read(path)
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path}: missing {missing}")

print("Dudu7 13.7.16 AF sensitivity patch applied successfully")
