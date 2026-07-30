package com.metrolist.music.variant

import android.content.Context

/** Persists only stable top-level right-pane routes, never detail routes. */
internal object VehicleLastTabStore {
    private const val PREFS = "dudu7_vehicle_layout"
    private const val KEY_LAST_ROUTE = "last_right_pane_route"

    internal fun normalize(savedRoute: String?, allowedRoutes: Set<String>, fallback: String): String =
        savedRoute?.takeIf { it in allowedRoutes } ?: fallback

    fun read(context: Context, allowedRoutes: Set<String>, fallback: String): String =
        normalize(
            context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_LAST_ROUTE, null),
            allowedRoutes,
            fallback,
        )

    fun persist(context: Context, route: String, allowedRoutes: Set<String>) {
        if (route !in allowedRoutes) return
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_LAST_ROUTE, route)
            .apply()
    }
}
