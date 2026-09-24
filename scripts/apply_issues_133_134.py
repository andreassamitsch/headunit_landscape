from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Version 13.7.68
build = ROOT / "app/build.gradle.kts"
replace_once(build, "versionCode = 1370076", "versionCode = 1370077")
replace_once(build, 'versionName = "13.7.67"', 'versionName = "13.7.68"')

# Bug #133: every explicit YT selection must suppress one stale YT snapshot restore,
# even when the previous queue was already a YT/Favourites queue.
coordinator = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinator.kt"
replace_once(
    coordinator,
    """        memory.markUserYtSelection(\n            requiresRestoreBypass = current != Dudu7PlaybackSource.YT_MUSIC,\n        )\n""",
    """        // An explicit song selection owns the next YT queue. This must bypass one\n        // remembered YT snapshot restore even when YT/Favourites was already active;\n        // otherwise the tab switch to Queue can resurrect the old favourites queue.\n        memory.markUserYtSelection(requiresRestoreBypass = true)\n""",
)

# Regression test: the previously encoded behaviour was exactly the bug.
coordinator_test = ROOT / "app/src/test/kotlin/com/metrolist/music/playback/Dudu7SourcePlaybackCoordinatorTest.kt"
replace_once(
    coordinator_test,
    """    @Test\n    fun `new YT selection while YT is already active leaves no stale bypass`() {\n        val memory = Dudu7SourcePlaybackMemory()\n\n        memory.markUserYtSelection(requiresRestoreBypass = false)\n\n        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)\n        assertFalse(memory.consumeUserYtSelection())\n    }\n""",
    """    @Test\n    fun `explicit YT selection while YT is already active bypasses stale queue restore once`() {\n        val memory = Dudu7SourcePlaybackMemory()\n\n        memory.markUserYtSelection(requiresRestoreBypass = true)\n\n        assertEquals(Dudu7PlaybackSource.YT_MUSIC, memory.activeSource)\n        assertTrue(memory.consumeUserYtSelection())\n        assertFalse(memory.consumeUserYtSelection())\n    }\n""",
)

# Feature #134: expose the original MetroList Home route in the existing Dudu7 NavHost.
vehicle = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleLandscapeLayout.kt"
replace_once(
    vehicle,
    """    QUEUE(\"Warteschlange\", R.drawable.queue_music, VEHICLE_QUEUE_ROUTE),\n    LIBRARY(\"Bibliothek\", R.drawable.library_music_outlined, Screens.Library.route),\n""",
    """    HOME(\"Home\", R.drawable.home_outlined, Screens.Home.route),\n    QUEUE(\"Warteschlange\", R.drawable.queue_music, VEHICLE_QUEUE_ROUTE),\n    LIBRARY(\"Bibliothek\", R.drawable.library_music_outlined, Screens.Library.route),\n""",
)

tab_store = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/variant/VehicleTabOrderStore.kt"
replace_once(
    tab_store,
    """        listOf(\n            \"QUEUE\",\n""",
    """        listOf(\n            \"HOME\",\n            \"QUEUE\",\n""",
)

# Guardrails.
assert 'versionCode = 1370077' in build.read_text(encoding='utf-8')
assert 'versionName = "13.7.68"' in build.read_text(encoding='utf-8')
assert 'requiresRestoreBypass = current != Dudu7PlaybackSource.YT_MUSIC' not in coordinator.read_text(encoding='utf-8')
assert 'memory.markUserYtSelection(requiresRestoreBypass = true)' in coordinator.read_text(encoding='utf-8')
assert 'HOME("Home", R.drawable.home_outlined, Screens.Home.route)' in vehicle.read_text(encoding='utf-8')
assert '"HOME",' in tab_store.read_text(encoding='utf-8')
print("Issues #133 and #134 patch applied")
