package com.metrolist.music.variant

import org.junit.Assert.assertEquals
import org.junit.Test

class VehicleLastTabStoreTest {
    private val routes = setOf("vehicle_queue", "vehicle_webradio", "vehicle_physical_radio", "search")

    @Test
    fun restoresValidMainRoute() {
        assertEquals("vehicle_physical_radio", VehicleLastTabStore.normalize("vehicle_physical_radio", routes, "vehicle_queue"))
    }

    @Test
    fun rejectsDetailAndUnknownRoutes() {
        assertEquals("vehicle_queue", VehicleLastTabStore.normalize("artist/abc", routes, "vehicle_queue"))
        assertEquals("vehicle_queue", VehicleLastTabStore.normalize("removed_tab", routes, "vehicle_queue"))
    }
}
