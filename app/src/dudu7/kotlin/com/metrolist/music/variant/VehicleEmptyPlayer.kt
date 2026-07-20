package com.metrolist.music.variant

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController

@Composable
fun VehicleEmptyPlayer(navController: NavController) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.fillMaxWidth().padding(24.dp),
    ) {
        Text("Noch keine Wiedergabe", style = MaterialTheme.typography.headlineSmall)
        Button(onClick = { navController.navigate("online_playlist/LM") }) {
            Text("Songs, die ich mag")
        }
        OutlinedButton(onClick = { navController.navigate("search_input") }) {
            Text("Musik suchen")
        }
        OutlinedButton(onClick = { navController.navigate("library") }) {
            Text("Mediathek öffnen")
        }
    }
}
