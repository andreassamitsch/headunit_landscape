package com.metrolist.music.radio

fun orderWebRadioFavourites(
    selected: RadioStation,
    savedStations: List<RadioStation>,
): List<RadioStation> =
    buildList {
        add(selected)
        savedStations
            .asSequence()
            .filterNot { it.uuid == selected.uuid }
            .distinctBy { it.uuid }
            .forEach(::add)
    }
