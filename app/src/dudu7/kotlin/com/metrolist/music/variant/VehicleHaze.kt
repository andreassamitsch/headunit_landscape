package com.metrolist.music.variant

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.ExperimentalHazeApi
import dev.chrisbanes.haze.HazeInputScale
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeTint
import dev.chrisbanes.haze.hazeEffect
import dev.chrisbanes.haze.hazeSource
import dev.chrisbanes.haze.rememberHazeState

class VehicleHazeState internal constructor(internal val delegate: HazeState)

@Composable
fun rememberVehicleHazeState(): VehicleHazeState {
    val delegate = rememberHazeState()
    return remember(delegate) { VehicleHazeState(delegate) }
}

fun Modifier.vehicleHazeSource(state: VehicleHazeState): Modifier =
    hazeSource(state = state.delegate, zIndex = 0f, key = "dudu7-player-background")

@OptIn(ExperimentalHazeApi::class)
fun Modifier.vehicleHazeEffect(
    state: VehicleHazeState,
    enabled: Boolean,
    blurRadius: Dp,
): Modifier {
    if (!enabled || blurRadius <= 0.dp) return this
    return hazeEffect(state = state.delegate) {
        blurEnabled = true
        this.blurRadius = blurRadius
        noiseFactor = 0f
        tints = emptyList()
        backgroundColor = Color.Transparent
        fallbackTint = HazeTint(Color.Transparent)
        inputScale = HazeInputScale.Auto
    }
}
