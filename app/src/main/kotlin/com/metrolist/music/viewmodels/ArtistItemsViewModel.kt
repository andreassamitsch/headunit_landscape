/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.viewmodels

import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.models.BrowseEndpoint
import com.metrolist.innertube.models.SongItem
import com.metrolist.innertube.models.YTItem
import com.metrolist.innertube.models.filterExplicit
import com.metrolist.innertube.models.filterVideoSongs
import com.metrolist.music.constants.HideExplicitKey
import com.metrolist.music.constants.HideVideoSongsKey
import com.metrolist.music.models.ItemsPage
import com.metrolist.music.utils.dataStore
import com.metrolist.music.utils.get
import com.metrolist.music.utils.reportException
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class ArtistItemsViewModel
@Inject
constructor(
    @ApplicationContext val context: Context,
    savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private val artistId = savedStateHandle.get<String>("artistId")!!
    private val browseId = savedStateHandle.get<String>("browseId").orEmpty()
    private val params = savedStateHandle.get<String>("params")

    val title = MutableStateFlow("")
    val itemsPage = MutableStateFlow<ItemsPage?>(null)
    val isLoading = MutableStateFlow(false)
    val errorMessage = MutableStateFlow<String?>(null)

    init {
        loadInitial()
    }

    private fun loadInitial() {
        viewModelScope.launch {
            isLoading.value = true
            errorMessage.value = null
            try {
                if (browseId.isBlank() || browseId == "__artist_songs__") {
                    loadArtistSongFallback()
                } else {
                    loadEndpoint(
                        endpoint =
                            BrowseEndpoint(
                                browseId = browseId,
                                params = params,
                            ),
                    )
                }
            } finally {
                isLoading.value = false
            }
        }
    }

    fun retry() {
        itemsPage.value = null
        loadInitial()
    }

    private suspend fun filteredItems(items: List<YTItem>): List<YTItem> {
        val resolvedItems = YouTube.resolveArtistIds(items)
        val hideExplicit = context.dataStore.get(HideExplicitKey, false)
        val hideVideoSongs = context.dataStore.get(HideVideoSongsKey, false)
        return resolvedItems
            .distinctBy { it.id }
            .filterExplicit(hideExplicit)
            .filterVideoSongs(hideVideoSongs)
    }

    private suspend fun loadEndpoint(
        endpoint: BrowseEndpoint,
        fallbackTitle: String = "",
    ): Boolean {
        val result = YouTube.artistItems(endpoint)
        val artistItemsPage = result.getOrNull()
        if (artistItemsPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            errorMessage.value = result.exceptionOrNull()?.message ?: "Künstler-Inhalte konnten nicht geladen werden"
            return false
        }

        errorMessage.value = null
        title.value = artistItemsPage.title.ifBlank { fallbackTitle }
        itemsPage.value =
            ItemsPage(
                items = filteredItems(artistItemsPage.items),
                continuation = artistItemsPage.continuation,
            )
        Timber
            .tag("Dudu7ArtistItems")
            .d(
                "Opened artist items endpoint title=%s count=%d",
                title.value,
                itemsPage.value?.items?.size ?: 0,
            )
        return true
    }

    private suspend fun loadArtistSongFallback() {
        val result = YouTube.artist(artistId)
        val artistPage = result.getOrNull()
        if (artistPage == null) {
            result.exceptionOrNull()?.let(::reportException)
            errorMessage.value = result.exceptionOrNull()?.message ?: "Künstler konnte nicht geladen werden"
            return
        }

        val songSection =
            artistPage.sections.firstOrNull { section ->
                section.items.any { it is SongItem }
            }
        if (songSection == null) {
            errorMessage.value = "Für diesen Künstler wurden keine Titel gefunden"
            return
        }

        val moreEndpoint = songSection.moreEndpoint
        if (moreEndpoint != null && loadEndpoint(moreEndpoint, songSection.title)) {
            return
        }

        errorMessage.value = null
        title.value = songSection.title.ifBlank { artistPage.artist.title }
        itemsPage.value =
            ItemsPage(
                items = filteredItems(songSection.items),
                continuation = null,
            )
        Timber
            .tag("Dudu7ArtistItems")
            .d(
                "Opened artist song fallback artistId=%s title=%s count=%d",
                artistId,
                title.value,
                itemsPage.value?.items?.size ?: 0,
            )
    }

    fun loadMore() {
        viewModelScope.launch {
            val oldItemsPage = itemsPage.value ?: return@launch
            val continuation = oldItemsPage.continuation ?: return@launch
            isLoading.value = true
            errorMessage.value = null
            YouTube
                .artistItemsContinuation(continuation)
                .onSuccess { artistItemsContinuationPage ->
                    val resolvedItems = YouTube.resolveArtistIds(artistItemsContinuationPage.items)
                    val hideExplicit = context.dataStore.get(HideExplicitKey, false)
                    val hideVideoSongs = context.dataStore.get(HideVideoSongsKey, false)
                    itemsPage.update {
                        ItemsPage(
                            items =
                                (oldItemsPage.items + resolvedItems)
                                    .distinctBy { it.id }
                                    .filterExplicit(hideExplicit)
                                    .filterVideoSongs(hideVideoSongs),
                            continuation = artistItemsContinuationPage.continuation,
                        )
                    }
                }.onFailure {
                    reportException(it)
                    errorMessage.value = it.message ?: "Weitere Inhalte konnten nicht geladen werden"
                }
            isLoading.value = false
        }
    }

    /** Load every continuation before a category is handed to the player queue. */
    suspend fun loadAllItems(): List<YTItem> {
        var page = itemsPage.value ?: return emptyList()
        val all = page.items.toMutableList()
        var continuation = page.continuation
        while (continuation != null) {
            val next = YouTube.artistItemsContinuation(continuation).getOrNull() ?: break
            all += YouTube.resolveArtistIds(next.items)
            continuation = next.continuation
        }
        val hideExplicit = context.dataStore.get(HideExplicitKey, false)
        val hideVideoSongs = context.dataStore.get(HideVideoSongsKey, false)
        val filtered = all.distinctBy { it.id }.filterExplicit(hideExplicit).filterVideoSongs(hideVideoSongs)
        itemsPage.value = ItemsPage(items = filtered, continuation = null)
        return filtered
    }
}
