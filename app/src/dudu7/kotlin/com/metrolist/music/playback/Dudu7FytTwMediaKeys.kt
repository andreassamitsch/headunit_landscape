package com.metrolist.music.playback

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
