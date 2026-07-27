package com.metrolist.music.radio

import java.util.Locale

internal fun parseRadioStreamTitle(raw: String): Pair<String?, String> {
    val cleaned = raw.substringBefore(" [").trim()
    val separator = listOf(" - ", " – ", " — ", " | ").firstOrNull { it in cleaned }
    if (separator == null) return null to cleaned
    val artist = cleaned.substringBefore(separator).trim().takeIf { it.isNotBlank() }
    val title = cleaned.substringAfter(separator).trim().ifBlank { cleaned }
    return artist to title
}

internal fun isClearRadioTrackMetadata(
    artist: String?,
    title: String,
    stationName: String,
): Boolean {
    if (artist.isNullOrBlank() || title.isBlank()) return false
    val normalizedArtist = normalizeRadioTrackText(artist)
    val normalizedTitle = normalizeRadioTrackText(title)
    val normalizedStation = normalizeRadioTrackText(stationName)
    if (normalizedArtist.length < 2 || normalizedTitle.length < 2) return false
    if (normalizedArtist == normalizedStation || normalizedTitle == normalizedStation) return false
    if ("http" in normalizedArtist || "http" in normalizedTitle || "www" in normalizedArtist || "www" in normalizedTitle) {
        return false
    }

    val generic =
        setOf(
            "radio",
            "webradio",
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
        )
    if (normalizedArtist in generic || normalizedTitle in generic) return false

    val compactStation = normalizedStation.replace(" ", "")
    fun isStationFragment(value: String): Boolean {
        val compactValue = value.replace(" ", "")
        return compactValue.length >= 4 &&
            (compactStation.contains(compactValue) || compactValue.contains(compactStation))
    }

    // Streams frequently format station branding like a track, for example
    // "Antenne - Partyhitmix". Both halves belong to the saved station name,
    // so this must stay eligible for audio fingerprint recognition.
    if (isStationFragment(normalizedArtist) && isStationFragment(normalizedTitle)) return false

    return true
}

internal fun normalizeRadioTrackText(value: String): String =
    value
        .lowercase(Locale.ROOT)
        .replace(
            Regex("""[\(\[][^(\[]*(official|music video|video|audio|lyrics?|remaster(?:ed)?|live)[^\)\]]*[\)\]]"""),
            " ",
        ).replace(Regex("""\b(feat|ft)\.?\b.*"""), " ")
        .replace(Regex("""[^\p{L}\p{N}]+"""), " ")
        .trim()
        .replace(Regex("""\s+"""), " ")
