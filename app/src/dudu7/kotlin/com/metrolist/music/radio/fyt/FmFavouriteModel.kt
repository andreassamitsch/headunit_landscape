package com.metrolist.music.radio.fyt

import java.util.UUID
import kotlin.math.abs

data class FmFavouriteRef(
    val id: String,
    val stationId: String,
    val frequency: Float,
    val pi: Int = 0,
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
    ): Int = resolveCurrentIndex(
        favourites = favourites,
        activeId = null,
        frequency = frequency,
        stationId = stationId,
        pi = 0,
        rdsConfirmed = false,
    )

    fun resolveCurrentIndex(
        favourites: List<FmFavouriteRef>,
        activeId: String?,
        frequency: Float,
        stationId: String,
        pi: Int,
        rdsConfirmed: Boolean,
    ): Int {
        activeId?.takeIf(String::isNotBlank)?.let { id ->
            favourites.indexOfFirst { it.id == id }.takeIf { it >= 0 }?.let { return it }
        }

        val exact = favourites.indices.filter { abs(favourites[it].frequency - frequency) < 0.05f }
        if (exact.size == 1) return exact.first()

        if (stationId.isNotBlank()) {
            val stationMatches = favourites.indices.filter {
                favourites[it].stationId.isNotBlank() && favourites[it].stationId == stationId
            }
            if (stationMatches.size == 1) return stationMatches.first()
        }

        if (rdsConfirmed && pi > 0) {
            val normalizedPi = pi and 0xffff
            val piMatches = favourites.indices.filter {
                favourites[it].pi > 0 && (favourites[it].pi and 0xffff) == normalizedPi
            }
            if (piMatches.size == 1) return piMatches.first()
        }

        return exact.firstOrNull() ?: -1
    }

    fun adjacentIndex(
        size: Int,
        currentIndex: Int,
        next: Boolean,
    ): Int {
        if (size <= 0) return -1
        return when {
            currentIndex !in 0 until size && next -> 0
            currentIndex !in 0 until size -> size - 1
            next -> (currentIndex + 1) % size
            else -> (currentIndex - 1 + size) % size
        }
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
