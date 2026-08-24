package com.metrolist.music.radio.fyt

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class FmActiveFavouriteIdentityPolicyTest {
    @Test
    fun `ambiguous RTR result cannot replace active favourite without fresh RDS`() {
        assertFalse(
            FmActiveFavouriteIdentityPolicy.allowRtrOverride(
                activeFavourite = true,
                storedStationId = "rtr:oe24",
                storedPi = 0xA123,
                currentPi = 0,
                rdsFresh = false,
                rtrStableId = "rtr:oe3",
            ),
        )
    }

    @Test
    fun `matching favourite station id may use RTR name immediately`() {
        assertTrue(
            FmActiveFavouriteIdentityPolicy.allowRtrOverride(
                activeFavourite = true,
                storedStationId = "rtr:oe24",
                storedPi = 0,
                currentPi = 0,
                rdsFresh = false,
                rtrStableId = "rtr:oe24",
            ),
        )
    }

    @Test
    fun `fresh PI matching favourite blocks conflicting RTR result`() {
        assertFalse(
            FmActiveFavouriteIdentityPolicy.allowRtrOverride(
                activeFavourite = true,
                storedStationId = "rtr:oe24",
                storedPi = 0xA123,
                currentPi = 0xA123,
                rdsFresh = true,
                rtrStableId = "rtr:oe3",
            ),
        )
    }

    @Test
    fun `fresh contradictory PI may recover outdated favourite association`() {
        assertTrue(
            FmActiveFavouriteIdentityPolicy.allowRtrOverride(
                activeFavourite = true,
                storedStationId = "rtr:old",
                storedPi = 0xA123,
                currentPi = 0xB456,
                rdsFresh = true,
                rtrStableId = "rtr:new",
            ),
        )
    }

    @Test
    fun `non favourite tuning keeps normal RTR behavior`() {
        assertTrue(
            FmActiveFavouriteIdentityPolicy.allowRtrOverride(
                activeFavourite = false,
                storedStationId = "",
                storedPi = 0,
                currentPi = 0,
                rdsFresh = false,
                rtrStableId = "rtr:any",
            ),
        )
    }
}
