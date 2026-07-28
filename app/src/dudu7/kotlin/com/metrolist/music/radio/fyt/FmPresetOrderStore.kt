package com.metrolist.music.radio.fyt

import android.content.Context
import kotlin.math.abs
import kotlin.math.roundToInt

/** Keeps FM-favourite order stable while AF changes the currently used frequency. */
object FmPresetOrderStore {
    private const val PREFS = "dudu7_physical_radio"
    private const val KEY_ORDER = "preset_order_v2"
    private const val LEGACY_KEY_ORDER = "preset_order"

    fun ordered(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ): List<FytPhysicalRadio.Preset> {
        if (presets.isEmpty()) return emptyList()
        val preferences = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val storedKeys =
            preferences
                .getString(KEY_ORDER, null)
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
        storedKeys.forEach { key ->
            presets.firstOrNull {
                key in FytPhysicalRadio.presetOrderKeys(it) && ordered.none { existing -> samePreset(existing, it) }
            }?.let(ordered::add)
        }
        legacyFrequencies.forEach { key ->
            presets.firstOrNull {
                frequencyKey(it.frequency) == key && ordered.none { existing -> samePreset(existing, it) }
            }?.let(ordered::add)
        }

        // RDS identity can arrive after a frequency was already stored. During that
        // transition the source list may briefly contain two records for the same PI.
        // Add presets incrementally so duplicate station identities never reach the
        // Compose LazyColumn, where equal stable keys would otherwise crash the app.
        presets.forEach { preset ->
            if (ordered.none { existing -> samePreset(existing, preset) }) {
                ordered += preset
            }
        }
        return ordered
    }

    fun persist(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ) {
        val stableOrder =
            presets
                .map { FytPhysicalRadio.stablePresetKey(it) }
                .distinct()
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ORDER, stableOrder.joinToString("\n"))
            .remove(LEGACY_KEY_ORDER)
            .apply()
    }

    fun remove(
        context: Context,
        preset: FytPhysicalRadio.Preset,
        remainingPresets: List<FytPhysicalRadio.Preset>,
    ) {
        persist(context, remainingPresets.filterNot { samePreset(it, preset) })
    }

    private fun samePreset(
        first: FytPhysicalRadio.Preset,
        second: FytPhysicalRadio.Preset,
    ): Boolean =
        FytPhysicalRadio.stablePresetKey(first) == FytPhysicalRadio.stablePresetKey(second) ||
            FytPhysicalRadio.presetFrequencies(first).any { frequency ->
                FytPhysicalRadio.presetContainsFrequency(second, frequency)
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

    val currentIndex =
        favourites.indexOfFirst {
            FytPhysicalRadio.presetMatches(it, snapshot.frequency, snapshot.pi)
        }
    val targetIndex =
        when {
            currentIndex < 0 && next -> 0
            currentIndex < 0 -> favourites.lastIndex
            next -> (currentIndex + 1) % favourites.size
            else -> (currentIndex - 1 + favourites.size) % favourites.size
        }
    tunePreset(favourites[targetIndex])
}
