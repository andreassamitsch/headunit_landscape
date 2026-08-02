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
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Minimal Dudu7/FYT Syu radio-source client derived from the live Dudu7 analysis and the
 * NavRadio+ 4.09 Dudu7 path.
 *
 * This is intentionally a diagnostic prototype:
 * - it binds to the Syu IRemoteToolkit service;
 * - resolves MAIN module 0;
 * - while physical FM is requested, registers broad MAIN callbacks and sends only the
 *   observed radio/source claim MAIN.cmd(0, [1]);
 * - it logs every callback and possible 87/88 payload, but does not route an unconfirmed
 *   callback to a favourite or send radio tune command 26.
 *
 * The working FmService/FmNative tuner path remains the sole tuner implementation.
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

    /**
     * Requests Syu radio-source ownership before FmNative is opened.
     * Returns true when a connected MAIN module accepted the command immediately.
     * A pending request is automatically replayed after a later service connection.
     */
    fun claimFmSource(): Boolean = client?.setFmRequested(true) ?: false

    /** Stops diagnostic callback registration. No unverified Syu source-release command is sent. */
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
        private val callback = SyuModuleCallback(::onModuleUpdate)

        @Volatile
        private var bound = false

        @Volatile
        private var fmRequested = false

        @Volatile
        private var registered = false

        @Volatile
        private var mainModule: SyuRemoteModule? = null

        @Volatile
        private var connectedComponent: ComponentName? = null

        private var endpointIndex = 0

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

                        val moduleBinder =
                            runCatching { SyuToolkit(service).getRemoteModule(SYU_MAIN_MODULE) }
                                .onFailure { error ->
                                    logFailure("resolveMain", error)
                                }.getOrNull()

                        if (moduleBinder == null) {
                            MediaKeyDiagnostics.record(
                                appContext,
                                "SYU_IPC_STATE",
                                "mainModule=unavailable component=${name.flattenToShortString()}",
                            )
                            return@post
                        }

                        mainModule = SyuRemoteModule(moduleBinder)
                        runCatching {
                            moduleBinder.linkToDeath(
                                {
                                    worker.post {
                                        MediaKeyDiagnostics.record(
                                            appContext,
                                            "SYU_IPC_STATE",
                                            "mainModule=binderDied component=${name.flattenToShortString()}",
                                        )
                                        mainModule = null
                                        registered = false
                                        scheduleReconnect()
                                    }
                                },
                                0,
                            )
                        }

                        MediaKeyDiagnostics.record(
                            appContext,
                            "SYU_IPC_STATE",
                            "mainModule=ready fmRequested=$fmRequested component=${name.flattenToShortString()}",
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
                        bound = false
                        registered = false
                        mainModule = null
                        connectedComponent = null
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
                        bound = false
                        registered = false
                        mainModule = null
                        connectedComponent = null
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
                        bound = false
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
                if (requested) {
                    activateForFm("powerOn")
                } else {
                    deactivateForFm("powerOff")
                }
            }
            return immediate
        }

        fun release() {
            if (!released.compareAndSet(false, true)) return
            worker.removeCallbacksAndMessages(null)
            deactivateForFm("serviceRelease")
            if (bound) runCatching { appContext.unbindService(connection) }
            bound = false
            mainModule = null
            connectedComponent = null
            MediaKeyDiagnostics.record(appContext, "SYU_IPC_STATE", "released")
            workerThread.quitSafely()
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
                }.onFailure { error ->
                    logFailure("bind:${endpoint}", error)
                }.getOrDefault(false)

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
            val module = mainModule
            if (module == null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_SOURCE",
                    "source=$source claim=pending reason=mainModuleUnavailable endpoint=${connectedComponent?.packageName.orEmpty()}",
                )
                if (!bound) scheduleReconnect()
                return
            }

            registerCallbacks(module)
            val claimed =
                runCatching {
                    module.cmd(
                        command = SYU_MAIN_COMMAND_SOURCE,
                        ints = SYU_RADIO_SOURCE_PAYLOAD.copyOf(),
                        floats = null,
                        strings = null,
                    )
                }.onFailure { error ->
                    logFailure("sourceClaim", error)
                }.isSuccess

            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_SOURCE",
                "source=$source command=$SYU_MAIN_COMMAND_SOURCE ints=${SYU_RADIO_SOURCE_PAYLOAD.contentToString()} " +
                    "claimed=$claimed endpoint=${connectedComponent?.packageName.orEmpty()}",
            )
        }

        private fun deactivateForFm(source: String) {
            val module = mainModule
            if (module != null && registered) {
                var removed = 0
                SYU_MAIN_CALLBACK_CODES.forEach { updateCode ->
                    if (runCatching { module.unregister(callback, updateCode) }.isSuccess) removed += 1
                }
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_STATE",
                    "source=$source callbacksUnregistered=$removed",
                )
            }
            registered = false
        }

        private fun registerCallbacks(module: SyuRemoteModule) {
            if (registered) return
            var accepted = 0
            SYU_MAIN_CALLBACK_CODES.forEach { updateCode ->
                if (runCatching { module.register(callback, updateCode, 1) }.isSuccess) accepted += 1
            }
            registered = true
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_STATE",
                "callbacksRegistered=$accepted range=${SYU_MAIN_CALLBACK_CODES.first}..${SYU_MAIN_CALLBACK_CODES.last} " +
                    "includes=${SYU_KNOWN_MAIN_CALLBACKS.contentToString()}",
            )
        }

        private fun onModuleUpdate(
            updateCode: Int,
            ints: IntArray?,
            floats: FloatArray?,
            strings: Array<String>?,
        ) {
            if (released.get()) return
            val keyCandidate = extractSyuMediaKeyCandidate(updateCode, ints, strings)
            MediaKeyDiagnostics.record(
                appContext,
                "SYU_IPC_CALLBACK",
                "update=$updateCode ints=${ints.compact()} floats=${floats.compact()} strings=${strings.compact()} " +
                    "fmRequested=$fmRequested keyCandidate=${keyCandidate ?: "none"}",
            )
            if (keyCandidate != null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "SYU_IPC_KEY_CANDIDATE",
                    "keyCode=$keyCandidate update=$updateCode decision=log_only_not_routed",
                )
            }
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
internal const val SYU_MAIN_COMMAND_SOURCE = 0
internal val SYU_RADIO_SOURCE_PAYLOAD = intArrayOf(1)
internal val SYU_MAIN_CALLBACK_CODES: IntRange = 0..255
internal val SYU_KNOWN_MAIN_CALLBACKS = intArrayOf(0, 12, 174)

internal fun extractSyuMediaKeyCandidate(
    updateCode: Int,
    ints: IntArray?,
    strings: Array<out String?>?,
): Int? {
    if (updateCode == 87 || updateCode == 88) return updateCode
    ints?.firstOrNull { it == 87 || it == 88 }?.let { return it }
    strings
        ?.asSequence()
        ?.filterNotNull()
        ?.flatMap { value -> SYU_KEY_NUMBER.findAll(value).mapNotNull { it.value.toIntOrNull() } }
        ?.firstOrNull { it == 87 || it == 88 }
        ?.let { return it }
    return null
}

private const val SYU_TOOLKIT_ACTION = "com.syu.ms.toolkit"
private const val SYU_TOOLKIT_SERVICE = "app.ToolkitService"
private const val SYU_RECONNECT_DELAY_MS = 1_500L
private val SYU_ENDPOINTS = arrayOf("com.syu.ms", "com.syu.ss")
private val SYU_KEY_NUMBER = Regex("""(?<![\d.])(?:87|88)(?![\d.])""")

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
