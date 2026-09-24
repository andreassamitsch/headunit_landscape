package com.metrolist.music.variant

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp

class VehicleHazeState internal constructor()

@Composable
fun rememberVehicleHazeState(): VehicleHazeState = remember { VehicleHazeState() }

fun Modifier.vehicleHazeSource(state: VehicleHazeState): Modifier = this

fun Modifier.vehicleHazeEffect(
    state: VehicleHazeState,
    enabled: Boolean,
    blurRadius: Dp,
): Modifier = this
