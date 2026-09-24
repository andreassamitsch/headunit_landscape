package com.metrolist.music.radio

/** Preserve the visible drag order while replacing stale station data. */
internal fun mergeSavedStationUpdates(
    ordered: List<RadioStation>,
    saved: List<RadioStation>,
): List<RadioStation> {
    val byId = saved.associateBy { it.uuid }
    val retainedOrder = ordered.mapNotNull { byId[it.uuid] }
    val retainedIds = retainedOrder.asSequence().map { it.uuid }.toHashSet()
    return retainedOrder + saved.filterNot { it.uuid in retainedIds }
}

/** Replace the selected station with a freshly resolved version in-place. */
internal fun replaceFavoriteStation(
    ordered: List<RadioStation>,
    selected: RadioStation,
): List<RadioStation> {
    val replaced = ordered.map { if (it.uuid == selected.uuid) selected else it }
    return if (replaced.any { it.uuid == selected.uuid }) replaced else replaced + selected
}

/** Return the adjacent saved station without handing the full list to ExoPlayer. */
internal fun radioFavoriteNeighbor(
    ordered: List<RadioStation>,
    currentMediaId: String?,
    direction: Int,
): RadioStation? {
    if (direction != -1 && direction != 1) return null
    val currentIndex = ordered.indexOfFirst { it.mediaId == currentMediaId }
    if (currentIndex < 0) return null
    return ordered.getOrNull(currentIndex + direction)
}
