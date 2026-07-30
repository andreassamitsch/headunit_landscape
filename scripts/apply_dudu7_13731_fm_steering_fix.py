#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Pure navigation rules: stable active UUID first, then deterministic reception fallbacks.
model = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmFavouriteModel.kt"
model.write_text('''package com.metrolist.music.radio.fyt

import java.util.UUID
import kotlin.math.abs

data class FmFavouriteRef(
    val id: String,
    val stationId: String,
    val frequency: Float,
    val pi: Int = 0,
)

/**
 * Pure rules for FM favourites. A favourite is a stable user item; frequencies are
 * only the last successful reception path and must never become its identity.
 */
object FmFavouriteModel {
    fun selectCurrentIndex(
        favourites: List<FmFavouriteRef>,
        frequency: Float,
        stationId: String,
    ): Int = resolveCurrentIndex(
        favourites = favourites,
        activeId = null,
        frequency = frequency,
        stationId = stationId,
        pi = 0,
        rdsConfirmed = false,
    )

    fun resolveCurrentIndex(
        favourites: List<FmFavouriteRef>,
        activeId: String?,
        frequency: Float,
        stationId: String,
        pi: Int,
        rdsConfirmed: Boolean,
    ): Int {
        activeId?.takeIf(String::isNotBlank)?.let { id ->
            favourites.indexOfFirst { it.id == id }.takeIf { it >= 0 }?.let { return it }
        }

        val exact = favourites.indices.filter { abs(favourites[it].frequency - frequency) < 0.05f }
        if (exact.size == 1) return exact.first()

        if (stationId.isNotBlank()) {
            val stationMatches = favourites.indices.filter {
                favourites[it].stationId.isNotBlank() && favourites[it].stationId == stationId
            }
            if (stationMatches.size == 1) return stationMatches.first()
        }

        if (rdsConfirmed && pi > 0) {
            val normalizedPi = pi and 0xffff
            val piMatches = favourites.indices.filter {
                favourites[it].pi > 0 && (favourites[it].pi and 0xffff) == normalizedPi
            }
            if (piMatches.size == 1) return piMatches.first()
        }

        return exact.firstOrNull() ?: -1
    }

    fun adjacentIndex(
        size: Int,
        currentIndex: Int,
        next: Boolean,
    ): Int {
        if (size <= 0) return -1
        return when {
            currentIndex !in 0 until size && next -> 0
            currentIndex !in 0 until size -> size - 1
            next -> (currentIndex + 1) % size
            else -> (currentIndex - 1 + size) % size
        }
    }

    fun existingIndexForUpsert(
        favourites: List<FmFavouriteRef>,
        frequency: Float,
        stationId: String,
    ): Int =
        if (stationId.isNotBlank()) {
            favourites.indexOfFirst { it.stationId == stationId }
        } else {
            favourites.indexOfFirst { it.stationId.isBlank() && abs(it.frequency - frequency) < 0.05f }
        }

    fun shouldGroupScan(firstStationId: String, secondStationId: String): Boolean =
        firstStationId.isNotBlank() && firstStationId == secondStationId

    fun legacyId(
        index: Int,
        frequency: Float,
        name: String,
        stationId: String,
    ): String =
        UUID.nameUUIDFromBytes(
            "metrolist-fm-v3:$index:${"%.1f".format(java.util.Locale.ROOT, frequency)}:$name:$stationId"
                .toByteArray(Charsets.UTF_8),
        ).toString()

    fun newId(): String = UUID.randomUUID().toString()
}
''', encoding="utf-8")

# One central navigation path for player buttons, MediaSession and steering-wheel keys.
order = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FmPresetOrderStore.kt"
order.write_text('''package com.metrolist.music.radio.fyt

import android.content.Context
import android.os.SystemClock
import timber.log.Timber
import kotlin.math.abs
import kotlin.math.roundToInt

/** Keeps FM-favourite order stable while AF changes only the last used frequency. */
object FmPresetOrderStore {
    private const val PREFS = "dudu7_physical_radio"
    private const val KEY_ORDER = "preset_order_v3"
    private const val LEGACY_KEY_ORDER_V2 = "preset_order_v2"
    private const val LEGACY_KEY_ORDER = "preset_order"

    fun ordered(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ): List<FytPhysicalRadio.Preset> {
        if (presets.isEmpty()) return emptyList()
        val preferences = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val storedIds = preferences.getString(KEY_ORDER, null).orEmpty()
            .lineSequence().map(String::trim).filter(String::isNotBlank).distinct().toList()
        val legacyKeys = preferences.getString(LEGACY_KEY_ORDER_V2, null).orEmpty()
            .lineSequence().map(String::trim).filter(String::isNotBlank).distinct().toList()
        val legacyFrequencies = preferences.getString(LEGACY_KEY_ORDER, null).orEmpty()
            .split(',').mapNotNull(String::toIntOrNull).distinct()

        val ordered = mutableListOf<FytPhysicalRadio.Preset>()
        storedIds.forEach { id ->
            presets.firstOrNull { it.id == id && ordered.none { existing -> existing.id == it.id } }
                ?.let(ordered::add)
        }
        legacyKeys.forEach { key ->
            presets.firstOrNull {
                key in FytPhysicalRadio.presetOrderKeys(it) && ordered.none { existing -> existing.id == it.id }
            }?.let(ordered::add)
        }
        legacyFrequencies.forEach { key ->
            presets.firstOrNull {
                frequencyKey(it.frequency) == key && ordered.none { existing -> existing.id == it.id }
            }?.let(ordered::add)
        }
        presets.forEach { preset -> if (ordered.none { it.id == preset.id }) ordered += preset }

        val normalizedIds = ordered.map(FytPhysicalRadio.Preset::id).filter(String::isNotBlank).distinct()
        if (normalizedIds != storedIds || legacyKeys.isNotEmpty() || legacyFrequencies.isNotEmpty()) {
            preferences.edit()
                .putString(KEY_ORDER, normalizedIds.joinToString("\n"))
                .remove(LEGACY_KEY_ORDER_V2)
                .remove(LEGACY_KEY_ORDER)
                .apply()
        }
        return ordered
    }

    fun persist(context: Context, presets: List<FytPhysicalRadio.Preset>) {
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
            .putString(KEY_ORDER, presets.map(FytPhysicalRadio::stablePresetKey).filter(String::isNotBlank).distinct().joinToString("\n"))
            .remove(LEGACY_KEY_ORDER_V2)
            .remove(LEGACY_KEY_ORDER)
            .apply()
    }

    fun remove(context: Context, preset: FytPhysicalRadio.Preset, remainingPresets: List<FytPhysicalRadio.Preset>) {
        FmFavouriteNavigationMemory.forget(preset.id)
        persist(context, remainingPresets.filterNot { it.id == preset.id })
    }

    private fun frequencyKey(value: Float): Int = (value * 10f).roundToInt()

    fun sameFrequency(first: Float, second: Float): Boolean = abs(first - second) < 0.05f
}

private object FmFavouriteNavigationMemory {
    private const val PENDING_SELECTION_MS = 2_500L

    @Volatile private var selectedId: String? = null
    @Volatile private var selectedAt: Long = 0L

    fun remember(id: String?) {
        selectedId = id?.takeIf(String::isNotBlank)
        selectedAt = if (selectedId == null) 0L else SystemClock.elapsedRealtime()
    }

    fun forget(id: String?) {
        if (id != null && selectedId == id) remember(null)
    }

    fun resolve(detectedId: String?, validIds: Set<String>, isBusy: Boolean): String? {
        val detected = detectedId?.takeIf { it in validIds }
        val remembered = selectedId?.takeIf { it in validIds }
        if (remembered == null) {
            if (selectedId != null) remember(null)
            return detected
        }
        if (detected == remembered) return detected
        val pending = SystemClock.elapsedRealtime() - selectedAt <= PENDING_SELECTION_MS
        return when {
            detected == null -> remembered
            isBusy || pending -> remembered
            else -> detected
        }
    }
}

internal fun rememberFmFavouriteSelection(id: String?) {
    FmFavouriteNavigationMemory.remember(id)
}

fun FytPhysicalRadio.tuneAdjacentFavourite(context: Context, next: Boolean) {
    val snapshot = state.value
    val favourites = FmPresetOrderStore.ordered(context, snapshot.presets)
    if (favourites.isEmpty()) {
        seek(next)
        return
    }

    val validIds = favourites.map(FytPhysicalRadio.Preset::id).filter(String::isNotBlank).toSet()
    val detectedId = snapshot.currentPreset?.id
    val activeId = FmFavouriteNavigationMemory.resolve(detectedId, validIds, snapshot.isBusy)
    val stationId = snapshot.rtrStableId.takeIf {
        abs(snapshot.rtrMatchedFrequency - snapshot.frequency) < 0.05f && snapshot.rtrMatchConfidence >= 60
    }.orEmpty()
    val freshRds = snapshot.rdsConfirmed && abs(snapshot.rdsFreshFrequency - snapshot.frequency) < 0.05f
    val refs = favourites.map { FmFavouriteRef(it.id, it.stationId, it.frequency, it.pi) }
    val currentIndex = FmFavouriteModel.resolveCurrentIndex(
        favourites = refs,
        activeId = activeId,
        frequency = snapshot.frequency,
        stationId = stationId,
        pi = snapshot.pi,
        rdsConfirmed = freshRds,
    )
    val targetIndex = FmFavouriteModel.adjacentIndex(favourites.size, currentIndex, next)
    if (targetIndex < 0) return
    val target = favourites[targetIndex]

    rememberFmFavouriteSelection(target.id)
    Timber.tag("FytFmFavouriteNav").i(
        "direction=%s busy=%s frequency=%.1f detected=%s remembered=%s currentIndex=%d targetIndex=%d target=%s targetFrequency=%.1f",
        if (next) "next" else "previous",
        snapshot.isBusy,
        snapshot.frequency,
        detectedId.orEmpty(),
        activeId.orEmpty(),
        currentIndex,
        targetIndex,
        target.id,
        target.frequency,
    )
    tunePreset(target)
}
''', encoding="utf-8")

radio = ROOT / "app/src/dudu7/kotlin/com/metrolist/music/radio/fyt/FytPhysicalRadio.kt"
replace_once(
    radio,
    '''    fun tunePreset(preset: Preset) {
        pendingPresetIdentity = preset
        tune(preset.frequency)
    }
''',
    '''    fun tunePreset(preset: Preset) {
        rememberFmFavouriteSelection(preset.id)
        pendingPresetIdentity = preset
        tune(preset.frequency)
    }
''',
    "remember selected preset before asynchronous tune",
)
replace_once(
    radio,
    '''    fun clearPresets() {
        pendingPresetIdentity = null
        persistPresets(emptyList())
''',
    '''    fun clearPresets() {
        pendingPresetIdentity = null
        rememberFmFavouriteSelection(null)
        persistPresets(emptyList())
''',
    "clear remembered favourite",
)
replace_once(
    radio,
    '''    private fun presetRef(preset: Preset): FmFavouriteRef =
        FmFavouriteRef(preset.id, preset.stationId, preset.frequency)
''',
    '''    private fun presetRef(preset: Preset): FmFavouriteRef =
        FmFavouriteRef(preset.id, preset.stationId, preset.frequency, preset.pi)
''',
    "include PI in favourite reference",
)

# Regression tests reproduce the Antenne-Steiermark position-zero loop.
test = ROOT / "app/src/test/kotlin/com/metrolist/music/radio/fyt/FmFavouriteModelTest.kt"
test.write_text('''package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FmFavouriteModelTest {
    private val favourites = listOf(
        FmFavouriteRef("antenne", "station:antenne_steiermark", 99.1f, 0xA902),
        FmFavouriteRef("oe3", "station:oe3", 99.5f, 0xA203),
        FmFavouriteRef("radio-stmk", "station:radio_steiermark", 95.4f, 0xA402),
    )

    @Test fun `exact frequency wins over station fallback`() {
        assertEquals(1, FmFavouriteModel.selectCurrentIndex(favourites, 99.5f, "station:antenne_steiermark"))
    }

    @Test fun `stable active id survives AF frequency changes`() {
        assertEquals(
            1,
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = "oe3",
                frequency = 107.0f,
                stationId = "",
                pi = 0,
                rdsConfirmed = false,
            ),
        )
    }

    @Test fun `confirmed unique PI restores current favourite`() {
        assertEquals(
            2,
            FmFavouriteModel.resolveCurrentIndex(
                favourites = favourites,
                activeId = null,
                frequency = 88.8f,
                stationId = "",
                pi = 0xA402,
                rdsConfirmed = true,
            ),
        )
    }

    @Test fun `missing active favourite falls back once then advances from remembered target`() {
        val firstTarget = FmFavouriteModel.adjacentIndex(favourites.size, -1, next = true)
        assertEquals(0, firstTarget)
        val secondCurrent = FmFavouriteModel.resolveCurrentIndex(
            favourites = favourites,
            activeId = favourites[firstTarget].id,
            frequency = 88.8f,
            stationId = "",
            pi = 0,
            rdsConfirmed = false,
        )
        assertEquals(1, FmFavouriteModel.adjacentIndex(favourites.size, secondCurrent, next = true))
    }

    @Test fun `forward and backward navigation wrap`() {
        assertEquals(1, FmFavouriteModel.adjacentIndex(3, 0, next = true))
        assertEquals(0, FmFavouriteModel.adjacentIndex(3, 2, next = true))
        assertEquals(2, FmFavouriteModel.adjacentIndex(3, 0, next = false))
    }

    @Test fun `unknown stations are unique by exact frequency`() {
        val unknown = listOf(FmFavouriteRef("a", "", 93.1f), FmFavouriteRef("b", "", 94.2f))
        assertEquals(0, FmFavouriteModel.existingIndexForUpsert(unknown, 93.1f, ""))
        assertEquals(1, FmFavouriteModel.existingIndexForUpsert(unknown, 94.2f, ""))
        assertEquals(-1, FmFavouriteModel.existingIndexForUpsert(unknown, 107.8f, ""))
    }

    @Test fun `scan grouping requires the same nonblank RTR station id`() {
        assertTrue(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe1"))
        assertFalse(FmFavouriteModel.shouldGroupScan("station:oe1", "station:oe3"))
        assertFalse(FmFavouriteModel.shouldGroupScan("", ""))
    }

    @Test fun `legacy ids are deterministic but records stay distinct`() {
        val first = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val again = FmFavouriteModel.legacyId(0, 87.6f, "Ö1", "station:oe1")
        val second = FmFavouriteModel.legacyId(1, 87.6f, "Ö1", "station:oe1")
        assertEquals(first, again)
        assertNotEquals(first, second)
    }
}
''', encoding="utf-8")

build = ROOT / "app/build.gradle.kts"
replace_once(
    build,
    '        versionCode = 1370038\n        versionName = "13.7.29"',
    '        versionCode = 1370040\n        versionName = "13.7.31"',
    "version bump",
)

print("Applied Dudu7 13.7.31 FM steering favourite navigation fix")
