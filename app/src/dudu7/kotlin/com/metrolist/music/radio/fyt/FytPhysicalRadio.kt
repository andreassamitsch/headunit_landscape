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
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
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
    private const val FM_MIN = 87.5f
    private const val FM_MAX = 108.0f
    private const val FM_STEP = 0.1f

    data class Preset(
        val frequency: Float,
        val name: String,
    )

    data class State(
        val initialized: Boolean = false,
        val libraryLoaded: Boolean = false,
        val isActive: Boolean = false,
        val isMuted: Boolean = false,
        val isBusy: Boolean = false,
        val frequency: Float = 99.7f,
        val ps: String = "",
        val rt: String = "",
        val rssi: Int = 0,
        val stereo: Boolean = false,
        val pi: Int = 0,
        val pty: Int = 0,
        val tp: Boolean = false,
        val ta: Boolean = false,
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
    private var audioManager: AudioManager? = null
    private var focusRequest: AudioFocusRequest? = null

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
                        pi = 0,
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
                    ps = "",
                    rt = "",
                    rssi = 0,
                    stereo = false,
                    pi = 0,
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
            _state.update { it.copy(isBusy = true, error = null, ps = "", rt = "", pi = 0, pty = 0) }
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
            if (_state.value.isBusy) return@launch
            _state.update { it.copy(isBusy = true, error = null, ps = "", rt = "") }
            val fm = native
            if (fm == null) {
                _state.update { it.copy(isBusy = false, error = "Tuner ist nicht verfügbar") }
                return@launch
            }

            val nativeResult = runCatching { fm.seek(_state.value.frequency, up) }.getOrNull()
            val nativeFrequency = nativeResult?.firstOrNull()?.takeIf { it in FM_MIN..FM_MAX }
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

    fun saveCurrentPreset() {
        val snapshot = _state.value
        val preset = Preset(snapshot.frequency, snapshot.ps.ifBlank { "FM ${formatFrequency(snapshot.frequency)}" })
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
            if (rssi >= 38) return candidate
        }
        return null
    }

    private fun installRdsListener() {
        FmService.setRdsListener { eventType, value1, _, _ ->
            when (eventType) {
                0 -> _state.update { it.copy(tp = value1 != 0) }
                2, 7 -> _state.update { it.copy(pty = value1) }
                6 -> _state.update { it.copy(ta = value1 != 0) }
                10, 11 -> triggerRdsRead()
                14 -> _state.update { it.copy(pi = value1) }
            }
        }
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob =
            scope.launch {
                while (isActive && _state.value.isActive) {
                    pollTuner()
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
        if (!_state.value.isActive) return
        runCatching { fm.readRds() }
        val ps = runCatching { fm.psString }.getOrDefault("")
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
    }

    private fun cleanupHardware() {
        pollingJob?.cancel()
        pollingJob = null
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

    private fun persistPresets(presets: List<Preset>) {
        val encoded =
            presets.joinToString("\n") { preset ->
                "${preset.frequency}\t${preset.name.replace('\n', ' ').replace('\t', ' ')}"
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
                val parts = line.split('\t', limit = 2)
                val frequency = parts.firstOrNull()?.toFloatOrNull() ?: return@mapNotNull null
                Preset(normalizeFrequency(frequency), parts.getOrNull(1).orEmpty().ifBlank { "FM ${formatFrequency(frequency)}" })
            }.distinctBy { it.frequency }
            .sortedBy { it.frequency }
            .toList()

    private fun normalizeFrequency(value: Float): Float =
        ((value.coerceIn(FM_MIN, FM_MAX) * 10f).roundToInt() / 10f)

    private fun systemProperty(name: String): String =
        runCatching {
            val clazz = Class.forName("android.os.SystemProperties")
            val method = clazz.getMethod("get", String::class.java, String::class.java)
            method.invoke(null, name, "") as String
        }.getOrDefault("")

    fun formatFrequency(value: Float): String = String.format(java.util.Locale.GERMANY, "%.1f", value)

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
