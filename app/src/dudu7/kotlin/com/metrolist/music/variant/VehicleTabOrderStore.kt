package com.metrolist.music.variant

import android.content.Context

/** Persists the user-defined Dudu7 right-pane tab order. */
object VehicleTabOrderStore {
    private const val PREFS = "dudu7_vehicle_tabs"
    private const val KEY_ORDER = "order"

    val defaultOrder: List<String> =
        listOf(
            "QUEUE",
            "LIBRARY",
            "WEBRADIO",
            "PHYSICAL_RADIO",
            "SEARCH",
            "HISTORY",
        )

    fun read(
        context: Context,
        available: Collection<String>,
    ): List<String> {
        val availableSet = available.toSet()
        val stored =
            context
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_ORDER, null)
                .orEmpty()
                .split(',')
                .map(String::trim)
                .filter { it in availableSet }
                .distinct()
        return (stored + defaultOrder + available)
            .filter { it in availableSet }
            .distinct()
    }

    fun persist(
        context: Context,
        order: List<String>,
    ) {
        context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_ORDER, order.distinct().joinToString(","))
            .apply()
    }

    fun reset(context: Context) {
        context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_ORDER)
            .apply()
    }
}
