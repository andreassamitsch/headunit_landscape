package com.metrolist.music.radio.fyt

import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.SongItem
import com.metrolist.music.ui.utils.resize
import com.metrolist.shazamkit.models.RecognitionResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import timber.log.Timber

/**
 * Resolves usable FM RDS text through the same strict YouTube Music matching
 * rules used for WebRadio. Ambiguous RDS text remains visible but never replaces
 * the sender artwork with an unrelated cover.
 */
object FmNowPlayingResolver {
    data class NowPlaying(
        val key: String = "",
        val stationName: String = "",
        val rawText: String = "",
        val title: String = "",
        val artist: String? = null,
        val resolvedSong: SongItem? = null,
        val coverUrl: String? = null,
        val hasTrackMetadata: Boolean = false,
        val resolving: Boolean = false,
    )

    private const val TAG = "FmNowPlayingResolver"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val cache = mutableMapOf<String, SongItem?>()
    private val _state = MutableStateFlow(NowPlaying())
    val state: StateFlow<NowPlaying> = _state.asStateFlow()
    private var lookupJob: Job? = null

    fun resolve(
        stationName: String,
        rawText: String,
    ) {
        val parsed = parse(stationName, rawText)
        val key =
            "${normalizeTrackText(stationName)}|" +
                "${normalizeTrackText(parsed.first.orEmpty())}|${normalizeTrackText(parsed.second)}"
        if (_state.value.key == key) return

        lookupJob?.cancel()
        val artist = parsed.first
        val title = parsed.second
        val clear = isClearTrackMetadata(artist, title, stationName)
        _state.value =
            NowPlaying(
                key = key,
                stationName = stationName,
                rawText = rawText.trim(),
                title = title,
                artist = artist,
                hasTrackMetadata = clear,
                resolving = clear,
            )
        if (!clear) return

        val lookupKey = "${normalizeTrackText(artist.orEmpty())}|${normalizeTrackText(title)}"
        if (cache.containsKey(lookupKey)) {
            applyResolved(key, cache[lookupKey])
            return
        }

        lookupJob =
            scope.launch {
                val song =
                    runCatching {
                        YouTube
                            .search("$artist - $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { candidate -> isStrongMatch(candidate, artist.orEmpty(), title) }
                    }.onFailure {
                        Timber.tag(TAG).w(it, "FM title lookup failed for %s - %s", artist, title)
                    }.getOrNull()
                cache[lookupKey] = song
                applyResolved(key, song)
            }
    }

    /** Apply a Shazam-compatible audio fingerprint result to physical FM. */
    fun applyRecognized(
        stationName: String,
        result: RecognitionResult,
    ) {
        lookupJob?.cancel()
        val artist = result.artist.trim()
        val title = result.title.trim()
        if (artist.isBlank() || title.isBlank()) return
        val preferredCover = result.coverArtHqUrl ?: result.coverArtUrl
        val key =
            "fingerprint|${normalizeTrackText(stationName)}|" +
                "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        _state.value =
            NowPlaying(
                key = key,
                stationName = stationName,
                rawText = "$artist - $title",
                title = title,
                artist = artist,
                coverUrl = preferredCover,
                hasTrackMetadata = true,
                resolving = true,
            )

        val lookupKey = "${normalizeTrackText(artist)}|${normalizeTrackText(title)}"
        if (cache.containsKey(lookupKey)) {
            applyResolved(key, cache[lookupKey], preferredCover)
            return
        }
        lookupJob =
            scope.launch {
                val song =
                    runCatching {
                        YouTube
                            .search("$artist - $title", YouTube.SearchFilter.FILTER_SONG)
                            .getOrNull()
                            ?.items
                            ?.filterIsInstance<SongItem>()
                            ?.firstOrNull { candidate -> isStrongMatch(candidate, artist, title) }
                    }.onFailure {
                        Timber.tag(TAG).w(it, "FM fingerprint YTM lookup failed for %s - %s", artist, title)
                    }.getOrNull()
                cache[lookupKey] = song
                applyResolved(key, song, preferredCover)
            }
    }

    fun clear() {
        lookupJob?.cancel()
        lookupJob = null
        _state.value = NowPlaying()
    }

    private fun applyResolved(
        key: String,
        song: SongItem?,
        preferredCover: String? = null,
    ) {
        val current = _state.value
        if (current.key != key) return
        _state.value =
            if (song != null) {
                current.copy(
                    title = song.title,
                    artist = song.artists.joinToString(", ") { it.name }.ifBlank { current.artist },
                    resolvedSong = song,
                    coverUrl = preferredCover ?: song.thumbnail.resize(1200, 1200),
                    resolving = false,
                )
            } else {
                current.copy(
                    coverUrl = preferredCover ?: current.coverUrl,
                    resolving = false,
                )
            }
    }

    private fun parse(
        stationName: String,
        raw: String,
    ): Pair<String?, String> {
        val cleaned =
            raw
                .substringBefore(" [")
                .trim()
                .removeStationPrefix(stationName)
                .trim()
        if (cleaned.isBlank()) return null to ""
        val separator = listOf(" - ", " – ", " — ", " | ").firstOrNull { it in cleaned }
        if (separator == null) return null to cleaned
        val artist = cleaned.substringBefore(separator).trim().takeIf { it.isNotBlank() }
        val title = cleaned.substringAfter(separator).trim().ifBlank { cleaned }
        return artist to title
    }

    private fun String.removeStationPrefix(stationName: String): String {
        val prefixCandidates =
            listOf(
                "$stationName:",
                "$stationName -",
                "$stationName |",
            )
        val prefix = prefixCandidates.firstOrNull { startsWith(it, ignoreCase = true) }
        return if (prefix == null) this else drop(prefix.length)
    }

    private fun isClearTrackMetadata(
        artist: String?,
        title: String,
        stationName: String,
    ): Boolean {
        if (artist.isNullOrBlank() || title.isBlank()) return false
        val normalizedArtist = normalizeTrackText(artist)
        val normalizedTitle = normalizeTrackText(title)
        val normalizedStation = normalizeTrackText(stationName)
        if (normalizedArtist.length < 2 || normalizedTitle.length < 2) return false
        if (normalizedArtist == normalizedStation || normalizedTitle == normalizedStation) return false
        if ("http" in normalizedArtist || "http" in normalizedTitle || "www" in normalizedArtist || "www" in normalizedTitle) {
            return false
        }
        val generic =
            setOf(
                "radio",
                "fm",
                "live",
                "stream",
                "unknown",
                "unbekannt",
                "station identification",
                "jingle",
                "promo",
                "advertisement",
                "commercial",
                "werbung",
                "news",
                "nachrichten",
                "verkehr",
                "wetter",
            )
        return normalizedArtist !in generic && normalizedTitle !in generic
    }

    private fun normalizeTrackText(value: String): String =
        value
            .lowercase()
            .replace(
                Regex("""[\(\[][^\(\[]*(official|music video|video|audio|lyrics?|remaster(?:ed)?|live)[^\)\]]*[\)\]]"""),
                " ",
            ).replace(Regex("""\b(feat|ft)\.?\b.*"""), " ")
            .replace(Regex("""[^\p{L}\p{N}]+"""), " ")
            .trim()
            .replace(Regex("""\s+"""), " ")

    private fun tokenCoverage(
        expected: String,
        actual: String,
    ): Double {
        if (expected.isBlank() || actual.isBlank()) return 0.0
        if (actual.contains(expected) || expected.contains(actual)) return 1.0
        val expectedTokens = expected.split(' ').filter { it.length > 1 }.toSet()
        val actualTokens = actual.split(' ').filter { it.length > 1 }.toSet()
        if (expectedTokens.isEmpty()) return 0.0
        return expectedTokens.intersect(actualTokens).size.toDouble() / expectedTokens.size
    }

    private fun isStrongMatch(
        song: SongItem,
        artist: String,
        title: String,
    ): Boolean {
        val expectedTitle = normalizeTrackText(title)
        val actualTitle = normalizeTrackText(song.title)
        val expectedArtist = normalizeTrackText(artist)
        val actualArtist = normalizeTrackText(song.artists.joinToString(" ") { it.name })
        return tokenCoverage(expectedTitle, actualTitle) >= 0.80 &&
            tokenCoverage(expectedArtist, actualArtist) >= 0.70
    }
}
