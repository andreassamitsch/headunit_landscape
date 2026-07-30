/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

package com.metrolist.music.viewmodels

import android.content.Context
import android.content.Intent
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.metrolist.music.App
import com.metrolist.innertube.YouTube
import com.metrolist.innertube.utils.parseCookieString
import com.metrolist.music.constants.AccountChannelHandleKey
import com.metrolist.music.constants.AccountEmailKey
import com.metrolist.music.constants.AccountNameKey
import com.metrolist.music.constants.DataSyncIdKey
import com.metrolist.music.constants.InnerTubeCookieKey
import com.metrolist.music.constants.VisitorDataKey
import com.metrolist.music.utils.SyncUtils
import com.metrolist.music.utils.dataStore
import com.metrolist.music.utils.safeDataStoreEdit
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import timber.log.Timber
import javax.inject.Inject

@HiltViewModel
class AccountSettingsViewModel @Inject constructor(
    private val syncUtils: SyncUtils,
) : ViewModel() {

    /**
     * Logout user and clear all synced content to prevent data mixing between accounts
     */
    fun logoutAndClearSyncedContent(context: Context, onCookieChange: (String) -> Unit) {
        viewModelScope.launch(Dispatchers.IO) {
            // Clear all YouTube Music synced content first
            syncUtils.clearAllSyncedContent()

            // Then clear account preferences
            App.forgetAccount(context)

            // Clear cookie in UI
            onCookieChange("")
        }
    }

    /**
     * Clear all library data including songs, albums, artists, playlists, podcasts.
     */
    suspend fun clearAllLibraryData() {
        Timber.d("[LOGOUT_CLEAR] ViewModel: clearAllLibraryData called")
        syncUtils.clearAllLibraryData()
        Timber.d("[LOGOUT_CLEAR] ViewModel: clearAllLibraryData completed")
    }

    /**
     * Forget the account FIRST (clearing auth so all background syncs skip),
     * THEN clear all library data. This prevents sync operations that are
     * triggered by the database becoming empty from re-adding songs.
     */
    suspend fun logoutAndClearLibraryData(context: Context) {
        Timber.d("[LOGOUT_CLEAR] ViewModel: logoutAndClearLibraryData called")
        withContext(Dispatchers.IO) {
            // Forget account first — clears cookie/auth from DataStore.
            // Once isLoggedIn() returns false, ALL sync operations will skip.
            App.forgetAccount(context)

            // Now clear the local database. Any sync coroutines that observe
            // the empty state will check isLoggedIn() and skip silently.
            syncUtils.clearAllLibraryData()
        }
        Timber.d("[LOGOUT_CLEAR] ViewModel: logoutAndClearLibraryData completed")
    }

    /**
     * Just logout without clearing library data
     */
    suspend fun logoutKeepData(context: Context, onCookieChange: (String) -> Unit) {
        Timber.d("[LOGOUT_KEEP] ViewModel: logoutKeepData called")
        withContext(Dispatchers.IO) {
            App.forgetAccount(context)
        }
        Timber.d("[LOGOUT_KEEP] ViewModel: Account forgotten, clearing cookie in UI")
        onCookieChange("")
    }

    /**
     * Save token credentials atomically to DataStore, then restart the app.
     * This ensures all writes complete before the process is killed,
     * preventing the race condition where Runtime.exit(0) kills the process
     * before async DataStore coroutines finish writing.
     */
    fun saveTokenAndRestart(
        context: Context,
        cookie: String,
        visitorData: String,
        dataSyncId: String,
        accountName: String,
        accountEmail: String,
        accountChannelHandle: String,
    ) {
        val normalizedCookie = cookie.trim()
        if ("SAPISID" !in parseCookieString(normalizedCookie)) {
            Timber.e("saveTokenAndRestart: missing SAPISID; token not saved")
            return
        }
        val normalizedVisitorData = visitorData.trim()
        val normalizedDataSyncId = dataSyncId.trim().substringBefore("||")

        viewModelScope.launch(Dispatchers.IO) {
            val saved = context.safeDataStoreEdit { settings ->
                settings[InnerTubeCookieKey] = normalizedCookie
                settings[VisitorDataKey] = normalizedVisitorData
                settings[DataSyncIdKey] = normalizedDataSyncId
                settings[AccountNameKey] = accountName.trim()
                settings[AccountEmailKey] = accountEmail.trim()
                settings[AccountChannelHandleKey] = accountChannelHandle.trim()
            }
            if (!saved) {
                Timber.e("saveTokenAndRestart: DataStore write failed — skipping restart to avoid losing credentials")
                return@launch
            }
            // Apply the new session immediately. A forced Runtime.exit(0) leaves some FYT
            // launchers on the previously visible app and looks exactly like a crash.
            YouTube.cookie = normalizedCookie
            YouTube.visitorData = normalizedVisitorData.takeIf { it.isNotBlank() }
            YouTube.dataSyncId = normalizedDataSyncId.takeIf { it.isNotBlank() }
            withContext(Dispatchers.Main) {
                val intent = context.packageManager.getLaunchIntentForPackage(context.packageName)
                if (intent != null) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
                    runCatching { context.startActivity(intent) }
                        .onFailure { Timber.e(it, "saveTokenAndRestart: safe relaunch failed") }
                } else {
                    Timber.w("saveTokenAndRestart: no launch intent; credentials remain active without relaunch")
                }
            }
        }
    }
}
