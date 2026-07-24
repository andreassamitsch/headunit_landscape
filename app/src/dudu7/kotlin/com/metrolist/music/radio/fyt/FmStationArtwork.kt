package com.metrolist.music.radio.fyt

import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import coil3.compose.AsyncImage
import com.metrolist.music.R
import com.metrolist.music.radio.RadioBrowserClient
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationLogoResolver
import com.metrolist.music.radio.RadioStationStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.roundToInt

/**
 * Reuses the WebRadio station catalogue and logo discovery for physical FM.
 *
 * Resolution order:
 * 1. stable local FM-logo cache
 * 2. matching saved WebRadio station (including manually selected logos)
 * 3. Radio Browser station search followed by the existing logo resolver
 */
object FmStationLogoResolver {
    private const val PREFS = "dudu7_fm_station_logos"
    private const val CACHE_PREFIX = "logo_"
    private const val NO_RESULT = "__none__"

    private val unresolvedThisSession = ConcurrentHashMap.newKeySet<String>()

    fun cachedLogo(
        context: Context,
        stationName: String,
        frequency: Float,
    ): String? {
        val value =
            context.applicationContext
                .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(CACHE_PREFIX + cacheKey(stationName, frequency), null)
        return value?.takeUnless { it == NO_RESULT }
    }

    suspend fun resolve(
        context: Context,
        stationName: String,
        frequency: Float,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(stationName, frequency)
            cachedLogo(appContext, stationName, frequency)?.let { return@withContext it }
            if (!isUsefulStationName(stationName) || !unresolvedThisSession.add(key)) return@withContext null

            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestMatch(stationName, localStations)
            val localLogo = localMatch?.let { resolveStationLogo(it) }
            if (!localLogo.isNullOrBlank()) {
                persist(appContext, key, localLogo)
                return@withContext localLogo
            }

            val remoteStations = RadioBrowserClient.search(stationName).getOrNull().orEmpty()
            val remoteMatch = bestMatch(stationName, remoteStations)
            val remoteLogo = remoteMatch?.let { resolveStationLogo(it) }
            if (!remoteLogo.isNullOrBlank()) {
                persist(appContext, key, remoteLogo)
                return@withContext remoteLogo
            }

            persist(appContext, key, NO_RESULT)
            null
        }

    fun invalidate(
        context: Context,
        stationName: String,
        frequency: Float,
    ) {
        val key = cacheKey(stationName, frequency)
        unresolvedThisSession.remove(key)
        context.applicationContext
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(CACHE_PREFIX + key)
            .apply()
    }

    private suspend fun resolveStationLogo(station: RadioStation): String? {
        if (station.manualFavicon && station.favicon.isHttpUrl()) return station.favicon
        return RadioStationLogoResolver.resolve(station)
            ?: station.favicon.takeIf(String::isHttpUrl)
    }

    private fun bestMatch(
        requestedName: String,
        stations: List<RadioStation>,
    ): RadioStation? =
        stations
            .asSequence()
            .map { station -> station to matchScore(requestedName, station) }
            .filter { (_, score) -> score >= 70 }
            .maxByOrNull { (_, score) -> score }
            ?.first

    private fun matchScore(
        requestedName: String,
        station: RadioStation,
    ): Int {
        val requested = normalize(requestedName)
        val candidate = normalize(station.name)
        if (requested.isBlank() || candidate.isBlank()) return 0

        var score =
            when {
                requested == candidate -> 100
                candidate.startsWith(requested) || requested.startsWith(candidate) -> 92
                candidate.contains(requested) || requested.contains(candidate) -> 84
                else -> {
                    val requestedTokens = requested.split(' ').filter { it.length >= 2 }.toSet()
                    val candidateTokens = candidate.split(' ').filter { it.length >= 2 }.toSet()
                    if (requestedTokens.isEmpty() || candidateTokens.isEmpty()) {
                        0
                    } else {
                        val overlap = requestedTokens.intersect(candidateTokens).size
                        ((overlap * 100.0) / requestedTokens.size.coerceAtLeast(candidateTokens.size)).roundToInt()
                    }
                }
            }

        if (station.country.equals("Austria", ignoreCase = true) || station.country.equals("Österreich", ignoreCase = true)) {
            score += 5
        }
        if (station.manualFavicon) score += 4
        if (station.favicon.isHttpUrl()) score += 2
        return score
    }

    private fun isUsefulStationName(value: String): Boolean {
        val normalized = normalize(value)
        if (normalized.isBlank()) return false
        if (normalized.matches(Regex("fm \\d{2,3} \\d"))) return false
        return normalized !in setOf("fm", "radio", "antennenempfang", "physischer antennenempfang")
    }

    private fun cacheKey(
        stationName: String,
        frequency: Float,
    ): String {
        val normalizedName = normalize(stationName).ifBlank { "unknown" }
        val normalizedFrequency = (frequency * 10f).roundToInt()
        return "${normalizedName}_$normalizedFrequency"
    }

    private fun normalize(value: String): String =
        Normalizer
            .normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace("&", " and ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()

    private fun persist(
        context: Context,
        key: String,
        value: String,
    ) {
        context
            .getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(CACHE_PREFIX + key, value)
            .apply()
    }

    private fun String.isHttpUrl(): Boolean =
        startsWith("https://", ignoreCase = true) || startsWith("http://", ignoreCase = true)
}

@Composable
fun FmStationArtwork(
    stationName: String,
    frequency: Float,
    size: Dp,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val artworkKey = remember(stationName, frequency) { "${stationName.trim()}-${(frequency * 10f).roundToInt()}" }
    var artworkUrl by remember(artworkKey) {
        mutableStateOf(FmStationLogoResolver.cachedLogo(context, stationName, frequency))
    }

    LaunchedEffect(artworkKey) {
        if (artworkUrl.isNullOrBlank()) {
            artworkUrl = FmStationLogoResolver.resolve(context, stationName, frequency)
        }
    }

    val shape = RoundedCornerShape(size / 7)
    if (!artworkUrl.isNullOrBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo $stationName",
            contentScale = ContentScale.Fit,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier =
                modifier
                    .size(size)
                    .clip(shape)
                    .background(MaterialTheme.colorScheme.surfaceVariant),
        )
    } else {
        Box(
            contentAlignment = Alignment.Center,
            modifier =
                modifier
                    .size(size)
                    .clip(shape)
                    .background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(size * 0.62f),
            )
        }
    }
}
