package com.metrolist.music.radio.fyt

import android.content.Context
import kotlin.math.abs
import kotlin.math.roundToInt

/** Keeps the visible FM-favourite order independent from the tuner backend. */
object FmPresetOrderStore {
    private const val PREFS = "dudu7_physical_radio"
    private const val KEY_ORDER = "preset_order"

    fun ordered(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ): List<FytPhysicalRadio.Preset> {
        if (presets.isEmpty()) return emptyList()
        val byKey = presets.associateBy { frequencyKey(it.frequency) }
        val storedKeys =
            context.applicationContext
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_ORDER, null)
                .orEmpty()
                .split(',')
                .mapNotNull(String::toIntOrNull)
                .distinct()
        val ordered = storedKeys.mapNotNull(byKey::get)
        val missing = presets.filterNot { preset -> ordered.any { sameFrequency(it.frequency, preset.frequency) } }
        return ordered + missing
    }

    fun persist(
        context: Context,
        presets: List<FytPhysicalRadio.Preset>,
    ) {
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ORDER, presets.joinToString(",") { frequencyKey(it.frequency).toString() })
            .apply()
    }

    fun remove(
        context: Context,
        frequency: Float,
        remainingPresets: List<FytPhysicalRadio.Preset>,
    ) {
        persist(context, remainingPresets.filterNot { sameFrequency(it.frequency, frequency) })
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

    val currentIndex = favourites.indexOfFirst { FmPresetOrderStore.sameFrequency(it.frequency, snapshot.frequency) }
    val targetIndex =
        when {
            currentIndex < 0 && next -> 0
            currentIndex < 0 -> favourites.lastIndex
            next -> (currentIndex + 1) % favourites.size
            else -> (currentIndex - 1 + favourites.size) % favourites.size
        }
    tune(favourites[targetIndex].frequency)
}
