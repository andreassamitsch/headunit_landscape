package com.metrolist.music.playback

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Binder
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Parcel
import android.os.RemoteException
import android.os.SystemClock
import android.view.KeyEvent
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import java.util.concurrent.ConcurrentHashMap

/**
 * Direct connection to the FYT system service used by NavRadio+ on UIS7862/FYT units.
 *
 * Android MediaSession remains the public playback API. This adapter listens one layer
 * earlier at com.syu.ms/app.ToolkitService, where steering-wheel/radio key events are
 * published by the MCU integration before the stock radio fallback handles them.
 */
internal class Dudu7FytToolkitMediaKeys(
    context: Context,
) {
    private val appContext = context.applicationContext
    private val radio = FytPhysicalRadio.get(appContext)
    private val mainHandler = Handler(Looper.getMainLooper())
    private val modules = ConcurrentHashMap<Int, FytModuleRegistration>()
    private val routeLock = Any()

    @Volatile
    private var released = false

    @Volatile
    private var bound = false

    private var lastKeyCode = KeyEvent.KEYCODE_UNKNOWN
    private var lastKeyAt = 0L

    private val reconnect =
        Runnable {
            if (!released && !bound) bind()
        }

    private val connection =
        object : ServiceConnection {
            override fun onServiceConnected(
                name: ComponentName,
                service: IBinder,
            ) {
                if (released) return
                bound = true
                mainHandler.removeCallbacks(reconnect)
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TOOLKIT_STATE",
                    "connected component=${name.flattenToShortString()}",
                )
                registerModules(service)
            }

            override fun onServiceDisconnected(name: ComponentName) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TOOLKIT_STATE",
                    "disconnected component=${name.flattenToShortString()}",
                )
                clearModules(unregister = false)
                bound = false
                scheduleReconnect()
            }

            override fun onBindingDied(name: ComponentName) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TOOLKIT_STATE",
                    "bindingDied component=${name.flattenToShortString()}",
                )
                clearModules(unregister = false)
                bound = false
                runCatching { appContext.unbindService(this) }
                scheduleReconnect()
            }
        }

    init {
        bind()
    }

    fun release() {
        if (released) return
        released = true
        mainHandler.removeCallbacks(reconnect)
        clearModules(unregister = true)
        if (bound) {
            runCatching { appContext.unbindService(connection) }
        }
        bound = false
        MediaKeyDiagnostics.record(appContext, "FYT_TOOLKIT_STATE", "released")
    }

    private fun bind() {
        if (released || bound) return
        val intent =
            Intent(TOOLKIT_ACTION).apply {
                component = ComponentName(TOOLKIT_PACKAGE, TOOLKIT_SERVICE)
            }
        val accepted =
            runCatching {
                appContext.bindService(intent, connection, Context.BIND_AUTO_CREATE)
            }.onFailure { error ->
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TOOLKIT_STATE",
                    "bindFailed=${error.javaClass.simpleName}:${error.message.orEmpty()}",
                )
            }.getOrDefault(false)

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TOOLKIT_STATE",
            "bindRequested accepted=$accepted component=$TOOLKIT_PACKAGE/$TOOLKIT_SERVICE",
        )
        if (!accepted) scheduleReconnect()
    }

    private fun scheduleReconnect() {
        if (released) return
        mainHandler.removeCallbacks(reconnect)
        mainHandler.postDelayed(reconnect, RECONNECT_DELAY_MS)
    }

    private fun registerModules(toolkitBinder: IBinder) {
        clearModules(unregister = false)
        MODULES.forEach { moduleCode ->
            val moduleBinder =
                runCatching { FytToolkit(toolkitBinder).getRemoteModule(moduleCode) }
                    .onFailure { error ->
                        MediaKeyDiagnostics.record(
                            appContext,
                            "FYT_TOOLKIT_STATE",
                            "module=$moduleCode resolveFailed=${error.javaClass.simpleName}:${error.message.orEmpty()}",
                        )
                    }.getOrNull()
            if (moduleBinder == null) {
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TOOLKIT_STATE",
                    "module=$moduleCode unavailable",
                )
                return@forEach
            }

            val remoteModule = FytRemoteModule(moduleBinder)
            val callback =
                FytModuleCallback { updateCode, ints, floats, strings ->
                    onModuleUpdate(moduleCode, updateCode, ints, floats, strings)
                }
            modules[moduleCode] = FytModuleRegistration(remoteModule, callback)
            var registered = 0
            UPDATE_CODES.forEach { updateCode ->
                if (runCatching { remoteModule.register(callback, updateCode, 1) }.isSuccess) {
                    registered += 1
                }
            }
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TOOLKIT_STATE",
                "module=$moduleCode registered=$registered",
            )
        }
    }

    private fun clearModules(unregister: Boolean) {
        val snapshot = modules.entries.toList()
        modules.clear()
        if (!unregister) return
        snapshot.forEach { (_, registration) ->
            UPDATE_CODES.forEach { updateCode ->
                runCatching { registration.module.unregister(registration.callback, updateCode) }
            }
        }
    }

    private fun onModuleUpdate(
        moduleCode: Int,
        updateCode: Int,
        ints: IntArray?,
        floats: FloatArray?,
        strings: Array<String?>?,
    ) {
        if (released) return
        val fmActive = radio.state.value.isActive
        val keyCode = extractMediaKeyCode(updateCode, ints, strings)
        val details =
            "module=$moduleCode update=$updateCode ints=${ints.compact()} floats=${floats.compact()} " +
                "strings=${strings.compact()} fmActive=$fmActive keyCode=${keyCode ?: "none"}"
        MediaKeyDiagnostics.record(appContext, "FYT_TOOLKIT_EVENT", details)

        if (!fmActive || keyCode == null) return
        if (isDuplicate(keyCode)) {
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TOOLKIT_ROUTE",
                "keyCode=$keyCode decision=duplicate",
            )
            return
        }

        val handled =
            when (keyCode) {
                KeyEvent.KEYCODE_MEDIA_NEXT -> PhysicalFmMediaKeyBridge.handleDirection(next = true)
                KeyEvent.KEYCODE_MEDIA_PREVIOUS -> PhysicalFmMediaKeyBridge.handleDirection(next = false)
                KeyEvent.KEYCODE_MEDIA_FAST_FORWARD -> {
                    radio.seek(next = true)
                    true
                }
                KeyEvent.KEYCODE_MEDIA_REWIND -> {
                    radio.seek(next = false)
                    true
                }
                else -> false
            }

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TOOLKIT_ROUTE",
            "module=$moduleCode update=$updateCode keyCode=$keyCode " +
                "keyName=${KeyEvent.keyCodeToString(keyCode)} handled=$handled",
        )
    }

    private fun isDuplicate(keyCode: Int): Boolean {
        val now = SystemClock.elapsedRealtime()
        synchronized(routeLock) {
            if (lastKeyCode == keyCode && now - lastKeyAt <= DUPLICATE_WINDOW_MS) return true
            lastKeyCode = keyCode
            lastKeyAt = now
            return false
        }
    }

    companion object {
        private const val TOOLKIT_ACTION = "com.syu.ms.toolkit"
        private const val TOOLKIT_PACKAGE = "com.syu.ms"
        private const val TOOLKIT_SERVICE = "app.ToolkitService"
        private const val RECONNECT_DELAY_MS = 1_500L
        private const val DUPLICATE_WINDOW_MS = 280L

        private const val MODULE_MAIN = 0
        private const val MODULE_RADIO = 1
        private const val MODULE_STEER = 10
        private val MODULES = intArrayOf(MODULE_MAIN, MODULE_RADIO, MODULE_STEER)

        // FYT modules expose sparse update identifiers. Registering the NavRadio-relevant
        // range mirrors the vendor observer pattern while keeping traffic bounded.
        private val UPDATE_CODES = 0..119
    }
}

internal fun extractMediaKeyCode(
    updateCode: Int,
    ints: IntArray?,
    strings: Array<String?>?,
): Int? {
    if (isSupportedFytMediaKey(updateCode)) return updateCode

    ints.orEmpty().firstOrNull(::isSupportedFytMediaKey)?.let { return it }

    strings.orEmpty()
        .asSequence()
        .filterNotNull()
        .flatMap { value -> MEDIA_KEY_NUMBER.findAll(value).mapNotNull { it.value.toIntOrNull() } }
        .firstOrNull(::isSupportedFytMediaKey)
        ?.let { return it }

    return null
}

internal fun isSupportedFytMediaKey(keyCode: Int): Boolean =
    keyCode == KeyEvent.KEYCODE_MEDIA_NEXT ||
        keyCode == KeyEvent.KEYCODE_MEDIA_PREVIOUS ||
        keyCode == KeyEvent.KEYCODE_MEDIA_FAST_FORWARD ||
        keyCode == KeyEvent.KEYCODE_MEDIA_REWIND

private val MEDIA_KEY_NUMBER = Regex("""(?<![\d.])(?:87|88|89|90)(?![\d.])""")

private fun IntArray?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 12, truncated = "…") ?: "null"

private fun FloatArray?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 8, truncated = "…") ?: "null"

private fun Array<String?>?.compact(): String =
    this?.joinToString(prefix = "[", postfix = "]", limit = 8, truncated = "…") { it.orEmpty() } ?: "null"

private data class FytModuleRegistration(
    val module: FytRemoteModule,
    val callback: FytModuleCallback,
)

private class FytToolkit(
    private val binder: IBinder,
) {
    @Throws(RemoteException::class)
    fun getRemoteModule(moduleCode: Int): IBinder? {
        val data = Parcel.obtain()
        val reply = Parcel.obtain()
        return try {
            data.writeInterfaceToken(TOOLKIT_DESCRIPTOR)
            data.writeInt(moduleCode)
            binder.transact(TRANSACTION_GET_REMOTE_MODULE, data, reply, 0)
            reply.readException()
            reply.readStrongBinder()
        } finally {
            reply.recycle()
            data.recycle()
        }
    }

    companion object {
        private const val TOOLKIT_DESCRIPTOR = "com.syu.ipc.IRemoteToolkit"
        private const val TRANSACTION_GET_REMOTE_MODULE = 1
    }
}

private class FytRemoteModule(
    private val binder: IBinder,
) {
    @Throws(RemoteException::class)
    fun register(
        callback: IBinder,
        updateCode: Int,
        update: Int,
    ) {
        val data = Parcel.obtain()
        try {
            data.writeInterfaceToken(MODULE_DESCRIPTOR)
            data.writeStrongBinder(callback)
            data.writeInt(updateCode)
            data.writeInt(update)
            binder.transact(TRANSACTION_REGISTER, data, null, IBinder.FLAG_ONEWAY)
        } finally {
            data.recycle()
        }
    }

    @Throws(RemoteException::class)
    fun unregister(
        callback: IBinder,
        updateCode: Int,
    ) {
        val data = Parcel.obtain()
        try {
            data.writeInterfaceToken(MODULE_DESCRIPTOR)
            data.writeStrongBinder(callback)
            data.writeInt(updateCode)
            binder.transact(TRANSACTION_UNREGISTER, data, null, IBinder.FLAG_ONEWAY)
        } finally {
            data.recycle()
        }
    }

    companion object {
        private const val MODULE_DESCRIPTOR = "com.syu.ipc.IRemoteModule"
        private const val TRANSACTION_REGISTER = 3
        private const val TRANSACTION_UNREGISTER = 4
    }
}

private class FytModuleCallback(
    private val listener: (
        updateCode: Int,
        ints: IntArray?,
        floats: FloatArray?,
        strings: Array<String?>?,
    ) -> Unit,
) : Binder() {
    init {
        attachInterface(null, CALLBACK_DESCRIPTOR)
    }

    override fun onTransact(
        code: Int,
        data: Parcel,
        reply: Parcel?,
        flags: Int,
    ): Boolean =
        when (code) {
            INTERFACE_TRANSACTION -> {
                reply?.writeString(CALLBACK_DESCRIPTOR)
                true
            }
            TRANSACTION_UPDATE -> {
                data.enforceInterface(CALLBACK_DESCRIPTOR)
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
        private const val CALLBACK_DESCRIPTOR = "com.syu.ipc.IModuleCallback"
        private const val TRANSACTION_UPDATE = 1
    }
}
