from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Patch context not found: {label}")
    return text.replace(old, new, 1)


syu_path = Path("app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7SyuRadioIpc.kt")
text = syu_path.read_text()

text = replace_once(
    text,
    '''    fun releaseFmSource() {
        client?.setFmRequested(false)
    }

    fun release() {''',
    '''    fun releaseFmSource() {
        client?.setFmRequested(false)
    }

    fun onMetroListTuneRequested(
        reason: String,
        targetFrequency: Float,
    ) {
        client?.onMetroListTuneRequested(reason, targetFrequency)
    }

    fun resetFrequencyAnchor(
        reason: String,
        baselineFrequency: Float? = null,
    ) {
        client?.resetFrequencyAnchor(reason, baselineFrequency)
    }

    fun release() {''',
    "public anchor API",
)

text = replace_once(
    text,
    '''        private var sourceOwnerPackage = ""
        private var sourceOwnedAt = 0L
        private var lastObservedFrequency = Float.NaN
        private var lastObservedAt = 0L
        private var lastRedirectDirection: Boolean? = null
        private var lastRedirectAt = 0L''',
    '''        private var sourceOwnerPackage = ""
        private var sourceOwnedAt = 0L
        private val frequencyAnchor = SyuFmFrequencyAnchor()
        private val redirectTuneGate = SyuFmRedirectTuneGate()
        private var lastRedirectDirection: Boolean? = null
        private var lastRedirectAt = 0L''',
    "anchor state",
)

text = replace_once(
    text,
    '''        fun setFmRequested(requested: Boolean): Boolean {
            fmRequested = requested
            val immediate = mainModule != null
            worker.post {
                if (released.get()) return@post
                if (requested) activateForFm("powerOn") else deactivateForFm("powerOff")
            }
            return immediate
        }

        fun release() {''',
    '''        fun setFmRequested(requested: Boolean): Boolean {
            fmRequested = requested
            val immediate = mainModule != null
            worker.post {
                if (released.get()) return@post
                if (requested) {
                    resetFrequencyAnchorInternal("powerOn", null)
                    activateForFm("powerOn")
                } else {
                    deactivateForFm("powerOff")
                }
            }
            return immediate
        }

        fun onMetroListTuneRequested(
            reason: String,
            targetFrequency: Float,
        ) {
            val now = SystemClock.elapsedRealtime()
            val target = decodeSyuFmFrequency(targetFrequency) ?: return
            val redirectTune = redirectTuneGate.consume(now)
            if (redirectTune) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_ANCHOR",
                    "reason=$reason target=$target decision=preserveRedirect " +
                        "anchor=${frequencyAnchor.current().frequency}",
                )
            } else {
                resetFrequencyAnchorInternal(reason, target)
            }
        }

        fun resetFrequencyAnchor(
            reason: String,
            baselineFrequency: Float?,
        ) {
            resetFrequencyAnchorInternal(reason, baselineFrequency)
        }

        fun release() {''',
    "client anchor API",
)

text = replace_once(
    text,
    '''            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
        }

        private fun bindCurrentEndpoint() {''',
    '''            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
            resetFrequencyAnchorInternal("connectionReset", null)
        }

        private fun bindCurrentEndpoint() {''',
    "connection reset",
)

text = replace_once(
    text,
    '''            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
            lastObservedFrequency = Float.NaN
            MediaKeyDiagnostics.record(''',
    '''            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
            resetFrequencyAnchorInternal(source, null)
            MediaKeyDiagnostics.record(''',
    "deactivation reset",
)

text = replace_once(
    text,
    '''                val owner = strings?.firstOrNull().orEmpty()
                sourceOwnerPackage = owner
                sourceOwnedAt =
                    if (owner == appContext.packageName) SystemClock.elapsedRealtime() else 0L
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_OWNER",
                    "package=$owner ours=${owner == appContext.packageName} fmRequested=$fmRequested",
                )''',
    '''                val owner = strings?.firstOrNull().orEmpty()
                val wasOurs = sourceOwnerPackage == appContext.packageName
                val isOurs = owner == appContext.packageName
                sourceOwnerPackage = owner
                sourceOwnedAt = if (isOurs) SystemClock.elapsedRealtime() else 0L
                if (wasOurs && !isOurs) {
                    resetFrequencyAnchorInternal("sourceOwnerLost:$owner", null)
                }
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_OWNER",
                    "package=$owner ours=$isOurs fmRequested=$fmRequested " +
                        "anchor=${frequencyAnchor.current().frequency}",
                )''',
    "owner reset",
)

start = text.index("        private fun redirectExternalTune(")
end = text.index("        private fun logFailure(", start)
redirect = '''        private fun redirectExternalTune(
            observedFrequency: Float,
            source: String,
        ) {
            val now = SystemClock.elapsedRealtime()
            val snapshot = FytPhysicalRadio.state.value
            val currentAnchor = frequencyAnchor.current()

            val hardIgnoreReason =
                when {
                    !fmRequested -> "fmNotRequested"
                    sourceOwnerPackage != appContext.packageName -> "notSourceOwner:$sourceOwnerPackage"
                    !snapshot.isActive -> "fmInactive"
                    snapshot.presets.size < 2 -> "notEnoughFavourites"
                    else -> null
                }
            if (hardIgnoreReason != null) {
                resetFrequencyAnchorInternal(hardIgnoreReason, null)
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency anchor=${currentAnchor.frequency} " +
                        "current=${snapshot.frequency} decision=ignore reason=$hardIgnoreReason",
                )
                return
            }

            val baselineReason =
                when {
                    sourceOwnedAt <= 0L || now - sourceOwnedAt < SYU_REDIRECT_ARM_DELAY_MS -> "ownerGrace"
                    snapshot.isBusy -> "metroListBusy"
                    snapshot.isScanning -> "scanActive"
                    abs(observedFrequency - snapshot.frequency) < SYU_FREQUENCY_TOLERANCE -> "matchesMetroList"
                    else -> null
                }
            if (baselineReason != null) {
                if (baselineReason == "ownerGrace" && currentAnchor.frequency.isNaN()) {
                    frequencyAnchor.reset(observedFrequency, now)
                }
                lastRedirectDirection = null
                lastRedirectAt = 0L
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency anchor=${currentAnchor.frequency} " +
                        "current=${snapshot.frequency} decision=ignore reason=$baselineReason",
                )
                return
            }

            if (!currentAnchor.frequency.isNaN() &&
                abs(observedFrequency - currentAnchor.frequency) < SYU_FREQUENCY_TOLERANCE &&
                now - currentAnchor.observedAt < SYU_EXTERNAL_DUPLICATE_WINDOW_MS
            ) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency anchor=${currentAnchor.frequency} " +
                        "current=${snapshot.frequency} decision=ignore reason=duplicateFrequency",
                )
                return
            }

            val observation = frequencyAnchor.observe(observedFrequency, now)
            val previousObserved = observation.previousFrequency
            if (previousObserved.isNaN()) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency current=${snapshot.frequency} " +
                        "decision=baseline reason=anchorInitialized",
                )
                return
            }

            val next = inferExternalFmDirection(previousObserved, observedFrequency)
            if (next == null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency anchor=$previousObserved " +
                        "current=${snapshot.frequency} decision=ignore reason=noDirection",
                )
                return
            }

            if (lastRedirectDirection == next && now - lastRedirectAt < SYU_REDIRECT_DEDUP_WINDOW_MS) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency anchor=$previousObserved " +
                        "current=${snapshot.frequency} direction=${if (next) "NEXT" else "PREVIOUS"} " +
                        "decision=duplicate",
                )
                return
            }

            redirectTuneGate.expect(now, SYU_REDIRECT_TUNE_EXPECTATION_MS)
            val handled = PhysicalFmMediaKeyBridge.handleDirection(next)
            if (handled) {
                lastRedirectDirection = next
                lastRedirectAt = now
            } else {
                redirectTuneGate.clear()
            }
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_FM_REDIRECT",
                "source=$source observed=$observedFrequency anchor=$previousObserved " +
                    "current=${snapshot.frequency} direction=${if (next) "NEXT" else "PREVIOUS"} " +
                    "handled=$handled",
            )
        }

        private fun resetFrequencyAnchorInternal(
            reason: String,
            baselineFrequency: Float?,
        ) {
            val normalizedBaseline = baselineFrequency?.let(::decodeSyuFmFrequency)
            val previous = frequencyAnchor.reset(normalizedBaseline, SystemClock.elapsedRealtime())
            redirectTuneGate.clear()
            lastRedirectDirection = null
            lastRedirectAt = 0L
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_FM_ANCHOR",
                "reason=$reason previous=$previous baseline=${normalizedBaseline ?: "none"}",
            )
        }

'''
text = text[:start] + redirect + text[end:]

marker = "internal const val SYU_MAIN_MODULE = 0"
helper = '''internal class SyuFmFrequencyAnchor {
    data class Observation(
        val previousFrequency: Float,
        val previousAt: Long,
    )

    data class Current(
        val frequency: Float,
        val observedAt: Long,
    )

    private var frequency = Float.NaN
    private var observedAt = 0L

    @Synchronized
    fun observe(
        observedFrequency: Float,
        now: Long,
    ): Observation {
        val previous = Observation(frequency, observedAt)
        frequency = observedFrequency
        observedAt = now
        return previous
    }

    @Synchronized
    fun reset(
        baselineFrequency: Float? = null,
        now: Long = 0L,
    ): Float {
        val previous = frequency
        frequency = baselineFrequency ?: Float.NaN
        observedAt = if (baselineFrequency == null) 0L else now
        return previous
    }

    @Synchronized
    fun current(): Current = Current(frequency, observedAt)
}

internal class SyuFmRedirectTuneGate {
    private var expectedUntil = 0L

    @Synchronized
    fun expect(
        now: Long,
        windowMs: Long,
    ) {
        expectedUntil = now + windowMs
    }

    @Synchronized
    fun consume(now: Long): Boolean {
        val expected = expectedUntil > 0L && now <= expectedUntil
        expectedUntil = 0L
        return expected
    }

    @Synchronized
    fun clear() {
        expectedUntil = 0L
    }
}

'''
if marker not in text:
    raise RuntimeError("Patch context not found: anchor helper marker")
text = text.replace(marker, helper + marker, 1)
text = replace_once(
    text,
    '''private const val SYU_REDIRECT_DEDUP_WINDOW_MS = 450L
private const val SYU_FREQUENCY_TOLERANCE = 0.05f''',
    '''private const val SYU_REDIRECT_DEDUP_WINDOW_MS = 450L
private const val SYU_REDIRECT_TUNE_EXPECTATION_MS = 1_500L
private const val SYU_FREQUENCY_TOLERANCE = 0.05f''',
    "redirect tune expectation constant",
)
syu_path.write_text(text)

radio_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
radio = radio_path.read_text()

radio = replace_once(
    radio,
    '''            val target = normalizeFrequency(frequency)
            val context = appContext''',
    '''            val target = normalizeFrequency(frequency)
            Dudu7SyuRadioIpc.resetFrequencyAnchor("powerOn:$target", target)
            val context = appContext''',
    "power on baseline",
)

radio = replace_once(
    radio,
    '''    fun tune(frequency: Float) {
        val target = normalizeFrequency(frequency)
        if (!_state.value.isActive) {''',
    '''    fun tune(frequency: Float) {
        val target = normalizeFrequency(frequency)
        Dudu7SyuRadioIpc.onMetroListTuneRequested("tune:$target", target)
        if (!_state.value.isActive) {''',
    "tune baseline gate",
)

radio = replace_once(
    radio,
    '''            if (found != null) {
                persistFrequency(found)''',
    '''            if (found != null) {
                Dudu7SyuRadioIpc.resetFrequencyAnchor("seekResult:$found", found)
                persistFrequency(found)''',
    "seek result baseline",
)

radio = replace_once(
    radio,
    '''    fun startAutoScan() {
        if (_state.value.isScanning) return
        scanJob?.cancel()''',
    '''    fun startAutoScan() {
        if (_state.value.isScanning) return
        Dudu7SyuRadioIpc.resetFrequencyAnchor("autoScanStart", null)
        scanJob?.cancel()''',
    "scan reset",
)

radio = replace_once(
    radio,
    '''                persistFrequency(originalFrequency)
                _state.update {''',
    '''                Dudu7SyuRadioIpc.resetFrequencyAnchor("autoScanComplete", originalFrequency)
                persistFrequency(originalFrequency)
                _state.update {''',
    "scan completion baseline",
)

radio = replace_once(
    radio,
    '''                if (blockedReason != null) {
                    _state.update { it.copy(afLastResult = blockedReason) }
                    return@launch
                }

                val preset = before.currentPreset''',
    '''                if (blockedReason != null) {
                    _state.update { it.copy(afLastResult = blockedReason) }
                    return@launch
                }

                Dudu7SyuRadioIpc.resetFrequencyAnchor(
                    reason = "afCheck:${if (manual) "manual" else "automatic"}",
                    baselineFrequency = null,
                )
                val preset = before.currentPreset''',
    "AF reset",
)

radio = replace_once(
    radio,
    '''                } finally {
                    runCatching { fm.setMute(before.isMuted) }
                }''',
    '''                } finally {
                    Dudu7SyuRadioIpc.resetFrequencyAnchor("afComplete", _state.value.frequency)
                    runCatching { fm.setMute(before.isMuted) }
                }''',
    "AF completion baseline",
)
radio_path.write_text(radio)

test_path = Path("app/src/test/kotlin/com/metrolist/music/playback/Dudu7SyuRadioIpcTest.kt")
tests = test_path.read_text()
insert = '''

    @Test
    fun `sequential syu observations preserve one direction despite MetroList favourite changes`() {
        val anchor = SyuFmFrequencyAnchor()
        assertTrue(anchor.observe(92.4f, 1L).previousFrequency.isNaN())
        assertTrue(inferExternalFmDirection(anchor.observe(92.6f, 2L).previousFrequency, 92.6f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(95.4f, 3L).previousFrequency, 95.4f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(96.5f, 4L).previousFrequency, 96.5f) == true)
        assertTrue(inferExternalFmDirection(anchor.observe(98.7f, 5L).previousFrequency, 98.7f) == true)
    }

    @Test
    fun `redirect favourite tune preserves the vendor frequency anchor`() {
        val anchor = SyuFmFrequencyAnchor()
        val gate = SyuFmRedirectTuneGate()
        anchor.reset(92.4f, 1L)
        gate.expect(now = 2L, windowMs = 1_500L)
        assertTrue(gate.consume(3L))
        val observation = anchor.observe(92.6f, 4L)
        assertEquals(92.4f, observation.previousFrequency)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 92.6f) == true)
        assertFalse(gate.consume(5L))
    }

    @Test
    fun `manual tune establishes a new known baseline`() {
        val anchor = SyuFmFrequencyAnchor()
        val gate = SyuFmRedirectTuneGate()
        anchor.observe(104.3f, 1L)
        assertFalse(gate.consume(2L))
        assertEquals(104.3f, anchor.reset(87.6f, 2L))
        val observation = anchor.observe(89.5f, 3L)
        assertEquals(87.6f, observation.previousFrequency)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 89.5f) == true)
    }

    @Test
    fun `expired redirect expectation cannot suppress a later manual tune`() {
        val gate = SyuFmRedirectTuneGate()
        gate.expect(now = 100L, windowMs = 50L)
        assertFalse(gate.consume(151L))
    }

    @Test
    fun `syu wrap sequence remains forward`() {
        val anchor = SyuFmFrequencyAnchor()
        anchor.reset(107.5f, 1L)
        val observation = anchor.observe(88.2f, 2L)
        assertTrue(inferExternalFmDirection(observation.previousFrequency, 88.2f) == true)
    }
'''
pos = tests.rfind("\n}")
if pos < 0:
    raise RuntimeError("Patch context not found: test class closing brace")
tests = tests[:pos] + insert + tests[pos:]
test_path.write_text(tests)

gradle_path = Path("app/build.gradle.kts")
gradle = gradle_path.read_text()
gradle = replace_once(gradle, "versionCode = 1370053", "versionCode = 1370054", "version code")
gradle = replace_once(gradle, 'versionName = "13.7.44"', 'versionName = "13.7.45"', "version name")
gradle_path.write_text(gradle)
