package org.voxquieta.app.presentation.components

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Pins the EXACT follow-up chip palette for BOTH modes (BITB-278 FR5).
 *
 * This is the regression test for the user-reported "colors were a bit
 * off" bug: the stock M3 `SuggestionChip` colors (light: surfaceVariant
 * #EFEBE5 container / onSurfaceVariant #49454F label / outlineVariant
 * #CAC4D0 border) clashed with the web chip. Light mode must mirror the
 * web chip (`FollowUpSuggestions.tsx`: `bg-white border-primary-200
 * text-gray-700`); dark mode must keep the dark scheme's neutral trio and
 * never the blue dark `primary` (#90CAF9).
 */
class FollowUpChipPaletteTest {

    @Test
    fun `light mode mirrors the web chip palette exactly`() {
        val palette = followUpChipPalette(darkTheme = false)

        assertEquals(Color(0xFFFFFFFF), palette.containerColor) // web bg-white
        assertEquals(Color(0xFF374151), palette.labelColor)     // web text-gray-700
        assertEquals(Color(0xFFE6D0B8), palette.borderColor)     // web primary-200
    }

    @Test
    fun `dark mode keeps the dark scheme neutral trio`() {
        val palette = followUpChipPalette(darkTheme = true)

        assertEquals(Color(0xFF2C2C2C), palette.containerColor) // dark surfaceVariant
        assertEquals(Color(0xFFBDBDBD), palette.labelColor)     // dark onSurfaceVariant
        assertEquals(Color(0xFF49454F), palette.borderColor)    // dark outlineVariant
    }

    @Test
    fun `light mode no longer uses the old stock M3 trio`() {
        // Fails if anyone reverts to the pre-BITB-278 stock chip colors.
        val palette = followUpChipPalette(darkTheme = false)

        assertNotEquals("container must be white, not stock surfaceVariant", Color(0xFFEFEBE5), palette.containerColor)
        assertNotEquals("label must be web gray-700, not stock onSurfaceVariant", Color(0xFF49454F), palette.labelColor)
        assertNotEquals("border must be web primary-200, not stock outlineVariant", Color(0xFFCAC4D0), palette.borderColor)
    }

    @Test
    fun `dark mode never uses the blue dark primary`() {
        // FR3: the dark scheme's `primary` (#90CAF9) must not leak into the
        // chip border — it breaks the warm web palette.
        val palette = followUpChipPalette(darkTheme = true)

        assertNotEquals(Color(0xFF90CAF9), palette.borderColor)
    }

    @Test
    fun `palettes differ between modes`() {
        assertNotEquals(followUpChipPalette(darkTheme = false), followUpChipPalette(darkTheme = true))
    }
}
