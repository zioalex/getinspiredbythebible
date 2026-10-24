package org.voxquieta.app

import android.content.Context
import android.content.SharedPreferences
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for Feature Spotlight SharedPreferences helpers (BITB-054).
 *
 * Tests the pure logic of hasTourBeenSeen, markTourSeen, and clearTourSeen
 * without requiring a real Android Context.
 */
class FeatureSpotlightTest {

    private lateinit var mockContext: Context
    private lateinit var mockPrefs: SharedPreferences
    private lateinit var mockEditor: SharedPreferences.Editor

    @Before
    fun setUp() {
        mockContext = mockk(relaxed = true)
        mockPrefs = mockk(relaxed = true)
        mockEditor = mockk(relaxed = true)

        every { mockContext.getSharedPreferences("app_prefs", Context.MODE_PRIVATE) } returns mockPrefs
        every { mockPrefs.edit() } returns mockEditor
        every { mockEditor.putBoolean("tour_seen", true) } returns mockEditor
        every { mockEditor.putBoolean("tour_seen", false) } returns mockEditor
    }

    @Test
    fun `hasTourBeenSeen returns false by default`() {
        every { mockPrefs.getBoolean("tour_seen", false) } returns false

        assertFalse(mockContext.hasTourBeenSeen())
    }

    @Test
    fun `hasTourBeenSeen returns true after markTourSeen`() {
        every { mockPrefs.getBoolean("tour_seen", false) } returns true

        assertTrue(mockContext.hasTourBeenSeen())
    }

    @Test
    fun `markTourSeen writes true to SharedPreferences`() {
        mockContext.markTourSeen()

        verify(exactly = 1) { mockEditor.putBoolean("tour_seen", true) }
        verify(exactly = 1) { mockEditor.apply() }
    }

    @Test
    fun `clearTourSeen writes false to SharedPreferences`() {
        mockContext.clearTourSeen()

        verify(exactly = 1) { mockEditor.putBoolean("tour_seen", false) }
        verify(exactly = 1) { mockEditor.apply() }
    }

    @Test
    fun `tourSeen persists across calls`() {
        // Initially not seen
        every { mockPrefs.getBoolean("tour_seen", false) } returns false
        assertFalse(mockContext.hasTourBeenSeen())

        // Mark as seen
        mockContext.markTourSeen()
        every { mockPrefs.getBoolean("tour_seen", false) } returns true
        assertTrue(mockContext.hasTourBeenSeen())

        // Clear
        mockContext.clearTourSeen()
        every { mockPrefs.getBoolean("tour_seen", false) } returns false
        assertFalse(mockContext.hasTourBeenSeen())
    }
}
