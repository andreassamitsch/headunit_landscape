package com.metrolist.music.variant

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavController

@Composable
fun VehicleSettingsScreen(navController: NavController) {
    LaunchedEffect(Unit) { navController.popBackStack() }
}
