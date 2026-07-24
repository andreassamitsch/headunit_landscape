package com.metrolist.music.ui.component

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.geometry.Offset

/**
 * Bridges vertical gestures and taps from the fixed Dudu7 right-pane container
 * to the currently embedded screen. Registration is owner-scoped so navigating
 * between screens cannot let an old screen clear a newer handler during disposal.
 */
class RightPaneScrollBridge {
    private var owner: Any? = null

    var handler: ((Float) -> Unit)? by mutableStateOf(null)
        private set

    var tapHandler: ((Offset) -> Boolean)? by mutableStateOf(null)
        private set

    fun register(
        owner: Any,
        handler: (Float) -> Unit,
        tapHandler: ((Offset) -> Boolean)? = null,
    ) {
        this.owner = owner
        this.handler = handler
        this.tapHandler = tapHandler
    }

    fun dispatchTap(positionInRoot: Offset): Boolean = tapHandler?.invoke(positionInRoot) == true

    fun unregister(owner: Any) {
        if (this.owner === owner) {
            this.owner = null
            handler = null
            tapHandler = null
        }
    }
}

val LocalRightPaneScrollBridge = staticCompositionLocalOf<RightPaneScrollBridge?> { null }
