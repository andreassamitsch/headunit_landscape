from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


controller_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/Dudu7FytTwController.kt")
controller = controller_path.read_text()
controller = replace_once(
    controller,
    '''                write3 = clazz.getMethod("write", Integer.TYPE, Integer.TYPE, Integer.TYPE)
                vendorRadioActive = false

                MediaKeyDiagnostics.record(''',
    '''                write3 = clazz.getMethod("write", Integer.TYPE, Integer.TYPE, Integer.TYPE)
                vendorRadioActive = false

                // NavRadio+ performs this sequence exactly once after registering the handler.
                Dudu7FytTwProtocol.INITIALIZATION_WRITES.forEach {
                    writeAndRecord("init", it)
                }

                MediaKeyDiagnostics.record(''',
    "one-time initialization",
)
controller = replace_once(
    controller,
    '''    fun initRadioSequence() {
        applySequence("init", Dudu7FytTwProtocol.INITIALIZATION_WRITES)
    }

''',
    "",
    "remove repeated init method",
)
controller = replace_once(
    controller,
    '''    fun radioOnFm() {
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
''',
    '''    fun radioOnFm() {
        // NavRadio+ does not assume ownership here. Event 0x0301 is the source of truth.
        applySequence("enter_fm", Dudu7FytTwProtocol.ENTER_FM_WRITES)
    }
''',
    "event-driven active state",
)
controller = replace_once(
    controller,
    '''    /** Reassert only the NavRadio+ audio-source writes after native tuner startup. */
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

''',
    "",
    "remove non-NavRadio writes",
)
controller_path.write_text(controller)

radio_path = Path("app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt")
radio = radio_path.read_text()
radio = replace_once(
    radio,
    '''                twUtil?.open()
                twUtil?.initRadioSequence()
                delay(150)
                twUtil?.radioOnFm()
                delay(100)
                twUtil?.unmute()
                delay(50)
''',
    '''                if (twUtil?.open() != true) {
                    error("FYT TWUtil konnte nicht initialisiert werden")
                }
                delay(150)
                twUtil?.radioOnFm()
                delay(100)
''',
    "power-on lifecycle",
)
radio = replace_once(
    radio,
    '''                fm.setMute(false)
                // Reassert the NavRadio+ FM audio-source ownership after native tuning.
                twUtil?.setAudioSourceFm()
                FmNative.setFirmwareFmVolumeEnabled(true)
''',
    '''                fm.setMute(false)
                FmNative.setFirmwareFmVolumeEnabled(true)
''',
    "remove duplicate source ownership",
)
radio = replace_once(
    radio,
    '''            val result = runCatching { native?.setMute(mute) }.getOrNull()
            if (mute) twUtil?.mute() else twUtil?.unmute()
            if (result != null) _state.update { it.copy(isMuted = mute) }
''',
    '''            val result = runCatching { native?.setMute(mute) }.getOrNull()
            if (result != null) _state.update { it.copy(isMuted = mute) }
''',
    "native mute only",
)
radio = replace_once(
    radio,
    '''        runCatching { twUtil?.radioOff() }
        runCatching { twUtil?.close() }
        FmNative.setFirmwareFmVolumeEnabled(false)
''',
    '''        // NavRadio+ releases FM ownership here but keeps the shared TWUtil handler alive.
        runCatching { twUtil?.radioOff() }
        FmNative.setFirmwareFmVolumeEnabled(false)
''',
    "keep shared client alive",
)
radio_path.write_text(radio)

routing_path = Path("app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7FmSessionRouting.kt")
routing = routing_path.read_text()
routing = replace_once(
    routing,
    '''                    release = {
                        legacyMediaSession.release()
                        player.release()
                    },
''',
    '''                    release = {
                        legacyMediaSession.release()
                        com.metrolist.music.radio.fyt.Dudu7FytTwController.get(appContext).close()
                        player.release()
                    },
''',
    "close shared client on service release",
)
routing_path.write_text(routing)
