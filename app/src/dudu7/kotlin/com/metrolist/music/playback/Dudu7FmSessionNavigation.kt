package com.metrolist.music.playback

/** Pure navigation rules used by the Media3 hardware-FM player. */
internal object Dudu7FmSessionNavigation {
    fun retainActiveId(
        validIds: Set<String>,
        rememberedId: String?,
        detectedId: String?,
        fallbackId: String?,
    ): String? = when {
        rememberedId != null && rememberedId in validIds -> rememberedId
        detectedId != null && detectedId in validIds -> detectedId
        fallbackId != null && fallbackId in validIds -> fallbackId
        else -> validIds.firstOrNull()
    }

    fun adjacentIndex(
        size: Int,
        currentIndex: Int,
        next: Boolean,
    ): Int {
        if (size <= 0) return -1
        val safeCurrent = currentIndex.takeIf { it in 0 until size } ?: if (next) -1 else 0
        val candidate = if (next) safeCurrent + 1 else safeCurrent - 1
        return ((candidate % size) + size) % size
    }
}
