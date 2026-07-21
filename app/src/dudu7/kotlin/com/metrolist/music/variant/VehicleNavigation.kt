package com.metrolist.music.variant

import androidx.navigation.NavController
import androidx.navigation.NavGraphBuilder
import androidx.navigation.compose.composable

fun NavGraphBuilder.vehicleNavigation(navController: NavController) {
    composable("vehicle_settings") {
        VehicleSettingsScreen(navController)
    }
}
