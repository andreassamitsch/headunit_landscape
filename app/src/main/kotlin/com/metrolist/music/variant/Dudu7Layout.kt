package com.metrolist.music.variant

object Dudu7Layout {
    const val MIN_PLAYER_PANE_WEIGHT = 0.32f
    const val MAX_PLAYER_PANE_WEIGHT = 0.68f

    fun sanitizePlayerPaneWeight(value: Float): Float =
        value.coerceIn(MIN_PLAYER_PANE_WEIGHT, MAX_PLAYER_PANE_WEIGHT)
}
