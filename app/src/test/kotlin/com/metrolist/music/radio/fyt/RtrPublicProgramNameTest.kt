package com.metrolist.music.radio.fyt

import org.junit.Assert.assertEquals
import org.junit.Test

class RtrPublicProgramNameTest {
    @Test
    fun `administrative ORF Oe2 labels become public programme names`() {
        assertEquals("Radio Steiermark", RtrPublicProgramName.resolve("Ö2 Steiermark"))
        assertEquals("Radio Steiermark", RtrPublicProgramName.resolve("ORF Steiermark Ö2"))
        assertEquals("Radio Kärnten", RtrPublicProgramName.resolve("Ö2 Kärnten"))
    }

    @Test
    fun `normal public names remain unchanged`() {
        assertEquals("Radio Steiermark", RtrPublicProgramName.resolve("Radio Steiermark"))
        assertEquals("Antenne Steiermark", RtrPublicProgramName.resolve("Antenne Steiermark"))
    }
}
