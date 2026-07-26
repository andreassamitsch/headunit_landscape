package com.metrolist.music.ui.screens

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Test

class ScreensInitializationTest {
    @Test
    fun `main screens are rebuilt after nested singleton initialization`() {
        // Touch a nested object first: this was the order that could poison the old
        // static MainScreens backing field with a null Home.INSTANCE.
        val home = Screens.Home
        val first = Screens.MainScreens
        val second = Screens.MainScreens

        assertEquals("home", home.route)
        assertNotSame(first, second)
        assertEquals(
            listOf("home", "search_input", "listen_together", "library"),
            first.map { it.route },
        )
    }
}
