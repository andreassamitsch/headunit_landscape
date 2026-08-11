package com.metrolist.music.ui.player

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class Dudu7PlayerLayoutSelectionTest {
    @Test
    fun dudu7AlwaysUsesVehiclePlayerInPortraitAndLandscape() {
        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = true, isLandscape = false))
        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = true, isLandscape = true))
    }

    @Test
    fun standardVariantKeepsExistingOrientationSelection() {
        assertFalse(shouldUseVehiclePlayerLayout(isDudu7 = false, isLandscape = false))
        assertTrue(shouldUseVehiclePlayerLayout(isDudu7 = false, isLandscape = true))
    }
}
