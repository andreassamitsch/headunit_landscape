from pathlib import Path

radio_path = Path('app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt')
text = radio_path.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one occurrence, found {count}: {old[:120]!r}')
    text = text.replace(old, new, 1)


replace_once(
    'import com.metrolist.music.playback.Dudu7FmSessionOwnership\n'
    'import com.metrolist.music.playback.Dudu7FmSessionRouting\n',
    'import com.metrolist.music.playback.Dudu7FmSessionOwnership\n'
    'import com.metrolist.music.playback.Dudu7FmSessionRouting\n'
    'import com.metrolist.music.playback.Dudu7SyuRadioIpc\n',
)

replace_once(
    '''                MediaKeyDiagnostics.record(
                    context,
                    "DUDU7_SESSION_CLAIM",
                    "source=powerOn claimed=true changed=$claimChanged target=$target",
                )
                delay(DUDU7_SESSION_PROPAGATION_MS)
''',
    '''                MediaKeyDiagnostics.record(
                    context,
                    "DUDU7_SESSION_CLAIM",
                    "source=powerOn claimed=true changed=$claimChanged target=$target",
                )
                val syuReady = Dudu7SyuRadioIpc.claimFmSource()
                MediaKeyDiagnostics.record(
                    context,
                    "SYU_IPC_SOURCE",
                    "source=powerOn requestQueued=true mainReady=$syuReady target=$target",
                )
                delay(DUDU7_SESSION_PROPAGATION_MS)
''',
)

replace_once(
    '''            } catch (error: Throwable) {
                Timber.tag(TAG).e(error, "Could not start physical FM")
                cleanupHardware()
                val released = Dudu7FmSessionOwnership.release()
''',
    '''            } catch (error: Throwable) {
                Timber.tag(TAG).e(error, "Could not start physical FM")
                Dudu7SyuRadioIpc.releaseFmSource()
                cleanupHardware()
                val released = Dudu7FmSessionOwnership.release()
''',
)

replace_once(
    '''            cleanupHardware()
            _state.update {
''',
    '''            Dudu7SyuRadioIpc.releaseFmSource()
            cleanupHardware()
            _state.update {
''',
)

radio_path.write_text(text)

gradle_path = Path('app/build.gradle.kts')
gradle = gradle_path.read_text()
if gradle.count('versionCode = 1370051') != 1 or gradle.count('versionName = "13.7.42"') != 1:
    raise SystemExit('Unexpected current app version; refusing automatic patch')
gradle = gradle.replace('versionCode = 1370051', 'versionCode = 1370052', 1)
gradle = gradle.replace('versionName = "13.7.42"', 'versionName = "13.7.43"', 1)
gradle_path.write_text(gradle)
