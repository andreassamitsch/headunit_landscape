/**
 * Storage model based on the small, local-first station library concept used by
 * Transistor (MIT License): https://codeberg.org/y20k/transistor
 */
package com.metrolist.music.radio

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONArray
import org.json.JSONObject

class RadioStationStore private constructor(context: Context) {
    private val preferences =
        context.applicationContext.getSharedPreferences("metrolist_webradio", Context.MODE_PRIVATE)
    private val _stations = MutableStateFlow(loadStations())
    val stations: StateFlow<List<RadioStation>> = _stations.asStateFlow()

    @Synchronized
    fun addOrUpdate(station: RadioStation) {
        val list = _stations.value.toMutableList()
        val index = list.indexOfFirst { it.uuid == station.uuid }
        if (index >= 0) list[index] = station else list.add(station)
        persist(list)
    }

    @Synchronized
    fun remove(uuid: String) {
        persist(_stations.value.filterNot { it.uuid == uuid })
    }

    @Synchronized
    fun move(uuid: String, direction: Int) {
        val list = _stations.value.toMutableList()
        val index = list.indexOfFirst { it.uuid == uuid }
        val target = index + direction
        if (index !in list.indices || target !in list.indices) return
        val item = list.removeAt(index)
        list.add(target, item)
        persist(list)
    }

    /** Persist an arbitrary drag-and-drop order while retaining every station once. */
    @Synchronized
    fun reorder(orderedUuids: List<String>) {
        if (orderedUuids.isEmpty()) return
        val byId = _stations.value.associateBy { it.uuid }
        val ordered = orderedUuids.mapNotNull(byId::get).distinctBy { it.uuid }
        val missing = _stations.value.filterNot { station -> ordered.any { it.uuid == station.uuid } }
        val result = ordered + missing
        if (result.map { it.uuid } != _stations.value.map { it.uuid }) persist(result)
    }

    fun contains(uuid: String): Boolean = _stations.value.any { it.uuid == uuid }

    private fun persist(stations: List<RadioStation>) {
        _stations.value = stations
        preferences.edit().putString(KEY_STATIONS, stations.toJson().toString()).apply()
    }

    private fun loadStations(): List<RadioStation> =
        runCatching {
            val raw = preferences.getString(KEY_STATIONS, null) ?: return emptyList()
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    val item = array.getJSONObject(index)
                    add(item.toRadioStation())
                }
            }.filter { it.name.isNotBlank() && it.streamUrl.isNotBlank() }
        }.getOrDefault(emptyList())

    private fun List<RadioStation>.toJson() =
        JSONArray().also { array ->
            forEach { station ->
                array.put(
                    JSONObject().apply {
                        put("uuid", station.uuid)
                        put("name", station.name)
                        put("streamUrl", station.streamUrl)
                        put("homepage", station.homepage)
                        put("favicon", station.favicon)
                        put("country", station.country)
                        put("language", station.language)
                        put("tags", station.tags)
                        put("codec", station.codec)
                        put("bitrate", station.bitrate)
                    },
                )
            }
        }

    private fun JSONObject.toRadioStation() =
        RadioStation(
            uuid = optString("uuid"),
            name = optString("name"),
            streamUrl = optString("streamUrl"),
            homepage = optString("homepage"),
            favicon = optString("favicon"),
            country = optString("country"),
            language = optString("language"),
            tags = optString("tags"),
            codec = optString("codec"),
            bitrate = optInt("bitrate", 0),
        )

    companion object {
        private const val KEY_STATIONS = "stations"

        @Volatile
        private var instance: RadioStationStore? = null

        fun get(context: Context): RadioStationStore =
            instance ?: synchronized(this) {
                instance ?: RadioStationStore(context).also { instance = it }
            }
    }
}
