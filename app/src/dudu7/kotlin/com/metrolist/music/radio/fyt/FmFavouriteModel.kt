package com.metrolist.music.radio.fyt

import java.util.UUID
import kotlin.math.abs

data class FmFavouriteRef(
    val id: String,
    val stationId: String,
    val frequency: Float,
)

/**
 * Pure rules for FM favourites. A favourite is a stable user item; frequencies are
 * only the last successful reception path and must never become its identity.
 */
object FmFavouriteModel {
    fun selectCurrentIndex(
        favourites: List<FmFavouriteRef>,
        frequency: Float,
        stationId: String,
    ): Int {
        val exact = favourites.indexOfFirst { abs(it.frequency - frequency) < 0.05f }
        if (exact >= 0) return exact
        if (stationId.isBlank()) return -1
        return favourites.indexOfFirst { it.stationId.isNotBlank() && it.stationId == stationId }
    }

    fun existingIndexForUpsert(
        favourites: List<FmFavouriteRef>,
        frequency: Float,
        stationId: String,
    ): Int =
        if (stationId.isNotBlank()) {
            favourites.indexOfFirst { it.stationId == stationId }
        } else {
            favourites.indexOfFirst { it.stationId.isBlank() && abs(it.frequency - frequency) < 0.05f }
        }

    fun shouldGroupScan(firstStationId: String, secondStationId: String): Boolean =
        firstStationId.isNotBlank() && firstStationId == secondStationId

    fun legacyId(
        index: Int,
        frequency: Float,
        name: String,
        stationId: String,
    ): String =
        UUID.nameUUIDFromBytes(
            "metrolist-fm-v3:$index:${"%.1f".format(java.util.Locale.ROOT, frequency)}:$name:$stationId"
                .toByteArray(Charsets.UTF_8),
        ).toString()

    fun newId(): String = UUID.randomUUID().toString()
}
