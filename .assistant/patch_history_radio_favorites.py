from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected source block: {label}")
    return text.replace(old, new, 1)

# Persist the original HistoryScreen source choice. Online is the default when logged in.
vm_path = Path("app/src/main/kotlin/com/metrolist/music/viewmodels/HistoryViewModel.kt")
vm = vm_path.read_text(encoding="utf-8")
vm = replace_once(
    vm,
    "    var historySource = MutableStateFlow(HistorySource.LOCAL)\n",
    """    private val historyPreferences =
        context.getSharedPreferences(\"metrolist_history\", Context.MODE_PRIVATE)

    val historySource =
        MutableStateFlow(
            historyPreferences.getString(KEY_HISTORY_SOURCE, null)
                ?.let { stored -> runCatching { HistorySource.valueOf(stored) }.getOrNull() }
                ?: HistorySource.REMOTE,
        )
""",
    "HistoryViewModel initial source",
)
vm = replace_once(
    vm,
    """    fun fetchRemoteHistory() {
""",
    """    fun setHistorySource(source: HistorySource) {
        historySource.value = source
        historyPreferences.edit().putString(KEY_HISTORY_SOURCE, source.name).apply()
        if (source == HistorySource.REMOTE && historyPage.value == null) {
            fetchRemoteHistory()
        }
    }

    fun fetchRemoteHistory() {
""",
    "HistoryViewModel setter insertion",
)
vm = replace_once(
    vm,
    """    fun fetchRemoteHistory() {
        viewModelScope.launch(Dispatchers.IO) {
            YouTube.musicHistory().onSuccess {
                historyPage.value = it
            }.onFailure {
                reportException(it)
            }
        }
    }
}
""",
    """    fun fetchRemoteHistory() {
        viewModelScope.launch(Dispatchers.IO) {
            YouTube.musicHistory().onSuccess {
                historyPage.value = it
            }.onFailure {
                reportException(it)
            }
        }
    }

    private companion object {
        const val KEY_HISTORY_SOURCE = \"history_source\"
    }
}
""",
    "HistoryViewModel preference key",
)
vm_path.write_text(vm, encoding="utf-8")

screen_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/HistoryScreen.kt")
screen = screen_path.read_text(encoding="utf-8")
screen = replace_once(
    screen,
    """    val isLoggedIn =
        remember(innerTubeCookie) {
            \"SAPISID\" in parseCookieString(innerTubeCookie)
        }

""",
    """    val isLoggedIn =
        remember(innerTubeCookie) {
            \"SAPISID\" in parseCookieString(innerTubeCookie)
        }
    // Keep the user's original Local/Online choice. Without an account only the
    // local source is usable, but the saved Online preference is not overwritten.
    val displayedHistorySource =
        if (isLoggedIn) historySource else HistorySource.LOCAL

""",
    "HistoryScreen effective source",
)
screen = replace_once(
    screen,
    """                    currentValue = historySource,
                    onValueUpdate = {
                        viewModel.historySource.value = it
                        if (it == HistorySource.REMOTE) {
                            viewModel.fetchRemoteHistory()
                        }
                    },
""",
    """                    currentValue = displayedHistorySource,
                    onValueUpdate = viewModel::setHistorySource,
""",
    "HistoryScreen chips",
)
# All rendering/actions must use the effective source, especially while logged out.
screen = screen.replace("historySource == HistorySource.REMOTE", "displayedHistorySource == HistorySource.REMOTE")
if "viewModel.historySource.value" in screen:
    raise SystemExit("Direct HistorySource mutation remained in HistoryScreen")
screen_path.write_text(screen, encoding="utf-8")

# Saved stations now use the same reliable zero-index playback path as search results.
radio_path = Path("app/src/main/kotlin/com/metrolist/music/ui/screens/radio/WebRadioScreen.kt")
radio = radio_path.read_text(encoding="utf-8")
radio = replace_once(
    radio,
    """    fun playSaved(station: RadioStation) {
        val stations = savedStations.ifEmpty { listOf(station) }
        val startIndex = stations.indexOfFirst { it.uuid == station.uuid }.coerceAtLeast(0)
        playerConnection.playQueue(
            ListQueue(
                title = \"WebRadio\",
                items = stations.map { it.toMediaItem() },
                startIndex = startIndex,
            ),
        )
    }
""",
    """    fun playSaved(station: RadioStation) {
        // ListQueue playback is most reliable from index 0. Rotate the saved list so
        // the explicitly selected favorite starts immediately while previous/next
        // can still switch through all saved stations.
        val stations = savedStations.ifEmpty { listOf(station) }
        val selected = stations.firstOrNull { it.uuid == station.uuid } ?: station
        val orderedStations = listOf(selected) + stations.filterNot { it.uuid == selected.uuid }
        playerConnection.playQueue(
            ListQueue(
                title = \"WebRadio\",
                items = orderedStations.map { it.toMediaItem() },
                startIndex = 0,
            ),
        )
    }
""",
    "WebRadio saved playback",
)
radio_path.write_text(radio, encoding="utf-8")

# Raise the update version.
build_path = Path("app/build.gradle.kts")
build = build_path.read_text(encoding="utf-8")
build = replace_once(build, "versionCode = 152", "versionCode = 153", "versionCode")
build = replace_once(build, 'versionName = "13.6.3"', 'versionName = "13.6.4"', "versionName")
build_path.write_text(build, encoding="utf-8")

client_path = Path("app/src/main/kotlin/com/metrolist/music/radio/RadioBrowserClient.kt")
client = client_path.read_text(encoding="utf-8").replace(
    'MetrolistHU/13.6.2 (Android WebRadio)',
    'MetrolistHU/13.6.4 (Android WebRadio)',
)
client_path.write_text(client, encoding="utf-8")

# Strengthen the deterministic UI test: start the second saved favorite first.
test_path = Path("scripts/dudu7_webradio_smoke.sh")
test = test_path.read_text(encoding="utf-8")
test = replace_once(
    test,
    """# Play station one and wait for ICY StreamTitle metadata on the left player.
tap_text \"station one\" 1 \"=Test Radio One\"
sleep 12
capture \"radio-one-playing\"
assert_text \"station one stream title\" 0 \"Test Track One\"
assert_text \"station one artist\" 0 \"Test Artist One\"
assert_text \"live indicator\" 0 \"LIVE\"

# Player next must move through the saved station queue.
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 12
capture \"radio-two-playing\"
assert_text \"station two stream title\" 0 \"Test Track Two\"
assert_text \"station two artist\" 0 \"Test Artist Two\"

# Previous returns to station one.
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 10
assert_text \"previous returns to station one\" 0 \"Test Track One\"
capture \"radio-previous\"
""",
    """# Start the SECOND saved favorite first. This explicitly covers the former
# non-zero start-index failure that did not occur when testing the first favorite.
tap_text \"station two favorite\" 1 \"=Test Radio Two\"
sleep 12
capture \"radio-two-favorite-playing\"
assert_text \"second favorite stream title\" 0 \"Test Track Two\"
assert_text \"second favorite artist\" 0 \"Test Artist Two\"
assert_text \"live indicator\" 0 \"LIVE\"
assert_text \"queue opened for favorite\" 1 \"=Test Radio Two\"

# Player next must move through the rotated saved-station queue.
adb shell input keyevent KEYCODE_MEDIA_NEXT || true
sleep 12
capture \"radio-one-after-next\"
assert_text \"next reaches first favorite\" 0 \"Test Track One\"
assert_text \"first favorite artist\" 0 \"Test Artist One\"

# Previous returns to the originally selected second favorite.
adb shell input keyevent KEYCODE_MEDIA_PREVIOUS || true
sleep 10
assert_text \"previous returns to selected favorite\" 0 \"Test Track Two\"
capture \"radio-favorite-previous\"
""",
    "WebRadio smoke favorite sequence",
)
test_path.write_text(test, encoding="utf-8")

# Final static guarantees.
checks = {
    vm_path: [
        'getSharedPreferences("metrolist_history"',
        '?: HistorySource.REMOTE',
        'fun setHistorySource(source: HistorySource)',
        'putString(KEY_HISTORY_SOURCE, source.name)',
    ],
    screen_path: [
        'val displayedHistorySource',
        'currentValue = displayedHistorySource',
        'onValueUpdate = viewModel::setHistorySource',
    ],
    radio_path: [
        'val orderedStations = listOf(selected)',
        'startIndex = 0',
    ],
    test_path: ['station two favorite', 'second favorite stream title'],
}
for path, needles in checks.items():
    content = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in content:
            raise SystemExit(f"Missing {needle!r} in {path}")
