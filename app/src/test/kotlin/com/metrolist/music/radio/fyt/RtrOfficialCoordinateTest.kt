package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Test

class RtrOfficialCoordinateTest {
    @Test
    fun parsesRtrDegreeMinuteSecondCoordinates() {
        assertEquals(15.711944, RtrOfficialProgramIndex.parseCoordinate("015E42 43")!!, 0.000001)
        assertEquals(48.213056, RtrOfficialProgramIndex.parseCoordinate("48N12 47")!!, 0.000001)
    }
}
