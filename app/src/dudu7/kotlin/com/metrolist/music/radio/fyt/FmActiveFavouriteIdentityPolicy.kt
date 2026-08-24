package com.metrolist.music.radio.fyt

/**
 * Protects an explicitly selected FM favourite from an ambiguous RTR frequency match.
 * A frequency is an RF path, not a station identity. While a favourite is active, an RTR result
 * for another program may replace it only when fresh RDS evidence also contradicts the stored
 * favourite identity.
 */
object FmActiveFavouriteIdentityPolicy {
    fun allowRtrOverride(
        activeFavourite: Boolean,
        storedStationId: String,
        storedPi: Int,
        currentPi: Int,
        rdsFresh: Boolean,
        rtrStableId: String,
    ): Boolean {
        if (!activeFavourite) return true
        if (rtrStableId.isBlank()) return false
        if (storedStationId.isNotBlank() && storedStationId == rtrStableId) return true
        if (!rdsFresh || currentPi <= 0) return false

        // If the stored favourite already has a PI and the freshly received PI still matches it,
        // an RTR result for another stable station is contradictory and must not win.
        if (storedStationId.isNotBlank() && storedPi > 0 && samePi(storedPi, currentPi)) return false

        // Fresh RDS plus a resolver result is strong enough to recover from an outdated favourite
        // association (for example after a broadcaster changes its technical identity).
        return true
    }

    private fun samePi(first: Int, second: Int): Boolean =
        first > 0 && second > 0 && (first and 0xffff) == (second and 0xffff)
}
