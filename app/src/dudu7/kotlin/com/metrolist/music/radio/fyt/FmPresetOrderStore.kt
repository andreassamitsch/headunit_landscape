package com.metrolist.music.radio.fyt

import android.content.Context
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
        val storedIds =
            preferences
                .getString(KEY_ORDER, null)
                .orEmpty()
                .lineSequence()
                .map(String::trim)
                .filter(String::isNotBlank)
                .distinct()
                .toList()
        val legacyKeys =
            preferences
                .getString(LEGACY_KEY_ORDER_V2, null)
                .orEmpty()
                .lineSequence()
                .map(String::trim)
                .filter(String::isNotBlank)
                .distinct()
                .toList()
        val legacyFrequencies =
            preferences
                .getString(LEGACY_KEY_ORDER, null)
                .orEmpty()
                .split(',')
                .mapNotNull(String::toIntOrNull)
                .distinct()

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
        presets.forEach { preset ->
            if (ordered.none { it.id == preset.id }) ordered += preset
        }
        return ordered
    }

    fun persist(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ) {
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ORDER, presets.map(FytPhysicalRadio::stablePresetKey).distinct().joinToString("\n"))
            .remove(LEGACY_KEY_ORDER_V2)
            .remove(LEGACY_KEY_ORDER)
            .apply()
    }

    fun remove(
        context: Context,
        preset: FytPhysicalRadio.Preset,
        remainingPresets: List<FytPhysicalRadio.Preset>,
    ) {
        persist(context, remainingPresets.filterNot { it.id == preset.id })
    }

    private fun frequencyKey(value: Float): Int = (value * 10f).roundToInt()

    fun sameFrequency(
        first: Float,
        second: Float,
    ): Boolean = abs(first - second) < 0.05f
}

fun FytPhysicalRadio.tuneAdjacentFavourite(
    context: Context,
    next: Boolean,
) {
    val snapshot = state.value
    val favourites = FmPresetOrderStore.ordered(context, snapshot.presets)
    if (favourites.isEmpty()) {
        seek(next)
        return
    }

    val activeId = snapshot.currentPreset?.id
    val currentIndex = favourites.indexOfFirst { it.id == activeId }
    val targetIndex =
        when {
            currentIndex < 0 && next -> 0
            currentIndex < 0 -> favourites.lastIndex
            next -> (currentIndex + 1) % favourites.size
            else -> (currentIndex - 1 + favourites.size) % favourites.size
        }
    tunePreset(favourites[targetIndex])
}
