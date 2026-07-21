package com.metrolist.music.variant

import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.painterResource
import com.metrolist.music.LocalNavController
import com.metrolist.music.R

@Composable
fun VehicleQueueActions() {
    val navController = LocalNavController.current
    IconButton(onClick = { navController.navigate("vehicle_settings") }) {
        Icon(
            painter = painterResource(R.drawable.settings),
            contentDescription = "Dudu7 settings",
        )
    }
}
