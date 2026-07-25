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
