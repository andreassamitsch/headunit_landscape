package com.metrolist.music.playback

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Binder
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Parcel
import android.os.SystemClock
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Dudu7/UIS7870 Syu radio-source client.
 *
 * The physical tuner remains exclusively controlled by FmService/FmNative. This client
 * claims the Syu radio source and observes the vendor MAIN, RADIO and STEER modules.
 *
 * Real Dudu7 captures show that steering-wheel next/previous is consumed inside com.syu.ms
 * and translated directly into RADIO cmd 26 before Android MediaSession sees a key. The
 * fallback below therefore detects a vendor-originated frequency change that was not
 * initiated by MetroList and redirects it to the adjacent MetroList FM favourite.
 */
internal object Dudu7SyuRadioIpc {
    private val lock = Any()

    @Volatile
    private var client: Client? = null

    fun install(context: Context) {
        if (client != null) return
        synchronized(lock) {
            if (client != null) return
            client = Client(context.applicationContext).also(Client::start)
        }
    }

    fun claimFmSource(): Boolean = client?.setFmRequested(true) ?: false

    /** Stops callback registration. No unverified Syu source-release command is sent. */
    fun releaseFmSource() {
        client?.setFmRequested(false)
    }

    fun release() {
        synchronized(lock) {
            client?.release()
            client = null
        }
    }

    private class Client(
        private val appContext: Context,
    ) {
        private val workerThread = HandlerThread("Dudu7SyuRadioIpc").apply { start() }
        private val worker = Handler(workerThread.looper)
        private val released = AtomicBoolean(false)

        private val mainCallback = SyuModuleCallback(::onMainUpdate)
        private val radioCallback = SyuModuleCallback(::onRadioUpdate)
        private val steerCallback = SyuModuleCallback(::onSteerUpdate)

        @Volatile
        private var bound = false

        @Volatile
        private var fmRequested = false

        @Volatile
        private var mainModule: SyuRemoteModule? = null

        @Volatile
        private var radioModule: SyuRemoteModule? = null

        @Volatile
        private var steerModule: SyuRemoteModule? = null

        @Volatile
        private var connectedComponent: ComponentName? = null

        private var mainRegistered = false
        private var radioRegistered = false
        private var steerRegistered = false
        private var endpointIndex = 0

        private var sourceOwnerPackage = ""
        private var sourceOwnedAt = 0L
        private var lastObservedFrequency = Float.NaN
        private var lastObservedAt = 0L
        private var lastRedirectDirection: Boolean? = null
        private var lastRedirectAt = 0L

        private val reconnect = Runnable { bindCurrentEndpoint() }

        private val connection =
            object : ServiceConnection {
                override fun onServiceConnected(
                    name: ComponentName,
                    service: IBinder,
                ) {
                    worker.post {
                        if (released.get()) return@post
                        bound = true
                        connectedComponent = name
                        val descriptor = runCatching { service.interfaceDescriptor }.getOrNull()
                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "connected=${name.flattenToShortString()} descriptor=${descriptor.orEmpty()}",
                        )

                        val toolkit = SyuToolkit(service)
                        mainModule = resolveModule(toolkit, SYU_MAIN_MODULE, "MAIN")
                        radioModule = resolveModule(toolkit, SYU_RADIO_MODULE, "RADIO")
                        steerModule = resolveModule(toolkit, SYU_STEER_MODULE, "STEER")

                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "modules main=${mainModule != null} radio=${radioModule != null} " +
                                "steer=${steerModule != null} fmRequested=$fmRequested",
                        )
                        if (fmRequested) activateForFm("serviceConnected")
                    }
                }

                override fun onServiceDisconnected(name: ComponentName) {
                    worker.post {
                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "disconnected=${name.flattenToShortString()}",
                        )
                        resetConnectionState()
                        scheduleReconnect()
                    }
                }

                override fun onBindingDied(name: ComponentName) {
                    worker.post {
                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "bindingDied=${name.flattenToShortString()}",
                        )
                        runCatching { appContext.unbindService(this) }
                        resetConnectionState()
                        scheduleReconnect()
                    }
                }

                override fun onNullBinding(name: ComponentName) {
                    worker.post {
                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "nullBinding=${name.flattenToShortString()}",
                        )
                        runCatching { appContext.unbindService(this) }
                        resetConnectionState()
                        tryNextEndpoint()
                    }
                }
            }

        fun start() {
            worker.post(::bindCurrentEndpoint)
        }

        fun setFmRequested(requested: Boolean): Boolean {
            fmRequested = requested
            val immediate = mainModule != null
            worker.post {
                if (released.get()) return@post
                if (requested) activateForFm("powerOn") else deactivateForFm("powerOff")
            }
            return immediate
        }

        fun release() {
            if (!released.compareAndSet(false, true)) return
            worker.removeCallbacksAndMessages(null)
            deactivateForFm("serviceRelease")
            if (bound) runCatching { appContext.unbindService(connection) }
            resetConnectionState()
            MediaKeyDiagnostics.record(appContext, "SYU_IPC_STATE", "released")
            workerThread.quitSafely()
        }

        private fun resolveModule(
            toolkit: SyuToolkit,
            moduleCode: Int,
            name: String,
        ): SyuRemoteModule? =
            runCatching { toolkit.getRemoteModule(moduleCode) }
                .onFailure { error -> logFailure("resolve$name", error) }
                .getOrNull()
                ?.let(::SyuRemoteModule)

        private fun resetConnectionState() {
            bound = false
            mainRegistered = false
            radioRegistered = false
            steerRegistered = false
            mainModule = null
            radioModule = null
            steerModule = null
            connectedComponent = null
            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
        }

        private fun bindCurrentEndpoint() {
            if (released.get() || bound) return
            val endpoint = SYU_ENDPOINTS[endpointIndex.coerceIn(SYU_ENDPOINTS.indices)]
            val intent =
                Intent(SYU_TOOLKIT_ACTION).apply {
                    component = ComponentName(endpoint, SYU_TOOLKIT_SERVICE)
                }
            val accepted =
                runCatching {
                    appContext.bindService(intent, connection, Context.BIND_AUTO_CREATE)
                }.onFailure { error -> logFailure("bind:$endpoint", error) }
                    .getOrDefault(false)

            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "bindRequested package=$endpoint accepted=$accepted",
            )
            if (!accepted) tryNextEndpoint()
        }

        private fun tryNextEndpoint() {
            if (released.get()) return
            endpointIndex = (endpointIndex + 1) % SYU_ENDPOINTS.size
            scheduleReconnect()
        }

        private fun scheduleReconnect() {
            if (released.get()) return
            worker.removeCallbacks(reconnect)
            worker.postDelayed(reconnect, SYU_RECONNECT_DELAY_MS)
        }

        private fun activateForFm(source: String) {
            val main = mainModule
            if (main == null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_SOURCE",
                    "source=$source claim=pending reason=mainModuleUnavailable " +
                        "endpoint=${connectedComponent?.packageName.orEmpty()}",
                )
                if (!bound) scheduleReconnect()
                return
            }

            registerMainCallbacks(main)
            radioModule?.let(::registerRadioCallbacks)
            steerModule?.let(::registerSteerCallbacks)

            val claimed =
                runCatching {
                    main.cmd(
                        command = SYU_MAIN_COMMAND_SOURCE,
                        ints = SYU_RADIO_SOURCE_PAYLOAD.copyOf(),
                        floats = null,
                        strings = null,
                    )
                }.onFailure { error -> logFailure("sourceClaim", error) }
                    .isSuccess

            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_SOURCE",
                "source=$source command=$SYU_MAIN_COMMAND_SOURCE " +
                    "ints=${SYU_RADIO_SOURCE_PAYLOAD.contentToString()} claimed=$claimed " +
                    "endpoint=${connectedComponent?.packageName.orEmpty()}",
            )
        }

        private fun deactivateForFm(source: String) {
            var removed = 0
            mainModule?.takeIf { mainRegistered }?.let { module ->
                SYU_MAIN_CALLBACK_CODES.forEach { code ->
                    if (runCatching { module.unregister(mainCallback, code) }.isSuccess) removed += 1
                }
            }
            radioModule?.takeIf { radioRegistered }?.let { module ->
                SYU_RADIO_CALLBACK_CODES.forEach { code ->
                    if (runCatching { module.unregister(radioCallback, code) }.isSuccess) removed += 1
                }
            }
            steerModule?.takeIf { steerRegistered }?.let { module ->
                SYU_STEER_CALLBACK_CODES.forEach { code ->
                    if (runCatching { module.unregister(steerCallback, code) }.isSuccess) removed += 1
                }
            }
            mainRegistered = false
            radioRegistered = false
            steerRegistered = false
            sourceOwnerPackage = ""
            sourceOwnedAt = 0L
            lastObservedFrequency = Float.NaN
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "source=$source callbacksUnregistered=$removed",
            )
        }

        private fun registerMainCallbacks(module: SyuRemoteModule) {
            if (mainRegistered) return
            var accepted = 0
            SYU_MAIN_CALLBACK_CODES.forEach { updateCode ->
                if (runCatching { module.register(mainCallback, updateCode, 1) }.isSuccess) accepted += 1
            }
            mainRegistered = true
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "mainCallbacksRegistered=$accepted codes=${SYU_MAIN_CALLBACK_CODES.contentToString()}",
            )
        }

        private fun registerRadioCallbacks(module: SyuRemoteModule) {
            if (radioRegistered) return
            var accepted = 0
            SYU_RADIO_CALLBACK_CODES.forEach { updateCode ->
                if (runCatching { module.register(radioCallback, updateCode, 1) }.isSuccess) accepted += 1
            }
            radioRegistered = true
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "radioCallbacksRegistered=$accepted range=${SYU_RADIO_CALLBACK_CODES.first}..${SYU_RADIO_CALLBACK_CODES.last}",
            )
        }

        private fun registerSteerCallbacks(module: SyuRemoteModule) {
            if (steerRegistered) return
            var accepted = 0
            SYU_STEER_CALLBACK_CODES.forEach { updateCode ->
                if (runCatching { module.register(steerCallback, updateCode, 1) }.isSuccess) accepted += 1
            }
            steerRegistered = true
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "steerCallbacksRegistered=$accepted range=${SYU_STEER_CALLBACK_CODES.first}..${SYU_STEER_CALLBACK_CODES.last}",
            )
        }

        private fun onMainUpdate(
            updateCode: Int,
            ints: IntArray?,
            floats: FloatArray?,
            strings: Array<String>?,
        ) {
            if (released.get()) return
            if (updateCode == SYU_MAIN_UPDATE_SOURCE_OWNER) {
                val owner = strings?.firstOrNull().orEmpty()
                sourceOwnerPackage = owner
                sourceOwnedAt =
                    if (owner == appContext.packageName) SystemClock.elapsedRealtime() else 0L
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_OWNER",
                    "package=$owner ours=${owner == appContext.packageName} fmRequested=$fmRequested",
                )
            } else {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_CALLBACK",
                    "module=MAIN update=$updateCode ints=${ints.compact()} floats=${floats.compact()} " +
                        "strings=${strings.compact()} fmRequested=$fmRequested",
                )
            }
        }

        private fun onRadioUpdate(
            updateCode: Int,
            ints: IntArray?,
            floats: FloatArray?,
            strings: Array<String>?,
        ) {
            if (released.get()) return
            val observed = extractSyuFmFrequency(ints, floats, strings) ?: return
            val snapshot = FytPhysicalRadio.state.value
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_RADIO_FREQUENCY",
                "update=$updateCode observed=$observed current=${snapshot.frequency} " +
                    "ints=${ints.compact()} floats=${floats.compact()} strings=${strings.compact()}",
            )
            redirectExternalTune(observed, "RADIO:$updateCode")
        }

        private fun onSteerUpdate(
            updateCode: Int,
            ints: IntArray?,
            floats: FloatArray?,
            strings: Array<String>?,
        ) {
            if (released.get()) return
            val direction = extractSyuSteeringDirection(updateCode, ints)
            if (direction != null) {
                // Diagnostic only. The Dudu7 firmware can still execute its own RADIO cmd 26;
                // the frequency observer below performs the final deterministic redirect after
                // that vendor tune has happened, avoiding a race and a double favourite jump.
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_STEER_CANDIDATE",
                    "update=$updateCode direction=${if (direction) "NEXT" else "PREVIOUS"} " +
                        "ints=${ints.compact()} decision=observe_radio_frequency",
                )
            } else if (ints?.isNotEmpty() == true || floats?.isNotEmpty() == true || strings?.isNotEmpty() == true) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_STEER_CALLBACK",
                    "update=$updateCode ints=${ints.compact()} floats=${floats.compact()} strings=${strings.compact()}",
                )
            }
        }

        private fun redirectExternalTune(
            observedFrequency: Float,
            source: String,
        ) {
            val now = SystemClock.elapsedRealtime()
            val snapshot = FytPhysicalRadio.state.value
            val ignoreReason =
                when {
                    !fmRequested -> "fmNotRequested"
                    sourceOwnerPackage != appContext.packageName -> "notSourceOwner:$sourceOwnerPackage"
                    sourceOwnedAt <= 0L || now - sourceOwnedAt < SYU_REDIRECT_ARM_DELAY_MS -> "ownerGrace"
                    !snapshot.isActive -> "fmInactive"
                    snapshot.isBusy -> "metroListBusy"
                    snapshot.isScanning -> "scanActive"
                    snapshot.presets.size < 2 -> "notEnoughFavourites"
                    abs(observedFrequency - snapshot.frequency) < SYU_FREQUENCY_TOLERANCE -> "matchesMetroList"
                    !lastObservedFrequency.isNaN() &&
                        abs(observedFrequency - lastObservedFrequency) < SYU_FREQUENCY_TOLERANCE &&
                        now - lastObservedAt < SYU_EXTERNAL_DUPLICATE_WINDOW_MS -> "duplicateFrequency"
                    else -> null
                }

            lastObservedFrequency = observedFrequency
            lastObservedAt = now

            if (ignoreReason != null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency current=${snapshot.frequency} " +
                        "decision=ignore reason=$ignoreReason",
                )
                return
            }

            val next = inferExternalFmDirection(snapshot.frequency, observedFrequency)
            if (next == null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency current=${snapshot.frequency} " +
                        "decision=ignore reason=noDirection",
                )
                return
            }

            if (lastRedirectDirection == next && now - lastRedirectAt < SYU_REDIRECT_DEDUP_WINDOW_MS) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_FM_REDIRECT",
                    "source=$source observed=$observedFrequency current=${snapshot.frequency} " +
                        "direction=${if (next) "NEXT" else "PREVIOUS"} decision=duplicate",
                )
                return
            }

            val handled = PhysicalFmMediaKeyBridge.handleDirection(next)
            if (handled) {
                lastRedirectDirection = next
                lastRedirectAt = now
            }
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_FM_REDIRECT",
                "source=$source observed=$observedFrequency current=${snapshot.frequency} " +
                    "direction=${if (next) "NEXT" else "PREVIOUS"} handled=$handled",
            )
        }

        private fun logFailure(
            stage: String,
            error: Throwable,
        ) {
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "stage=$stage failed=${error.javaClass.simpleName}:${error.message.orEmpty()}",
            )
        }
    }
}

internal const val SYU_MAIN_MODULE = 0
internal const val SYU_RADIO_MODULE = 1
internal const val SYU_STEER_MODULE = 10
internal const val SYU_MAIN_COMMAND_SOURCE = 0
internal const val SYU_MAIN_UPDATE_SOURCE_OWNER = 195
internal val SYU_RADIO_SOURCE_PAYLOAD = intArrayOf(1)
internal val SYU_MAIN_CALLBACK_CODES = intArrayOf(SYU_MAIN_UPDATE_SOURCE_OWNER)
internal val SYU_RADIO_CALLBACK_CODES: IntRange = 0..255
internal val SYU_STEER_CALLBACK_CODES: IntRange = 0..255

/** Extracts a real FM frequency, never a media key, from vendor module payloads. */
internal fun extractSyuFmFrequency(
    ints: IntArray?,
    floats: FloatArray?,
    strings: Array<out String?>?,
): Float? {
    ints?.asSequence()?.mapNotNull(::decodeSyuFmInteger)?.firstOrNull()?.let { return it }
    floats?.asSequence()?.mapNotNull(::decodeSyuFmFrequency)?.firstOrNull()?.let { return it }
    strings
        ?.asSequence()
        ?.filterNotNull()
        ?.forEach { value ->
            SYU_FM_DECIMAL.findAll(value).forEach { match ->
                val whole = match.groupValues[1].toIntOrNull() ?: return@forEach
                val decimals = match.groupValues[2]
                val fraction = decimals.toIntOrNull()?.toFloat()?.div(if (decimals.length == 1) 10f else 100f) ?: 0f
                decodeSyuFmFrequency(whole + fraction)?.let { return it }
            }
            SYU_FM_INTEGER.findAll(value).forEach { match ->
                decodeSyuFmInteger(match.value.toIntOrNull() ?: return@forEach)?.let { return it }
            }
        }
    return null
}

/** Integer payloads use scaled vendor units; raw 87/88 are steering-key values, not MHz. */
internal fun decodeSyuFmInteger(raw: Int): Float? {
    val decoded =
        when (raw) {
            in 875..1080 -> raw / 10f
            in 8750..10800 -> raw / 100f
            in 87500..108000 -> raw / 1000f
            else -> return null
        }
    return (decoded * 10f).roundToInt() / 10f
}

internal fun decodeSyuFmFrequency(raw: Float): Float? {
    if (!raw.isFinite()) return null
    val decoded =
        when (raw) {
            in 87.5f..108.0f -> raw
            in 875f..1080f -> raw / 10f
            in 8750f..10800f -> raw / 100f
            in 87500f..108000f -> raw / 1000f
            else -> return null
        }
    return (decoded * 10f).roundToInt() / 10f
}

/**
 * Uses the shortest direction on the cyclic European FM band. true = next/up,
 * false = previous/down.
 */
internal fun inferExternalFmDirection(
    currentFrequency: Float,
    observedFrequency: Float,
): Boolean? {
    val current = decodeSyuFmFrequency(currentFrequency) ?: return null
    val observed = decodeSyuFmFrequency(observedFrequency) ?: return null
    if (abs(current - observed) < SYU_FREQUENCY_TOLERANCE) return null

    val upDistance =
        if (observed > current) {
            observed - current
        } else {
            (SYU_FM_MAX - current) + SYU_FM_STEP + (observed - SYU_FM_MIN)
        }
    val downDistance =
        if (observed < current) {
            current - observed
        } else {
            (current - SYU_FM_MIN) + SYU_FM_STEP + (SYU_FM_MAX - observed)
        }
    return upDistance <= downDistance
}

/**
 * STEER callbacks are diagnostic until the subsequent RADIO frequency callback arrives.
 * Initial callback slots 87/88 with payload [0] are deliberately rejected.
 */
internal fun extractSyuSteeringDirection(
    updateCode: Int,
    ints: IntArray?,
): Boolean? {
    ints?.firstOrNull { it == 87 || it == 88 }?.let { return it == 87 }
    val pressed = ints?.firstOrNull() == 1
    return when {
        updateCode == 87 && pressed -> true
        updateCode == 88 && pressed -> false
        else -> null
    }
}

private const val SYU_TOOLKIT_ACTION = "com.syu.ms.toolkit"
private const val SYU_TOOLKIT_SERVICE = "app.ToolkitService"
private const val SYU_RECONNECT_DELAY_MS = 1_500L
private const val SYU_REDIRECT_ARM_DELAY_MS = 900L
private const val SYU_EXTERNAL_DUPLICATE_WINDOW_MS = 700L
private const val SYU_REDIRECT_DEDUP_WINDOW_MS = 450L
private const val SYU_FREQUENCY_TOLERANCE = 0.05f
private const val SYU_FM_MIN = 87.5f
private const val SYU_FM_MAX = 108.0f
private const val SYU_FM_STEP = 0.1f
private val SYU_ENDPOINTS = arrayOf("com.syu.ms", "com.syu.ss")
private val SYU_FM_DECIMAL = Regex("""(?<!\d)(8[7-9]|9\d|10[0-8])[\.,](\d{1,2})(?!\d)""")
private val SYU_FM_INTEGER = Regex("""(?<!\d)\d{4,6}(?!\d)""")

private fun IntArray?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 16, truncated = "…") ?: "null"

private fun FloatArray?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 12, truncated = "…") ?: "null"

private fun Array<String>?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 12, truncated = "…") ?: "null"

private class SyuToolkit(
    private val binder: IBinder,
) {
    fun getRemoteModule(moduleCode: Int): IBinder? {
        val data = Parcel.obtain()
        val reply = Parcel.obtain()
        return try {
            data.writeInterfaceToken(SYU_TOOLKIT_DESCRIPTOR)
            data.writeInt(moduleCode)
            check(binder.transact(SYU_TOOLKIT_GET_REMOTE_MODULE, data, reply, 0)) {
                "IRemoteToolkit.getRemoteModule transact returned false"
            }
            reply.readException()
            reply.readStrongBinder()
        } finally {
            reply.recycle()
            data.recycle()
        }
    }

    companion object {
        private const val SYU_TOOLKIT_DESCRIPTOR = "com.syu.ipc.IRemoteToolkit"
        private const val SYU_TOOLKIT_GET_REMOTE_MODULE = 1
    }
}

private class SyuRemoteModule(
    private val binder: IBinder,
) {
    fun cmd(
        command: Int,
        ints: IntArray?,
        floats: FloatArray?,
        strings: Array<String>?,
    ) {
        val data = Parcel.obtain()
        try {
            data.writeInterfaceToken(SYU_MODULE_DESCRIPTOR)
            data.writeInt(command)
            data.writeIntArray(ints)
            data.writeFloatArray(floats)
            data.writeStringArray(strings)
            check(binder.transact(SYU_MODULE_COMMAND, data, null, IBinder.FLAG_ONEWAY)) {
                "IRemoteModule.cmd transact returned false"
            }
        } finally {
            data.recycle()
        }
    }

    fun register(
        callback: IBinder,
        updateCode: Int,
        update: Int,
    ) {
        val data = Parcel.obtain()
        try {
            data.writeInterfaceToken(SYU_MODULE_DESCRIPTOR)
            data.writeStrongBinder(callback)
            data.writeInt(updateCode)
            data.writeInt(update)
            check(binder.transact(SYU_MODULE_REGISTER, data, null, IBinder.FLAG_ONEWAY)) {
                "IRemoteModule.register transact returned false for $updateCode"
            }
        } finally {
            data.recycle()
        }
    }

    fun unregister(
        callback: IBinder,
        updateCode: Int,
    ) {
        val data = Parcel.obtain()
        try {
            data.writeInterfaceToken(SYU_MODULE_DESCRIPTOR)
            data.writeStrongBinder(callback)
            data.writeInt(updateCode)
            check(binder.transact(SYU_MODULE_UNREGISTER, data, null, IBinder.FLAG_ONEWAY)) {
                "IRemoteModule.unregister transact returned false for $updateCode"
            }
        } finally {
            data.recycle()
        }
    }

    companion object {
        private const val SYU_MODULE_DESCRIPTOR = "com.syu.ipc.IRemoteModule"
        private const val SYU_MODULE_COMMAND = 1
        private const val SYU_MODULE_REGISTER = 3
        private const val SYU_MODULE_UNREGISTER = 4
    }
}

private class SyuModuleCallback(
    private val listener: (
        updateCode: Int,
        ints: IntArray?,
        floats: FloatArray?,
        strings: Array<String>?,
    ) -> Unit,
) : Binder() {
    init {
        attachInterface(null, SYU_CALLBACK_DESCRIPTOR)
    }

    override fun onTransact(
        code: Int,
        data: Parcel,
        reply: Parcel?,
        flags: Int,
    ): Boolean =
        when (code) {
            INTERFACE_TRANSACTION -> {
                reply?.writeString(SYU_CALLBACK_DESCRIPTOR)
                true
            }
            SYU_CALLBACK_UPDATE -> {
                data.enforceInterface(SYU_CALLBACK_DESCRIPTOR)
                listener(
                    data.readInt(),
                    data.createIntArray(),
                    data.createFloatArray(),
                    data.createStringArray(),
                )
                true
            }
            else -> super.onTransact(code, data, reply, flags)
        }

    companion object {
        private const val SYU_CALLBACK_DESCRIPTOR = "com.syu.ipc.IModuleCallback"
        private const val SYU_CALLBACK_UPDATE = 1
    }
}
