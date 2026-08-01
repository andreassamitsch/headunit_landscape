from pathlib import Path

path = Path('app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt')
text = path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one occurrence, found {count}: {old[:100]!r}')
    text = text.replace(old, new, 1)


replace_once(
    'import com.metrolist.music.playback.Dudu7FmMediaButtonRouting\n'
    'import com.metrolist.music.playback.Dudu7FmSessionRouting\n',
    'import com.metrolist.music.playback.Dudu7FmMediaButtonRouting\n'
    'import com.metrolist.music.playback.Dudu7FmSessionOwnership\n'
    'import com.metrolist.music.playback.Dudu7FmSessionRouting\n'
    'import com.metrolist.music.playback.MediaKeyDiagnostics\n',
)
replace_once('import java.lang.reflect.Method\n', '')
replace_once(
    ' * It talks directly to the firmware-provided libfmjni.so and TWUtil MCU bridge;\n'
    ' * NavRadio+ is neither referenced nor required at runtime.\n',
    ' * It uses the Dudu7/UIS7870 FmService/FmNative path exposed by the Syu RadioProxy.\n'
    ' * Optional TWUtil backends belong to other head-unit families and are not used here.\n',
)
replace_once(
    '    private const val AF_RSSI_HYSTERESIS = 3\n',
    '    private const val AF_RSSI_HYSTERESIS = 3\n'
    '    private const val DUDU7_SESSION_PROPAGATION_MS = 150L\n',
)
replace_once('    private var twUtil: TwUtilBridge? = null\n', '')
replace_once('            twUtil = TwUtilBridge()\n', '')

replace_once(
    '''            try {
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
                runCatching { fm.setRds(false) }
                val tuneOk = fm.tune(target)
                fm.setMute(false)
                repeat(3) { index ->
                    twUtil?.setAudioSourceFm()
                    if (index < 2) delay(100)
                }
                FmNative.setFirmwareFmVolumeEnabled(true)
''',
    '''            try {
                // NavRadio+ publishes its Dudu7 MediaSession before claiming RadioProxy/FmNative.
                // Give Android/com.syu.ms one dispatch turn before activating the hardware source.
                val claimChanged = Dudu7FmSessionOwnership.claim()
                MediaKeyDiagnostics.record(
                    context,
                    "DUDU7_SESSION_CLAIM",
                    "source=powerOn claimed=true changed=$claimChanged target=$target",
                )
                delay(DUDU7_SESSION_PROPAGATION_MS)

                requestAudioFocus()
                FytAudioRouter.prepare(context)
                installRdsListener()

                val openOk = fm.openDev()
                val powerOk = fm.powerUp(target)
                runCatching { fm.setRds(false) }
                val tuneOk = fm.tune(target)
                fm.setMute(false)
                FmNative.setFirmwareFmVolumeEnabled(true)
''',
)

replace_once(
    '''            } catch (error: Throwable) {
                Timber.tag(TAG).e(error, "Could not start physical FM")
                cleanupHardware()
                _state.update { it.copy(isActive = false, isBusy = false, error = error.message ?: "Radio konnte nicht gestartet werden") }
            }
''',
    '''            } catch (error: Throwable) {
                Timber.tag(TAG).e(error, "Could not start physical FM")
                cleanupHardware()
                val released = Dudu7FmSessionOwnership.release()
                MediaKeyDiagnostics.record(
                    context,
                    "DUDU7_SESSION_CLAIM",
                    "source=powerOn_failed claimed=false changed=$released error=${error.javaClass.simpleName}",
                )
                _state.update { it.copy(isActive = false, isBusy = false, error = error.message ?: "Radio konnte nicht gestartet werden") }
            }
''',
)

replace_once(
    '''            }
            Timber.tag(TAG).i("Physical FM released")
''',
    '''            }
            val released = Dudu7FmSessionOwnership.release()
            appContext?.let { context ->
                MediaKeyDiagnostics.record(
                    context,
                    "DUDU7_SESSION_CLAIM",
                    "source=powerOff claimed=false changed=$released",
                )
            }
            Timber.tag(TAG).i("Physical FM released")
''',
)

replace_once(
    '''        runCatching { native?.closeDev() }
        runCatching { twUtil?.radioOff() }
        runCatching { twUtil?.close() }
        FmNative.setFirmwareFmVolumeEnabled(false)
''',
    '''        runCatching { native?.closeDev() }
        FmNative.setFirmwareFmVolumeEnabled(false)
''',
)

marker = '\n    private class TwUtilBridge {'
start = text.find(marker)
if start < 0:
    raise SystemExit('TwUtilBridge class not found')
if not text.rstrip().endswith('}'):
    raise SystemExit('Unexpected FytPhysicalRadio ending')
text = text[:start] + '\n}\n'
path.write_text(text)

gradle = Path('app/build.gradle.kts')
build = gradle.read_text()
if build.count('versionCode = 1370050') != 1 or build.count('versionName = "13.7.41"') != 1:
    raise SystemExit('Unexpected current app version')
build = build.replace('versionCode = 1370050', 'versionCode = 1370051', 1)
build = build.replace('versionName = "13.7.41"', 'versionName = "13.7.42"', 1)
gradle.write_text(build)
