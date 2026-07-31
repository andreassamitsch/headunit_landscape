package com.metrolist.music.radio

fun orderWebRadioFavourites(
    selected: RadioStation,
    savedStations: List<RadioStation>,
): List<RadioStation> {
    val ordered = savedStations.distinctBy { it.uuid }.toMutableList()
    val selectedIndex = ordered.indexOfFirst { it.uuid == selected.uuid }
    if (selectedIndex >= 0) {
        ordered[selectedIndex] = selected
    } else {
        ordered += selected
    }
    return ordered
}

fun webRadioFavouriteStartIndex(
    selected: RadioStation,
    orderedStations: List<RadioStation>,
): Int = orderedStations.indexOfFirst { it.uuid == selected.uuid }.coerceAtLeast(0)
