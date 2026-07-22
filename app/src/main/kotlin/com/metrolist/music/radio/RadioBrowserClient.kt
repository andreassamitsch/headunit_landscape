/**
 * Station search follows the Radio Browser integration approach used by
 * Transistor (MIT License): https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.UUID

object RadioBrowserClient {
    private const val USER_AGENT = "MetrolistHU/13.6.2 (Android WebRadio)"
    private const val SEARCH_ENDPOINT = "https://all.api.radio-browser.info/json/stations/search"

    suspend fun search(query: String): Result<List<RadioStation>> =
        runCatching {
            withContext(Dispatchers.IO) {
                val encoded = URLEncoder.encode(query.trim(), StandardCharsets.UTF_8.name())
                val url =
                    URL(
                        "$SEARCH_ENDPOINT?name=$encoded&hidebroken=true&limit=60&order=clickcount&reverse=true",
                    )
                val text = readText(url)
                val array = JSONArray(text)
                buildList {
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
                }.distinctBy { it.uuid }
            }
        }

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
