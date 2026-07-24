/**
 * Station search follows the Radio Browser integration approach used by
 * Transistor (MIT License): https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.UUID

object RadioBrowserClient {
    private const val USER_AGENT = "MetrolistHU/13.6.9 (Android WebRadio)"
    private const val SEARCH_ENDPOINT = "https://all.api.radio-browser.info/json/stations/search"

    data class SearchFilters(
        val country: String = "",
        val genre: String = "",
        val language: String = "",
    ) {
        val isEmpty: Boolean
            get() = country.isBlank() && genre.isBlank() && language.isBlank()
    }

    /**
     * Search by station name and structured Radio Browser metadata. Without an
     * explicit filter a free-text query is deliberately tried against name,
     * country, tag and language, so "Österreich" / "Austria" works even when the
     * word is absent from the station name.
     */
    suspend fun search(
        query: String,
        filters: SearchFilters = SearchFilters(),
    ): Result<List<RadioStation>> =
        runCatching {
            withContext(Dispatchers.IO) {
                val cleanedQuery = query.trim()
                val requests =
                    if (filters.isEmpty && cleanedQuery.isNotBlank()) {
                        listOf(
                            mapOf("name" to cleanedQuery),
                            mapOf("country" to normalizeCountry(cleanedQuery)),
                            mapOf("tag" to cleanedQuery),
                            mapOf("language" to cleanedQuery),
                        )
                    } else {
                        listOf(
                            buildMap {
                                cleanedQuery.takeIf { it.isNotBlank() }?.let { put("name", it) }
                                filters.country.trim().takeIf { it.isNotBlank() }?.let { put("country", normalizeCountry(it)) }
                                filters.genre.trim().takeIf { it.isNotBlank() }?.let { put("tag", it) }
                                filters.language.trim().takeIf { it.isNotBlank() }?.let { put("language", it) }
                            },
                        )
                    }
                require(requests.any { it.isNotEmpty() }) { "Bitte Suchtext oder Filter angeben" }

                coroutineScope {
                    requests
                        .filter { it.isNotEmpty() }
                        .map { params -> async { requestStations(params) } }
                        .awaitAll()
                        .flatten()
                        .distinctBy { it.uuid }
                        .take(120)
                }
            }
        }

    private fun requestStations(parameters: Map<String, String>): List<RadioStation> {
        val queryString =
            buildList {
                parameters.forEach { (key, value) -> add("$key=${encode(value)}") }
                add("hidebroken=true")
                add("limit=80")
                add("order=clickcount")
                add("reverse=true")
            }.joinToString("&")
        val array = JSONArray(readText(URL("$SEARCH_ENDPOINT?$queryString")))
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.getJSONObject(index)
                val streamUrl = item.optString("url_resolved").ifBlank { item.optString("url") }
                val name = item.optString("name").trim()
                if (name.isBlank() || streamUrl.isBlank()) continue
                add(
                    RadioStation(
                        uuid = item.optString("stationuuid").ifBlank { UUID.nameUUIDFromBytes(streamUrl.toByteArray()).toString() },
                        name = name,
                        streamUrl = streamUrl,
                        homepage = item.optString("homepage"),
                        favicon = item.optString("favicon"),
                        country = item.optString("country"),
                        language = item.optString("language"),
                        tags = item.optString("tags"),
                        codec = item.optString("codec"),
                        bitrate = item.optInt("bitrate", 0),
                    ),
                )
            }
        }
    }

    private fun normalizeCountry(value: String): String =
        when (value.trim().lowercase()) {
            "österreich", "oesterreich" -> "Austria"
            "deutschland" -> "Germany"
            "schweiz" -> "Switzerland"
            "italien" -> "Italy"
            "frankreich" -> "France"
            "spanien" -> "Spain"
            "kroatien" -> "Croatia"
            "slowenien" -> "Slovenia"
            "ungarn" -> "Hungary"
            "tschechien" -> "Czechia"
            "slowakei" -> "Slovakia"
            "niederlande" -> "Netherlands"
            "vereinigtes königreich", "großbritannien", "grossbritannien" -> "United Kingdom"
            "vereinigte staaten", "usa" -> "United States"
            else -> value.trim()
        }

    private fun encode(value: String): String =
        URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    suspend fun resolveStreamUrl(input: String): Result<String> =
        runCatching {
            withContext(Dispatchers.IO) {
                val trimmed = input.trim()
                require(trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
                    "Ungültige Stream-Adresse"
                }
                val lower = trimmed.lowercase()
                if (!lower.endsWith(".m3u") && !lower.endsWith(".m3u8") && !lower.endsWith(".pls")) {
                    return@withContext trimmed
                }
                if (lower.endsWith(".m3u8")) return@withContext trimmed
                val playlistText = readText(URL(trimmed))
                val candidate =
                    if (lower.endsWith(".pls")) {
                        playlistText.lineSequence()
                            .map { it.trim() }
                            .firstOrNull { it.startsWith("File", ignoreCase = true) && "=" in it }
                            ?.substringAfter("=")
                    } else {
                        playlistText.lineSequence()
                            .map { it.trim() }
                            .firstOrNull { it.isNotBlank() && !it.startsWith("#") }
                    }
                require(!candidate.isNullOrBlank()) { "Keine Stream-Adresse in der Playlist gefunden" }
                URI(trimmed).resolve(candidate).toString()
            }
        }

    private fun readText(url: URL): String {
        val connection = (url.openConnection() as HttpURLConnection).apply {
            connectTimeout = 12_000
            readTimeout = 15_000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", USER_AGENT)
            setRequestProperty("Accept", "application/json, audio/x-mpegurl, audio/x-scpls, */*")
        }
        return try {
            val code = connection.responseCode
            require(code in 200..299) { "Serverfehler $code" }
            connection.inputStream.bufferedReader().use { it.readText() }
        } finally {
            connection.disconnect()
        }
    }
}
