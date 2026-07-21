package com.metrolist.music.variant

import androidx.compose.runtime.Composable

@Suppress("UNUSED_PARAMETER")
@Composable
fun rememberVehicleVoiceSearch(
    onSearch: (String) -> Unit,
    fallback: () -> Unit,
): () -> Unit = fallback
