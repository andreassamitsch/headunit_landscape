package com.metrolist.music.variant

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import com.metrolist.music.constants.Dudu7AlwaysStartPlayerKey
import com.metrolist.music.constants.Dudu7AutoCenterQueueKey
import com.metrolist.music.constants.Dudu7PlayerPaneWeightKey
import com.metrolist.music.constants.Dudu7StartWithLyricsKey
import com.metrolist.music.constants.Dudu7SwipeToRemoveQueueKey
import com.metrolist.music.constants.KeepScreenOn
import com.metrolist.music.constants.QueueEditLockKey
import com.metrolist.music.constants.ResumeOnBluetoothConnectKey
import com.metrolist.music.constants.UseNewMiniPlayerDesignKey
import com.metrolist.music.constants.UseNewPlayerDesignKey
import com.metrolist.music.utils.dataStore

object VehicleVariantDefaults {
    suspend fun apply(context: Context) {
        context.dataStore.edit { preferences ->
            preferences.putDefault(Dudu7AlwaysStartPlayerKey, true)
            preferences.putDefault(Dudu7PlayerPaneWeightKey, VehicleVariantConfig.defaultPlayerPaneWeight)
            preferences.putDefault(Dudu7StartWithLyricsKey, false)
            preferences.putDefault(Dudu7SwipeToRemoveQueueKey, true)
            preferences.putDefault(Dudu7AutoCenterQueueKey, true)
            preferences.putDefault(KeepScreenOn, true)
            preferences.putDefault(QueueEditLockKey, false)
            preferences.putDefault(ResumeOnBluetoothConnectKey, true)
            preferences.putDefault(UseNewPlayerDesignKey, true)
            preferences.putDefault(UseNewMiniPlayerDesignKey, true)
        }
    }

    private fun <T> androidx.datastore.preferences.core.MutablePreferences.putDefault(
        key: Preferences.Key<T>,
        value: T,
    ) {
        if (!asMap().containsKey(key)) this[key] = value
    }
}
