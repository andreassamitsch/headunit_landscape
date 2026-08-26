package com.metrolist.music.radio

import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.util.Locale

internal fun parseRadioStreamTitle(raw: String): Pair<String?, String> {
    val cleaned = repairRadioStreamMojibake(raw).substringBefore(" [").trim()
    val separator = listOf(" - ", " – ", " — ", " | ").firstOrNull { it in cleaned }
    if (separator == null) return null to cleaned
    val artist = cleaned.substringBefore(separator).trim().takeIf { it.isNotBlank() }
    val title = cleaned.substringAfter(separator).trim().ifBlank { cleaned }
    return artist to title
}

/**
 * Media3 exposes ICY stream metadata as an already-decoded String. Some radio streams label
 * UTF-8 bytes as ISO-8859-1, which turns e.g. `für` into the characteristic `fÃ¼r` mojibake.
 *
 * Repair is intentionally conservative and local to WebRadio metadata: only strings that contain
 * typical mojibake markers, consist entirely of single-byte Latin-1 characters and round-trip to
 * strictly valid UTF-8 are eligible. The candidate is accepted only when it contains fewer
 * mojibake markers than the original. Correct Unicode/ASCII text is therefore left untouched.
 */
internal fun repairRadioStreamMojibake(value: String): String {
    val originalScore = radioMojibakeScore(value)
    if (originalScore == 0 || value.any { it.code > 0xff }) return value

    val candidate =
        runCatching {
            val decoder =
                Charsets.UTF_8
                    .newDecoder()
                    .onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT)
            decoder.decode(ByteBuffer.wrap(value.toByteArray(Charsets.ISO_8859_1))).toString()
        }.getOrNull() ?: return value

    return candidate.takeIf { radioMojibakeScore(it) < originalScore } ?: value
}

private fun radioMojibakeScore(value: String): Int =
    value.sumOf { character ->
        when {
            character == 'Ã' || character == 'Â' -> 3
            character == 'â' || character == 'ð' -> 2
            character == '�' -> 4
            character.code in 0x80..0x9f -> 2
            else -> 0
        }
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
