package com.metrolist.music.playback

import java.util.concurrent.atomic.AtomicLong

internal class LatestRequestGate {
    private val generation = AtomicLong(0L)

    fun issue(): Long = generation.incrementAndGet()

    fun isCurrent(token: Long): Boolean = generation.get() == token
}
