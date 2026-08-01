from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


protocol = r'''package com.metrolist.music.playback

/** One reflected TWUtil write call captured from the NavRadio+ 4.08 FYT path. */
internal data class FytTwWrite(
    val command: Int,
    val value1: Int,
    val value2: Int? = null,
)

/**
 * Exact FYT protocol values used by NavRadio+ 4.08 on UIS7862/UIS7870 units.
 *
 * Keeping these values as data makes the reverse-engineered contract regression-testable.
 */
internal object Dudu7FytTwProtocol {
    const val CLIENT_ID = 1
    const val HANDLER_NAME = "radio"
    const val OPEN_SUCCESS = 0

    const val EVENT_KEY = 0x0201
    const val EVENT_RADIO_STATE = 0x0301
    const val KEY_NEXT = 19
    const val KEY_PREVIOUS = 21
    const val PRESS_SHORT = 1
    const val PRESS_LONG = 2

    val EVENTS =
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

    // RadioService.init() directly after open -> start -> addHandler("radio").
    val INITIALIZATION_WRITES =
        listOf(
            FytTwWrite(0x0109, 0xFF),
            FytTwWrite(0x010A, 0xFF),
            FytTwWrite(0x010A, 0xFF, 1),
            FytTwWrite(0x0112, 0xFF),
            FytTwWrite(0x010A, 0xFF, 0),
            FytTwWrite(0x0301, 0xFF),
            FytTwWrite(0x0406, 0),
            FytTwWrite(0x0401, 0xFF),
            FytTwWrite(0x0404, 0xFF),
            FytTwWrite(0x0405, 0xFF),
            FytTwWrite(0x0203, 0xFF),
        )

    // com.navimods.radio.tw.e.q(): claim FM and its audio source.
    val ENTER_FM_WRITES =
        listOf(
            FytTwWrite(0x0301, 0xC0, 1),
            FytTwWrite(0x9E00, 1),
            FytTwWrite(0x9E11, 0xC0, 1),
        )

    // com.navimods.radio.tw.e.r(): release FM and its audio source.
    val EXIT_FM_WRITES =
        listOf(
            FytTwWrite(0x0301, 0xC0, 0),
            FytTwWrite(0x9E11, 0xC0, 0x81),
            FytTwWrite(0x9E00, 0x81),
            FytTwWrite(0x9E00, 0x81, 0),
        )
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
    vendorRadioActive: Boolean = true,
): FytTwKeyAction {
    if (!fmActive || !vendorRadioActive || eventCode != Dudu7FytTwProtocol.EVENT_KEY) {
        return FytTwKeyAction.NONE
    }

    return when (keyCode) {
        Dudu7FytTwProtocol.KEY_NEXT ->
            when (pressType) {
                Dudu7FytTwProtocol.PRESS_SHORT -> FytTwKeyAction.NEXT_FAVOURITE
                Dudu7FytTwProtocol.PRESS_LONG -> FytTwKeyAction.SEEK_UP
                else -> FytTwKeyAction.NONE
            }

        Dudu7FytTwProtocol.KEY_PREVIOUS ->
            when (pressType) {
                Dudu7FytTwProtocol.PRESS_SHORT -> FytTwKeyAction.PREVIOUS_FAVOURITE
                Dudu7FytTwProtocol.PRESS_LONG -> FytTwKeyAction.SEEK_DOWN
                else -> FytTwKeyAction.NONE
            }

        else -> FytTwKeyAction.NONE
    }
}
'''

controller = r'''package com.metrolist.music.radio.fyt

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
'''

tests = r'''package com.metrolist.music.playback

import org.junit.Assert.assertEquals
import org.junit.Test

class Dudu7FytTwMediaKeysTest {
    @Test
    fun `short FYT key presses navigate FM favourites`() {
        assertEquals(
            FytTwKeyAction.NEXT_FAVOURITE,
            resolveFytTwKeyAction(0x0201, 19, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.PREVIOUS_FAVOURITE,
            resolveFytTwKeyAction(0x0201, 21, 1, fmActive = true),
        )
    }

    @Test
    fun `long FYT key presses start seek in matching direction`() {
        assertEquals(
            FytTwKeyAction.SEEK_UP,
            resolveFytTwKeyAction(0x0201, 19, 2, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.SEEK_DOWN,
            resolveFytTwKeyAction(0x0201, 21, 2, fmActive = true),
        )
    }

    @Test
    fun `key messages require both MetroList and FYT radio ownership`() {
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 19, 1, fmActive = false),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(
                0x0201,
                19,
                1,
                fmActive = true,
                vendorRadioActive = false,
            ),
        )
    }

    @Test
    fun `unrelated TW events keys and press types are ignored`() {
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0203, 19, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 20, 1, fmActive = true),
        )
        assertEquals(
            FytTwKeyAction.NONE,
            resolveFytTwKeyAction(0x0201, 19, 0, fmActive = true),
        )
    }

    @Test
    fun `event subscription exactly matches NavRadio 4 08 FYT path`() {
        assertEquals(
            listOf(0x0109, 0x010A, 0x0201, 0x0203, 0x0301, 0x0302, 0x0401, 0x0402, 0x0404, 0x0405, 0x0406, 0x9E00),
            Dudu7FytTwProtocol.EVENTS.map { it.toInt() and 0xFFFF },
        )
    }

    @Test
    fun `initialization writes exactly match NavRadio 4 08`() {
        assertEquals(
            listOf(
                FytTwWrite(0x0109, 0xFF),
                FytTwWrite(0x010A, 0xFF),
                FytTwWrite(0x010A, 0xFF, 1),
                FytTwWrite(0x0112, 0xFF),
                FytTwWrite(0x010A, 0xFF, 0),
                FytTwWrite(0x0301, 0xFF),
                FytTwWrite(0x0406, 0),
                FytTwWrite(0x0401, 0xFF),
                FytTwWrite(0x0404, 0xFF),
                FytTwWrite(0x0405, 0xFF),
                FytTwWrite(0x0203, 0xFF),
            ),
            Dudu7FytTwProtocol.INITIALIZATION_WRITES,
        )
    }

    @Test
    fun `FM ownership writes match NavRadio enter and exit logic`() {
        assertEquals(
            listOf(
                FytTwWrite(0x0301, 0xC0, 1),
                FytTwWrite(0x9E00, 1),
                FytTwWrite(0x9E11, 0xC0, 1),
            ),
            Dudu7FytTwProtocol.ENTER_FM_WRITES,
        )
        assertEquals(
            listOf(
                FytTwWrite(0x0301, 0xC0, 0),
                FytTwWrite(0x9E11, 0xC0, 0x81),
                FytTwWrite(0x9E00, 0x81),
                FytTwWrite(0x9E00, 0x81, 0),
            ),
            Dudu7FytTwProtocol.EXIT_FM_WRITES,
        )
    }
}
'''

Path("app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FytTwMediaKeys.kt").write_text(protocol)
Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/Dudu7FytTwController.kt").write_text(controller)
Path("app/src/test/kotlin/com/metrolist/music/playback/Dudu7FytTwMediaKeysTest.kt").write_text(tests)

radio_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
radio = radio_path.read_text()
radio = replace_once(
    radio,
    "import java.lang.reflect.Method\n",
    "",
    "obsolete reflection import",
)
radio = replace_once(
    radio,
    "private var twUtil: TwUtilBridge? = null",
    "private var twUtil: Dudu7FytTwController? = null",
    "shared TWUtil field",
)
radio = replace_once(
    radio,
    "twUtil = TwUtilBridge()",
    "twUtil = Dudu7FytTwController.get(applicationContext)",
    "shared TWUtil construction",
)
radio = replace_once(
    radio,
    '''                repeat(3) { index ->
                    twUtil?.setAudioSourceFm()
                    if (index < 2) delay(100)
                }''',
    '''                // Reassert the NavRadio+ FM audio-source ownership after native tuning.
                twUtil?.setAudioSourceFm()''',
    "legacy repeated source writes",
)
legacy_start = radio.index("\n    private class TwUtilBridge {")
if not radio.endswith("\n}\n"):
    raise SystemExit("FytPhysicalRadio: unexpected file ending")
radio = radio[:legacy_start] + "\n}\n"
radio_path.write_text(radio)

routing_path = Path("app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FmSessionRouting.kt")
routing = routing_path.read_text()
routing = replace_once(
    routing,
    "            val twMediaKeys = Dudu7FytTwMediaKeys(appContext)\n",
    "",
    "duplicate TWUtil construction",
)
routing = replace_once(
    routing,
    "                        twMediaKeys.release()\n",
    "",
    "duplicate TWUtil release",
)
routing_path.write_text(routing)

gradle_path = Path("app/build.gradle.kts")
gradle = gradle_path.read_text()
gradle = replace_once(gradle, "versionCode = 1370048", "versionCode = 1370049", "versionCode")
gradle = replace_once(gradle, 'versionName = "13.7.39"', 'versionName = "13.7.40"', "versionName")
gradle_path.write_text(gradle)
