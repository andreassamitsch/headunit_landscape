package com.metrolist.music.radio.fyt

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.os.Message
import com.metrolist.music.playback.Dudu7FytTwProtocol
import com.metrolist.music.playback.FytTwKeyAction
import com.metrolist.music.playback.FytTwWrite
import com.metrolist.music.playback.MediaKeyDiagnostics
import com.metrolist.music.playback.PhysicalFmMediaKeyBridge
import com.metrolist.music.playback.resolveFytTwKeyAction
import java.lang.reflect.InvocationTargetException
import java.lang.reflect.Method

/**
 * Single FYT TWUtil owner shared by the physical tuner and steering-wheel-key routing.
 *
 * NavRadio+ 4.08 uses one TWUtil(1) instance for event subscription, FM source ownership,
 * status messages and key handling. Using a second TWUtil(1) replaces the registered
 * handler on this firmware, so this controller deliberately owns the complete lifecycle.
 */
internal class Dudu7FytTwController private constructor(
    context: Context,
) {
    private val appContext = context.applicationContext
    private val lock = Any()
    private val handler =
        object : Handler(Looper.getMainLooper()) {
            override fun handleMessage(message: Message) {
                handleTwMessage(message)
            }
        }

    private var twClass: Class<*>? = null
    private var twInstance: Any? = null
    private var write2: Method? = null
    private var write3: Method? = null

    @Volatile
    private var vendorRadioActive = false

    fun open(): Boolean =
        synchronized(lock) {
            if (twInstance != null) return@synchronized true

            runCatching {
                val clazz = Class.forName(TW_UTIL_CLASS)
                val instance =
                    clazz.getConstructor(Integer.TYPE)
                        .newInstance(Dudu7FytTwProtocol.CLIENT_ID)
                val openResult =
                    (clazz.getMethod("open", ShortArray::class.java)
                        .invoke(instance, Dudu7FytTwProtocol.EVENTS.copyOf()) as? Number)
                        ?.toInt()
                        ?: -1

                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TW_STATE",
                    "owner=shared classLoaded=true openResult=$openResult " +
                        "events=${Dudu7FytTwProtocol.EVENTS.size}",
                )

                if (openResult != Dudu7FytTwProtocol.OPEN_SUCCESS) {
                    runCatching { clazz.getMethod("close").invoke(instance) }
                    return@runCatching false
                }

                // Exact NavRadio+ order: open -> start -> addHandler("radio").
                clazz.getMethod("start").invoke(instance)
                clazz.getMethod("addHandler", String::class.java, Handler::class.java)
                    .invoke(instance, Dudu7FytTwProtocol.HANDLER_NAME, handler)

                twClass = clazz
                twInstance = instance
                write2 = clazz.getMethod("write", Integer.TYPE, Integer.TYPE)
                write3 = clazz.getMethod("write", Integer.TYPE, Integer.TYPE, Integer.TYPE)
                vendorRadioActive = false

                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TW_STATE",
                    "owner=shared started handler=${Dudu7FytTwProtocol.HANDLER_NAME} " +
                        "keyEvent=0x${Dudu7FytTwProtocol.EVENT_KEY.toString(16)}",
                )
                true
            }.onFailure { throwable ->
                val error = throwable.rootCause()
                MediaKeyDiagnostics.record(
                    appContext,
                    "FYT_TW_STATE",
                    "owner=shared initFailed=${error.javaClass.simpleName}:${error.message.sanitized()}",
                )
                clearReflectionState()
            }.getOrDefault(false)
        }

    fun close() {
        synchronized(lock) {
            val clazz = twClass
            val instance = twInstance
            if (clazz != null && instance != null) {
                runCatching { clazz.getMethod("stop").invoke(instance) }
                    .onFailure { recordFailure("stop", it) }
                runCatching { clazz.getMethod("close").invoke(instance) }
                    .onFailure { recordFailure("close", it) }
            }
            clearReflectionState()
            vendorRadioActive = false
            MediaKeyDiagnostics.record(appContext, "FYT_TW_STATE", "owner=shared closed")
        }
    }

    fun initRadioSequence() {
        applySequence("init", Dudu7FytTwProtocol.INITIALIZATION_WRITES)
    }

    fun radioOnFm() {
        applySequence("enter_fm", Dudu7FytTwProtocol.ENTER_FM_WRITES)
        // NavRadio subsequently confirms this through event 0x0301. Keep an optimistic
        // state so a key arriving before that acknowledgement is not dropped.
        vendorRadioActive = true
        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_RADIO_STATE",
            "source=enter_fm active=true",
        )
    }

    fun radioOff() {
        applySequence("exit_fm", Dudu7FytTwProtocol.EXIT_FM_WRITES)
        vendorRadioActive = false
        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_RADIO_STATE",
            "source=exit_fm active=false",
        )
    }

    /** Reassert only the NavRadio+ audio-source writes after native tuner startup. */
    fun setAudioSourceFm() {
        applySequence("source_fm", Dudu7FytTwProtocol.ENTER_FM_WRITES.drop(1))
    }

    // FmNative controls tuner mute; these proven FYT writes retain audio-path compatibility.
    fun mute() {
        writeAndRecord("mute", FytTwWrite(0x0105, 1))
    }

    fun unmute() {
        writeAndRecord("unmute", FytTwWrite(0x0105, 0))
    }

    private fun applySequence(
        stage: String,
        writes: List<FytTwWrite>,
    ) {
        writes.forEach { writeAndRecord(stage, it) }
    }

    private fun writeAndRecord(
        stage: String,
        write: FytTwWrite,
    ): Int {
        val result =
            synchronized(lock) {
                val instance = twInstance ?: return@synchronized -1
                runCatching {
                    if (write.value2 == null) {
                        write2?.invoke(instance, write.command, write.value1) as? Number
                    } else {
                        write3?.invoke(instance, write.command, write.value1, write.value2) as? Number
                    }
                }.onFailure { recordFailure("write_${write.command.toString(16)}", it) }
                    .getOrNull()
                    ?.toInt()
                    ?: -1
            }

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_WRITE",
            "stage=$stage command=0x${write.command.toString(16)} value1=${write.value1} " +
                "value2=${write.value2 ?: "-"} result=$result",
        )
        return result
    }

    private fun handleTwMessage(message: Message) {
        if (message.what == Dudu7FytTwProtocol.EVENT_RADIO_STATE) {
            vendorRadioActive = message.arg1 == 1
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TW_RADIO_STATE",
                "source=event what=0x${message.what.toString(16)} arg1=${message.arg1} " +
                    "arg2=${message.arg2} active=$vendorRadioActive",
            )
        }

        val fmActive = FytPhysicalRadio.state.value.isActive
        val action =
            resolveFytTwKeyAction(
                eventCode = message.what,
                keyCode = message.arg2,
                pressType = message.arg1,
                fmActive = fmActive,
                vendorRadioActive = vendorRadioActive,
            )

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_EVENT",
            "what=0x${message.what.toString(16)} arg1=${message.arg1} arg2=${message.arg2} " +
                "obj=${message.obj.toString().sanitized()} fmActive=$fmActive " +
                "vendorRadioActive=$vendorRadioActive action=$action",
        )

        if (action == FytTwKeyAction.NONE) return

        val handled =
            when (action) {
                FytTwKeyAction.NEXT_FAVOURITE ->
                    PhysicalFmMediaKeyBridge.handleDirection(next = true)

                FytTwKeyAction.PREVIOUS_FAVOURITE ->
                    PhysicalFmMediaKeyBridge.handleDirection(next = false)

                FytTwKeyAction.SEEK_UP -> {
                    FytPhysicalRadio.seek(up = true)
                    true
                }

                FytTwKeyAction.SEEK_DOWN -> {
                    FytPhysicalRadio.seek(up = false)
                    true
                }

                FytTwKeyAction.NONE -> false
            }

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_ROUTE",
            "key=${message.arg2} press=${message.arg1} action=$action handled=$handled",
        )
    }

    private fun clearReflectionState() {
        twInstance = null
        twClass = null
        write2 = null
        write3 = null
    }

    private fun recordFailure(
        stage: String,
        throwable: Throwable,
    ) {
        val error = throwable.rootCause()
        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_STATE",
            "owner=shared stage=$stage failed=${error.javaClass.simpleName}:${error.message.sanitized()}",
        )
    }

    companion object {
        private const val TW_UTIL_CLASS = "android.tw.john.TWUtil"

        @Volatile
        private var singleton: Dudu7FytTwController? = null

        fun get(context: Context): Dudu7FytTwController =
            singleton ?: synchronized(this) {
                singleton ?: Dudu7FytTwController(context).also { singleton = it }
            }
    }
}

private fun Throwable.rootCause(): Throwable =
    when (this) {
        is InvocationTargetException -> targetException ?: this
        else -> cause ?: this
    }

private fun String?.sanitized(): String =
    orEmpty()
        .replace('\n', ' ')
        .replace('\r', ' ')
        .take(120)
