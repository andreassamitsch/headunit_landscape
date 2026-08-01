package com.metrolist.music.playback

import android.content.Context
import android.os.Handler
import android.os.HandlerThread
import android.os.Message
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import java.lang.reflect.InvocationTargetException

/**
 * FYT/Dudu7 steering-wheel key input used by NavRadio+.
 *
 * On this device family the MCU does not publish FM steering keys through Android's
 * MEDIA_BUTTON or the generic com.syu.ms ToolkitService observer. NavRadio+ opens the
 * vendor framework class android.tw.john.TWUtil, subscribes to event 0x0201 and receives
 * the vendor key code in Message.arg2 and the press type in Message.arg1.
 */
internal class Dudu7FytTwMediaKeys(
    context: Context,
) {
    private val appContext = context.applicationContext
    private val radio = FytPhysicalRadio.get(appContext)
    private val thread = HandlerThread("Dudu7FytTwKeys").apply { start() }

    @Volatile
    private var released = false

    private var twUtil: Any? = null
    private var twUtilClass: Class<*>? = null

    private val handler =
        object : Handler(thread.looper) {
            override fun handleMessage(message: Message) {
                handleTwMessage(message)
            }
        }

    init {
        handler.post { initialize() }
    }

    fun release() {
        if (released) return
        released = true
        handler.post {
            val instance = twUtil
            val clazz = twUtilClass
            if (instance != null && clazz != null) {
                runCatching { clazz.getMethod("stop").invoke(instance) }
                runCatching { clazz.getMethod("close").invoke(instance) }
            }
            twUtil = null
            twUtilClass = null
            MediaKeyDiagnostics.record(appContext, "FYT_TW_STATE", "released")
            thread.quitSafely()
        }
    }

    private fun initialize() {
        if (released) return
        runCatching {
            val clazz = Class.forName(TW_UTIL_CLASS)
            val instance = clazz.getConstructor(Integer.TYPE).newInstance(TW_CLIENT_ID)
            val openResult =
                (clazz.getMethod("open", ShortArray::class.java)
                    .invoke(instance, TW_EVENTS.copyOf()) as? Number)?.toInt()
                    ?: -1

            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TW_STATE",
                "classLoaded=true openResult=$openResult events=${TW_EVENTS.size}",
            )

            if (openResult != TW_OPEN_SUCCESS) {
                runCatching { clazz.getMethod("close").invoke(instance) }
                return
            }

            // Keep the same order as NavRadio+ 4.08: open -> start -> addHandler("radio").
            clazz.getMethod("start").invoke(instance)
            clazz.getMethod("addHandler", String::class.java, Handler::class.java)
                .invoke(instance, TW_HANDLER_NAME, handler)

            twUtilClass = clazz
            twUtil = instance
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TW_STATE",
                "started handler=$TW_HANDLER_NAME keyEvent=0x${TW_KEY_EVENT.toString(16)}",
            )
        }.onFailure { throwable ->
            val error = throwable.rootCause()
            MediaKeyDiagnostics.record(
                appContext,
                "FYT_TW_STATE",
                "initFailed=${error.javaClass.simpleName}:${error.message.sanitized()}",
            )
        }
    }

    private fun handleTwMessage(message: Message) {
        if (released) return
        val fmActive = radio.state.value.isActive
        val action =
            resolveFytTwKeyAction(
                eventCode = message.what,
                keyCode = message.arg2,
                pressType = message.arg1,
                fmActive = fmActive,
            )

        MediaKeyDiagnostics.record(
            appContext,
            "FYT_TW_EVENT",
            "what=0x${message.what.toString(16)} arg1=${message.arg1} arg2=${message.arg2} " +
                "obj=${message.obj.toString().sanitized()} fmActive=$fmActive action=$action",
        )

        if (action == FytTwKeyAction.NONE) return

        val handled =
            when (action) {
                FytTwKeyAction.NEXT_FAVOURITE ->
                    PhysicalFmMediaKeyBridge.handleDirection(next = true)

                FytTwKeyAction.PREVIOUS_FAVOURITE ->
                    PhysicalFmMediaKeyBridge.handleDirection(next = false)

                FytTwKeyAction.SEEK_UP -> {
                    radio.seek(up = true)
                    true
                }

                FytTwKeyAction.SEEK_DOWN -> {
                    radio.seek(up = false)
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

    companion object {
        private const val TW_UTIL_CLASS = "android.tw.john.TWUtil"
        private const val TW_CLIENT_ID = 1
        private const val TW_HANDLER_NAME = "radio"
        private const val TW_OPEN_SUCCESS = 0
        internal const val TW_KEY_EVENT = 0x0201
        internal const val TW_KEY_NEXT = 19
        internal const val TW_KEY_PREVIOUS = 21
        internal const val TW_PRESS_SHORT = 1
        internal const val TW_PRESS_LONG = 2

        // Exact event subscription used by NavRadio+ 4.08 on FYT/Dudu7.
        private val TW_EVENTS =
            shortArrayOf(
                0x0109.toShort(),
                0x010A.toShort(),
                0x0201.toShort(),
                0x0203.toShort(),
                0x0301.toShort(),
                0x0302.toShort(),
                0x0401.toShort(),
                0x0402.toShort(),
                0x0404.toShort(),
                0x0405.toShort(),
                0x0406.toShort(),
                0x9E00.toShort(),
            )
    }
}

internal enum class FytTwKeyAction {
    NONE,
    NEXT_FAVOURITE,
    PREVIOUS_FAVOURITE,
    SEEK_UP,
    SEEK_DOWN,
}

internal fun resolveFytTwKeyAction(
    eventCode: Int,
    keyCode: Int,
    pressType: Int,
    fmActive: Boolean,
): FytTwKeyAction {
    if (!fmActive || eventCode != Dudu7FytTwMediaKeys.TW_KEY_EVENT) return FytTwKeyAction.NONE

    return when (keyCode) {
        Dudu7FytTwMediaKeys.TW_KEY_NEXT ->
            when (pressType) {
                Dudu7FytTwMediaKeys.TW_PRESS_SHORT -> FytTwKeyAction.NEXT_FAVOURITE
                Dudu7FytTwMediaKeys.TW_PRESS_LONG -> FytTwKeyAction.SEEK_UP
                else -> FytTwKeyAction.NONE
            }

        Dudu7FytTwMediaKeys.TW_KEY_PREVIOUS ->
            when (pressType) {
                Dudu7FytTwMediaKeys.TW_PRESS_SHORT -> FytTwKeyAction.PREVIOUS_FAVOURITE
                Dudu7FytTwMediaKeys.TW_PRESS_LONG -> FytTwKeyAction.SEEK_DOWN
                else -> FytTwKeyAction.NONE
            }

        else -> FytTwKeyAction.NONE
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
