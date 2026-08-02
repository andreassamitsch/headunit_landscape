package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FmReceptionPathStoreTest {
    @Test
    fun `region key is coarse and rejects missing coordinates`() {
        assertEquals("468:151", FmReceptionRegion.key(46.84, 15.12))
        assertEquals("468:151", FmReceptionRegion.key(46.89, 15.19))
        assertNull(FmReceptionRegion.key(null, 15.1))
        assertNull(FmReceptionRegion.key(91.0, 15.1))
    }

    @Test
    fun `planner only returns local positive coverage candidates and limits tuning`() {
        val history =
            listOf(
                path("fav-a", 99.1f, "468:151", 0xA101, "rtr:a", 20L),
                path("fav-a", 95.7f, "467:150", 0xA101, "rtr:a", 30L),
                path("fav-a", 101.1f, "468:151", 0xB202, "rtr:a", 40L),
            )
        val result =
            FmLocalAfPlanner.plan(
                favouriteId = "fav-a",
                currentFrequency = 94.2f,
                expectedPi = 0xA101,
                stationId = "rtr:a",
                regionKey = "468:151",
                history = history,
                rtrCandidates =
                    listOf(
                        FmRtrLocalCandidate(99.1f, 9, "RTR"),
                        FmRtrLocalCandidate(102.5f, 8, "RTR"),
                        FmRtrLocalCandidate(103.3f, 7, "RTR"),
                        FmRtrLocalCandidate(104.4f, 6, "RTR"),
                        FmRtrLocalCandidate(88.2f, 0, "RTR ohne lokale Abdeckung"),
                    ),
            )

        assertEquals(3, result.size)
        assertEquals(listOf(99.1f, 102.5f, 103.3f), result.map { it.frequency })
        assertTrue(result.first().cachedPath)
        assertTrue(result.none { it.frequency == 88.2f })
        assertTrue(result.none { it.frequency == 95.7f })
        assertTrue(result.none { it.frequency == 101.1f })
    }

    @Test
    fun `planner refuses automatic AF without location PI or station identity`() {
        val rtr = listOf(FmRtrLocalCandidate(99.1f, 9, "RTR"))
        assertTrue(FmLocalAfPlanner.plan("fav", 98.7f, 0xA101, "station", null, emptyList(), rtr).isEmpty())
        assertTrue(FmLocalAfPlanner.plan("fav", 98.7f, 0, "station", "468:151", emptyList(), rtr).isEmpty())
        assertTrue(FmLocalAfPlanner.plan("fav", 98.7f, 0xA101, "", "468:151", emptyList(), rtr).isEmpty())
    }

    @Test
    fun `codec preserves independent favourites sharing one frequency`() {
        val original =
            listOf(
                path("fav-a", 99.7f, "468:151", 0xA101, "rtr:a", 100L),
                path("fav-b", 99.7f, "478:163", 0xB202, "rtr:b", 200L),
            )
        val decoded = FmReceptionPathCodec.decode(FmReceptionPathCodec.encode(original))

        assertEquals(2, decoded.size)
        assertEquals(listOf("fav-a", "fav-b"), decoded.map { it.favouriteId })
        assertEquals(listOf(0xA101, 0xB202), decoded.map { it.pi })
        assertEquals(listOf("468:151", "478:163"), decoded.map { it.regionKey })
    }

    @Test
    fun `AF target is accepted only with fresh identical PI`() {
        assertTrue(FmAlternativeFrequencySelector.compatiblePi(0xA101, 0xA101, false))
        assertFalse(FmAlternativeFrequencySelector.compatiblePi(0xA101, 0xB202, true))
        assertFalse(FmAlternativeFrequencySelector.compatiblePi(0xA101, 0, true))
        assertFalse(FmAlternativeFrequencySelector.compatiblePi(0, 0xA101, true))
    }

    private fun path(
        favouriteId: String,
        frequency: Float,
        region: String,
        pi: Int,
        stationId: String,
        time: Long,
    ) =
        FmReceptionPath(
            favouriteId = favouriteId,
            frequency = frequency,
            regionKey = region,
            pi = pi,
            stationId = stationId,
            confirmedAt = time,
            rssi = 45,
            coverageStrength = 5,
        )
}
