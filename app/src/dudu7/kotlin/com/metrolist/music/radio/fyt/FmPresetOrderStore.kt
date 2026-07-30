package com.metrolist.music.radio.fyt

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

        val normalizedIds = ordered.map { it.id }.filter(String::isNotBlank).distinct()
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
            .putString(
                KEY_ORDER,
                presets.map(FytPhysicalRadio::stablePresetKey)
                    .filter(String::isNotBlank)
                    .distinct()
                    .joinToString("\n"),
            )
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

    val validIds = favourites.map { it.id }.filter(String::isNotBlank).toSet()
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
