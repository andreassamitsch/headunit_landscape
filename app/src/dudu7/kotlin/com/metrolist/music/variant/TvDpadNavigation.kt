package com.metrolist.music.variant

import android.app.UiModeManager
import android.content.Context
import android.content.pm.PackageManager
import androidx.compose.foundation.border
import androidx.compose.foundation.focusGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.unit.dp

/** This is deliberately a Dudu7-flavor-only opt-in; receiving a DPAD key is not a TV signal. */
internal object TvDpadNavigation {
    fun isEnabled(context: Context): Boolean {
        val pm = context.packageManager
        val uiMode = (context.getSystemService(Context.UI_MODE_SERVICE) as? UiModeManager)?.currentModeType
        val hasFytServices = listOf("com.syu.ms", "com.syu.ss").any { packageName ->
            try {
                @Suppress("DEPRECATION")
                pm.getPackageInfo(packageName, 0)
                true
            } catch (_: PackageManager.NameNotFoundException) {
                false
            } catch (_: SecurityException) {
                // Unknown device: fail closed rather than rerouting headunit input.
                true
            }
        }
        return shouldEnable(
            isTelevisionMode = uiMode == android.content.res.Configuration.UI_MODE_TYPE_TELEVISION,
            hasLeanback = pm.hasSystemFeature(PackageManager.FEATURE_LEANBACK),
            hasAutomotive = pm.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE),
            hasFytServices = hasFytServices,
        )
    }

    internal fun shouldEnable(
        isTelevisionMode: Boolean,
        hasLeanback: Boolean,
        hasAutomotive: Boolean,
        hasFytServices: Boolean,
    ): Boolean = isTelevisionMode && hasLeanback && !hasAutomotive && !hasFytServices
}

/** On the headunit this is the identity modifier: its existing touch/key paths are untouched. */
internal fun Modifier.tvDpadFocusGroup(enabled: Boolean): Modifier =
    if (enabled) this.focusGroup() else this

/** TV-only visible highlight; does not add a second click/focus target or consume key events. */
internal fun Modifier.tvDpadFocusIndicator(enabled: Boolean): Modifier =
    if (!enabled) this else composed {
        var focused by remember { mutableStateOf(false) }
        this.onFocusChanged { focused = it.isFocused }
            .border(
                width = if (focused) 2.dp else 0.dp,
                color = if (focused) MaterialTheme.colorScheme.primary else androidx.compose.ui.graphics.Color.Transparent,
                shape = RoundedCornerShape(8.dp),
            )
    }
