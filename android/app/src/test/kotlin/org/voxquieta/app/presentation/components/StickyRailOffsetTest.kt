package org.voxquieta.app.presentation.components

import org.junit.Assert.assertEquals
import org.junit.Test

/** JVM unit tests for [stickyRailOffset] (BITB-205: sticky action rail beside an answer). */
class StickyRailOffsetTest {

    private val margin = 8f

    private fun offset(itemTop: Float, itemHeight: Float, railHeight: Float = 200f) =
        stickyRailOffset(
            itemTop = itemTop,
            itemHeight = itemHeight,
            railHeight = railHeight,
            viewportTop = 100f,
            viewportBottom = 1100f,
            marginPx = margin,
        )

    @Test
    fun `answer fully inside the viewport keeps the rail at its top`() {
        assertEquals(0f, offset(itemTop = 300f, itemHeight = 600f), 0.001f)
    }

    @Test
    fun `answer whose top scrolled above the viewport pins the rail just below the top`() {
        // item top is 250px above the viewport top (100) -> rail at viewportTop + margin
        assertEquals(258f, offset(itemTop = -150f, itemHeight = 2000f), 0.001f)
    }

    @Test
    fun `rail stops at the bottom edge of the answer`() {
        // answer ends 100px below viewport top: rail may not slide past item bottom - rail height
        // item: top=-1800 height=1900 -> bottom=100; max offset = 1900 - 200
        assertEquals(1700f, offset(itemTop = -1800f, itemHeight = 1900f), 0.001f)
    }

    @Test
    fun `answer entirely below the viewport keeps the rail at its top`() {
        assertEquals(0f, offset(itemTop = 2000f, itemHeight = 800f), 0.001f)
    }

    @Test
    fun `answer entirely above the viewport clamps to its bottom edge`() {
        assertEquals(600f, offset(itemTop = -2000f, itemHeight = 800f), 0.001f)
    }

    @Test
    fun `rail taller than the answer never moves`() {
        assertEquals(0f, offset(itemTop = -50f, itemHeight = 150f, railHeight = 300f), 0.001f)
        assertEquals(0f, offset(itemTop = 0f, itemHeight = 200f, railHeight = 200f), 0.001f)
    }

    @Test
    fun `rail is kept inside a short viewport`() {
        // viewport 100..300 (200px), rail 200px: pinning below the top would push the rail's
        // bottom past the viewport bottom, so it is held back to viewportBottom - margin
        val result = stickyRailOffset(
            itemTop = -500f,
            itemHeight = 3000f,
            railHeight = 200f,
            viewportTop = 100f,
            viewportBottom = 300f,
            marginPx = margin,
        )
        // pinned would be 608; limited so itemTop + offset + rail <= viewportBottom - margin
        assertEquals(500f + 300f - margin - 200f, result, 0.001f)
    }
}
