package com.metrolist.music.variant

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class TvDpadNavigationTest {
    @Test
    fun googleTvEnablesOnlyWithTelevisionModeAndLeanback() {
        assertTrue(TvDpadNavigation.shouldEnable(true, true, false, false))
        assertFalse(TvDpadNavigation.shouldEnable(false, true, false, false))
        assertFalse(TvDpadNavigation.shouldEnable(true, false, false, false))
    }

    @Test
    fun fyTHeadunitNeverEnablesTvFocusEvenIfItReportsTvFeatures() {
        assertFalse(TvDpadNavigation.shouldEnable(true, true, false, true))
        assertFalse(TvDpadNavigation.shouldEnable(true, true, true, false))
        assertFalse(TvDpadNavigation.shouldEnable(false, false, false, true))
    }
}
