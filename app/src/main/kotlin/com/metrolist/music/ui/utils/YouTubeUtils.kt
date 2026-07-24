/**
 * Metrolist Project (C) 2026
 * Licensed under GPL-3.0 | See git history for contributors
 */

@file:Suppress("LocalVariableName")

package com.metrolist.music.ui.utils

fun String.resize(
    width: Int? = null,
    height: Int? = null,
): String {
    if (width == null && height == null) return this

    // YouTube Music album art is served from both lh3 and yt3. Replace the
    // existing dimensions instead of appending a second parameter block.
    "https://(?:lh3|yt3)\\.googleusercontent\\.com/.*=w(\\d+)-h(\\d+).*".toRegex()
        .matchEntire(this)
        ?.groupValues
        ?.let { group ->
            val (W, H) = group.drop(1).map(String::toInt)
            val requestedWidth = width ?: ((height!!.toLong() * W) / H).toInt()
            val requestedHeight = height ?: ((width!!.toLong() * H) / W).toInt()
            return "${substringBefore("=w")}=w$requestedWidth-h$requestedHeight-l90-rj"
        }

    // Channel/avatar images use =sNN by default. A rectangular request needs
    // YouTube's w-h-p form; a single dimension can stay in the square format.
    if (matches("https://yt3\\.ggpht\\.com/.*=s(\\d+).*".toRegex())) {
        val base = substringBefore("=s")
        return if (width != null && height != null) {
            "$base=w$width-h$height-p-l90-rj"
        } else {
            "$base=s${width ?: height}"
        }
    }

    // Video thumbnails should use the high-resolution asset for large player
    // artwork while retaining any signed/query parameters on the URL.
    if (
        startsWith("https://i.ytimg.com/vi/") &&
        maxOf(width ?: 0, height ?: 0) >= 544
    ) {
        return replace(
            Regex("/(?:default|mqdefault|hqdefault|sddefault)\\.jpg(?=\\?|$)"),
            "/maxresdefault.jpg",
        )
    }

    return this
}
