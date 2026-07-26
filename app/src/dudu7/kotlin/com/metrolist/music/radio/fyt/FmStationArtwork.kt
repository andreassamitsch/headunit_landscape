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
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.metrolist.music.R
import com.metrolist.music.radio.RadioDnsLogoResolver
import com.metrolist.music.radio.RadioStation
import com.metrolist.music.radio.RadioStationLogoCache
import com.metrolist.music.radio.RadioStationLogoResolver
import com.metrolist.music.radio.RadioStationLogoSearch
import com.metrolist.music.radio.RadioStationStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.roundToInt

/** Shared FM logo resolver: RadioDNS first, then fixed WebRadio artwork and multi-source search. */
object FmStationLogoResolver {
    private const val PREFS = "dudu7_fm_station_logos_v2"
    private const val CACHE_PREFIX = "logo_"
    private val unresolvedThisSession = ConcurrentHashMap.newKeySet<String>()

    fun cachedLogo(context: Context, stationName: String, frequency: Float, pi: Int = 0): String? =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(CACHE_PREFIX + cacheKey(stationName, frequency, pi), null)

    suspend fun resolve(
        context: Context,
        stationName: String,
        frequency: Float,
        pi: Int = 0,
    ): String? =
        withContext(Dispatchers.IO) {
            val appContext = context.applicationContext
            val key = cacheKey(stationName, frequency, pi)
            cachedLogo(appContext, stationName, frequency, pi)?.let { return@withContext it }
            if (!isUsefulStationName(stationName) || !unresolvedThisSession.add(key)) return@withContext null

            if (pi > 0) {
                RadioDnsLogoResolver.resolveFm(appContext, frequency, pi).forEach { candidate ->
                    cacheAndPersist(appContext, key, candidate.url)?.let { return@withContext it }
                }
            }

            val localStations = RadioStationStore.get(appContext).stations.value
            val localMatch = bestMatch(stationName, localStations)
            val fixedLocal = localMatch?.let { station ->
                when {
                    station.manualFavicon && station.favicon.isNotBlank() -> station.favicon
                    else -> RadioStationLogoResolver.resolve(station) ?: station.favicon
                }
            }
            if (!fixedLocal.isNullOrBlank()) {
                cacheAndPersist(appContext, key, fixedLocal)?.let { return@withContext it }
            }

            RadioStationLogoSearch.search(stationName, localMatch).getOrDefault(emptyList()).forEach { candidate ->
                cacheAndPersist(appContext, key, candidate.url)?.let { return@withContext it }
            }
            null
        }

    fun invalidate(context: Context, stationName: String, frequency: Float, pi: Int = 0) {
        val key = cacheKey(stationName, frequency, pi)
        unresolvedThisSession.remove(key)
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().remove(CACHE_PREFIX + key).apply()
    }

    private suspend fun cacheAndPersist(context: Context, key: String, source: String): String? {
        val stable = RadioStationLogoCache.cache(context, "fm_$key", source) ?: return null
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(CACHE_PREFIX + key, stable).apply()
        return stable
    }

    private fun bestMatch(requestedName: String, stations: List<RadioStation>): RadioStation? =
        stations.asSequence()
            .map { station -> station to matchScore(requestedName, station) }
            .filter { (_, score) -> score >= 70 }
            .maxByOrNull { (_, score) -> score }
            ?.first

    private fun matchScore(requestedName: String, station: RadioStation): Int {
        val requested = normalize(requestedName)
        val candidate = normalize(station.name)
        if (requested.isBlank() || candidate.isBlank()) return 0
        var score =
            when {
                requested == candidate -> 100
                candidate.startsWith(requested) || requested.startsWith(candidate) -> 92
                candidate.contains(requested) || requested.contains(candidate) -> 84
                else -> {
                    val left = requested.split(' ').filter { it.length >= 2 }.toSet()
                    val right = candidate.split(' ').filter { it.length >= 2 }.toSet()
                    if (left.isEmpty() || right.isEmpty()) 0 else left.intersect(right).size * 100 / maxOf(left.size, right.size)
                }
            }
        if (station.country.equals("Austria", true) || station.country.equals("Österreich", true)) score += 5
        if (station.manualFavicon) score += 4
        return score
    }

    private fun isUsefulStationName(value: String): Boolean {
        val normalized = normalize(value)
        if (normalized.isBlank() || normalized.matches(Regex("fm \\d{2,3} \\d"))) return false
        return normalized !in setOf("fm", "radio", "antennenempfang", "physischer antennenempfang")
    }

    private fun cacheKey(stationName: String, frequency: Float, pi: Int): String {
        val identity = if (pi > 0) "pi_${(pi and 0xffff).toString(16).padStart(4, '0')}" else normalize(stationName).ifBlank { "unknown" }
        return "${identity}_${(frequency * 100f).roundToInt()}"
    }

    private fun normalize(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .lowercase(Locale.ROOT)
            .replace("&", " and ")
            .replace(Regex("[^a-z0-9]+"), " ")
            .trim()
}

@Composable
fun FmStationArtwork(
    stationName: String,
    frequency: Float,
    pi: Int = 0,
    size: Dp,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val artworkKey = remember(stationName, frequency, pi) { "${stationName.trim()}-${(frequency * 100f).roundToInt()}-$pi" }
    var artworkUrl by remember(artworkKey) { mutableStateOf(FmStationLogoResolver.cachedLogo(context, stationName, frequency, pi)) }
    LaunchedEffect(artworkKey) {
        if (artworkUrl.isNullOrBlank()) artworkUrl = FmStationLogoResolver.resolve(context, stationName, frequency, pi)
    }
    val shape = RoundedCornerShape((size.value / 7f).dp)
    if (!artworkUrl.isNullOrBlank()) {
        AsyncImage(
            model = artworkUrl,
            contentDescription = "Senderlogo $stationName",
            contentScale = ContentScale.Fit,
            error = painterResource(R.drawable.radio),
            fallback = painterResource(R.drawable.radio),
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        )
    } else {
        Box(
            contentAlignment = Alignment.Center,
            modifier = modifier.size(size).clip(shape).background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Icon(
                painter = painterResource(R.drawable.radio),
                contentDescription = "FM-Radio",
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size((size.value * 0.62f).dp),
            )
        }
    }
}
