package com.metrolist.music.playback

import androidx.media3.common.C
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HttpRangeChunkingDataSourceTest {
    @Test
    fun `youtube sized transfer is planned in ten MiB chunks`() {
        val chunk = 10L * 1024L * 1024L
        val total = 58_265_392L
        assertEquals(chunk, nextHttpChunkLength(total, 0L, chunk))
        assertEquals(chunk, nextHttpChunkLength(total, chunk, chunk))
        assertEquals(5_836_592L, nextHttpChunkLength(total, 5L * chunk, chunk))
        assertEquals(0L, nextHttpChunkLength(total, total, chunk))
    }

    @Test
    fun `unknown request length keeps bounded chunks`() {
        assertEquals(10L * 1024L * 1024L, nextHttpChunkLength(C.LENGTH_UNSET.toLong(), 20L, 10L * 1024L * 1024L))
    }

    @Test
    fun `content range exposes absolute range and total`() {
        val parsed = parseHttpContentRange("bytes 10485760-20971519/58265392")
        assertEquals(10_485_760L, parsed?.start)
        assertEquals(20_971_519L, parsed?.endInclusive)
        assertEquals(58_265_392L, parsed?.totalLength)
        assertEquals(10_485_760L, parsed?.length)
    }

    @Test
    fun `malformed or unsafe content ranges are rejected`() {
        assertNull(parseHttpContentRange(null))
        assertNull(parseHttpContentRange("bytes */58265392"))
        assertNull(parseHttpContentRange("bytes 20-10/100"))
        assertNull(parseHttpContentRange("bytes 0-100/100"))
    }
}
