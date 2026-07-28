package com.metrolist.music.ui.screens.radio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.metrolist.music.radio.RadioDnsLogoResolver
import com.metrolist.music.radio.fyt.FmStationLogoResolver
import com.metrolist.music.radio.fyt.FytPhysicalRadio
import kotlinx.coroutines.launch
import java.util.Locale
import kotlin.math.roundToInt

@Composable
internal fun FmRadioDiagnostics(state: FytPhysicalRadio.State) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val revision by FmStationLogoResolver.revisions.collectAsState()
    val info = FmStationLogoResolver.logoInfo(context, state.displayStation, state.frequency, state.pi)
    val piHex = (state.pi and 0xffff).toString(16).padStart(4, '0')
    val ecc = state.ecc.ifBlank { RadioDnsLogoResolver.defaultEcc(context).orEmpty() }.lowercase(Locale.ROOT)
    val gcc = if (state.pi > 0 && ecc.matches(Regex("[0-9a-f]{2}"))) "${piHex.first()}$ecc" else ""
    val frequencyCode = (state.frequency * 100f).roundToInt().toString().padStart(5, '0')
    val lookup = if (gcc.isNotBlank()) "$frequencyCode.$piHex.$gcc.fm.radiodns.org" else "–"
    val bearer = if (gcc.isNotBlank()) "fm:$gcc.$piHex.$frequencyCode" else "–"

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("FM-Diagnose", style = MaterialTheme.typography.titleMedium)
        Text("PS: ${state.ps.ifBlank { "–" }}")
        Text(
            "PI: ${if (state.pi > 0) piHex.uppercase(Locale.ROOT) else "–"}  •  " +
                "ECC: ${state.ecc.ifBlank { "– (Fallback $ecc)" }}  •  GCC: ${gcc.ifBlank { "–" }}",
        )
        Text("RadioDNS: $lookup", style = MaterialTheme.typography.bodySmall)
        Text("Bearer: $bearer", style = MaterialTheme.typography.bodySmall)
        Text(
            "AF: ${if (state.alternativeFrequencies.isEmpty()) "–" else FytPhysicalRadio.formatFrequencies(state.alternativeFrequencies)}",
        )
        Text(
            "RSSI: aktuell ${state.rssi}  •  Mittel ${state.afAverageRssi.takeIf { it > 0 } ?: "–"}  •  " +
                "Schwelle ${state.afSensitivity}  •  schwach ${state.afWeakSamples}/3",
        )
        Text(
            "FYT ro.fyt.fmsens: ${state.firmwareFmSensitivity ?: "–"}",
            style = MaterialTheme.typography.bodySmall,
        )
        Text("Logoquelle: ${info?.sourceLabel ?: "–"}${if (info?.manual == true) " (manuell)" else ""}")
        if (!info?.sourceUrl.isNullOrBlank()) {
            Text("Logo-URL: ${info?.sourceUrl}", style = MaterialTheme.typography.bodySmall, maxLines = 3)
        }
        Button(
            onClick = {
                scope.launch {
                    FmStationLogoResolver.invalidateAuto(context, state.displayStation, state.frequency, state.pi)
                    FmStationLogoResolver.resolve(
                        context,
                        state.displayStation,
                        state.frequency,
                        state.pi,
                        state.ecc,
                        force = true,
                    )
                }
            },
            enabled = state.pi > 0 || state.displayStation.isNotBlank(),
            modifier = Modifier.fillMaxWidth(),
        ) { Text("LOGO-AUTOMATIK NEU LADEN") }
        @Suppress("UNUSED_VARIABLE") val keepRevisionReactive = revision
    }
}
