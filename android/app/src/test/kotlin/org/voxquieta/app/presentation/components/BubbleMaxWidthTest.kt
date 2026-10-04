package org.voxquieta.app.presentation.components

import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** JVM unit tests for [bubbleMaxWidth] (BITB-174: adaptive chat bubble width). */
class BubbleMaxWidthTest {

    @Test
    fun `phone width keeps the historical 320dp cap`() {
        // 360dp phone minus 2 x 12dp row padding
        assertEquals(320.dp, bubbleMaxWidth(336.dp))
    }

    @Test
    fun `narrow screen never exceeds available width`() {
        assertEquals(280.dp, bubbleMaxWidth(280.dp))
        assertEquals(100.dp, bubbleMaxWidth(100.dp))
    }

    @Test
    fun `tablet portrait uses 85 percent of available width`() {
        assertEquals(680.dp, bubbleMaxWidth(800.dp))
    }

    @Test
    fun `tablet landscape is capped at 840dp`() {
        assertEquals(840.dp, bubbleMaxWidth(1280.dp))
    }

    @Test
    fun `boundary where 85 percent equals the floor`() {
        // 320 / 0.85 = 376.47..; just above it scales, just below it floors.
        assertEquals(320.dp, bubbleMaxWidth(370.dp))
        assertTrue(bubbleMaxWidth(400.dp) > 320.dp)
        assertEquals(340.dp, bubbleMaxWidth(400.dp))
    }

    @Test
    fun `boundary where 85 percent equals the ceiling`() {
        // 840 / 0.85 = 988.23..
        assertEquals(840.dp, bubbleMaxWidth(1000.dp))
        assertEquals(839.8f, bubbleMaxWidth(988.dp).value, 0.01f)
        assertTrue(bubbleMaxWidth(980.dp) < 840.dp)
    }

    @Test
    fun `available exactly at the floor returns the floor`() {
        assertEquals(320.dp, bubbleMaxWidth(320.dp))
    }

    @Test
    fun `infinite and unspecified fall back to the ceiling`() {
        assertEquals(840.dp, bubbleMaxWidth(Dp.Infinity))
        assertEquals(840.dp, bubbleMaxWidth(Dp.Unspecified))
    }

    @Test
    fun `zero and negative available width yield zero`() {
        assertEquals(0.dp, bubbleMaxWidth(0.dp))
        assertEquals(0.dp, bubbleMaxWidth((-10).dp))
    }
}
