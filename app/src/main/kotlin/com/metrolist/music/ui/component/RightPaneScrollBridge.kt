package com.metrolist.music.ui.component

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf

/**
 * Bridges vertical gestures from the fixed Dudu7 right-pane container to the
 * currently embedded screen. Registration is owner-scoped so navigating between
 * screens cannot let an old screen clear a newer handler during disposal.
 */
class RightPaneScrollBridge {
    private var owner: Any? = null

    var handler: ((Float) -> Unit)? by mutableStateOf(null)
        private set

    fun register(owner: Any, handler: (Float) -> Unit) {
        this.owner = owner
        this.handler = handler
    }

    fun unregister(owner: Any) {
        if (this.owner === owner) {
            this.owner = null
            handler = null
        }
    }
}

val LocalRightPaneScrollBridge = staticCompositionLocalOf<RightPaneScrollBridge?> { null }
