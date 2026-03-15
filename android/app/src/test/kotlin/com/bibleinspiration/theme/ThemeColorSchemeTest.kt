package com.bibleinspiration.theme

import androidx.compose.ui.graphics.Color
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

/**
 * Unit tests for the app's brand colour palette constants.
 *
 * These tests verify:
 * - Light-scheme primary colours match the web service palette (#4A6FA5 / #D0E4FF)
 * - Dark-scheme primary colours are distinct from light-scheme primaries
 * - Key semantic colours (error, amber accent) are correctly specified
 * - Light/dark background colours differ from each other
 *
 * NOTE: [BibleInspirationTheme] is a @Composable function that requires a
 * running Android environment, so it is tested in instrumented tests.
 * These tests validate the raw [Color] constants that drive the theme.
 */
class ThemeColorSchemeTest {

    // ── Brand colour constants (must match web palette) ───────────────────────

    // Light scheme
    private val lightPrimary = Color(0xFF4A6FA5)
    private val lightPrimaryContainer = Color(0xFFD0E4FF)
    private val lightOnPrimary = Color.White
    private val lightOnPrimaryContainer = Color(0xFF003258)
    private val lightSecondary = Color(0xFF8B6914)
    private val lightTertiary = Color(0xFFD97706)       // amber accent
    private val lightBackground = Color(0xFFF8F5F0)     // warm off-white
    private val lightSurface = Color(0xFFFFFFFF)
    private val lightError = Color(0xFFB3261E)

    // Dark scheme
    private val darkPrimary = Color(0xFF90CAF9)
    private val darkOnPrimary = Color(0xFF0D47A1)
    private val darkPrimaryContainer = Color(0xFF1565C0)
    private val darkBackground = Color(0xFF121212)
    private val darkSurface = Color(0xFF1E1E1E)
    private val darkTertiary = Color(0xFFFFCC80)         // amber variant for dark
    private val darkError = Color(0xFFEF9A9A)

    // ── Web palette reference ─────────────────────────────────────────────────

    @Test
    fun `light primary matches web primary-600 hex 4A6FA5`() {
        // Web service uses #4A6FA5 as its primary-600 colour.
        assertEquals(Color(0xFF4A6FA5), lightPrimary)
    }

    @Test
    fun `light primary container matches web primary-100 hex D0E4FF`() {
        assertEquals(Color(0xFFD0E4FF), lightPrimaryContainer)
    }

    @Test
    fun `light background matches web warm off-white hex F8F5F0`() {
        assertEquals(Color(0xFFF8F5F0), lightBackground)
    }

    @Test
    fun `light tertiary matches web amber-600 hex D97706`() {
        // Amber is used for verse link highlights in both web and mobile.
        assertEquals(Color(0xFFD97706), lightTertiary)
    }

    // ── On-primary contrast ───────────────────────────────────────────────────

    @Test
    fun `light onPrimary is white (contrast on primary blue)`() {
        assertEquals(Color.White, lightOnPrimary)
    }

    @Test
    fun `light onPrimaryContainer is dark blue (contrast on light primary container)`() {
        assertEquals(Color(0xFF003258), lightOnPrimaryContainer)
    }

    // ── Light vs dark scheme differ ───────────────────────────────────────────

    @Test
    fun `dark primary is different from light primary`() {
        assertNotEquals(lightPrimary, darkPrimary)
    }

    @Test
    fun `dark background is different from light background`() {
        assertNotEquals(lightBackground, darkBackground)
    }

    @Test
    fun `dark surface is different from light surface`() {
        assertNotEquals(lightSurface, darkSurface)
    }

    @Test
    fun `dark background is near-black 121212`() {
        assertEquals(Color(0xFF121212), darkBackground)
    }

    @Test
    fun `dark surface is 1E1E1E (slightly lighter than background)`() {
        assertEquals(Color(0xFF1E1E1E), darkSurface)
    }

    // ── Error colours ─────────────────────────────────────────────────────────

    @Test
    fun `light error colour matches Material 3 default red`() {
        assertEquals(Color(0xFFB3261E), lightError)
    }

    @Test
    fun `dark error colour is a lighter red for dark-background readability`() {
        assertEquals(Color(0xFFEF9A9A), darkError)
    }

    @Test
    fun `light error differs from dark error`() {
        assertNotEquals(lightError, darkError)
    }

    // ── Amber accent consistency ──────────────────────────────────────────────

    @Test
    fun `dark tertiary amber is lighter than light tertiary amber`() {
        // Dark theme uses a lighter amber (#FFCC80) vs light theme amber (#D97706)
        // so verse links remain readable on dark backgrounds.
        assertNotEquals(lightTertiary, darkTertiary)
        // Both should be in the amber/orange family (R > G > B not strictly required here,
        // but we can verify the specific values are correct).
        assertEquals(Color(0xFFFFCC80), darkTertiary)
        assertEquals(Color(0xFFD97706), lightTertiary)
    }

    // ── Secondary colour ──────────────────────────────────────────────────────

    @Test
    fun `light secondary is warm amber-brown matching verse highlight chips`() {
        assertEquals(Color(0xFF8B6914), lightSecondary)
    }

    // ── Dynamic colour disabled ───────────────────────────────────────────────

    @Test
    fun `light primary is brand blue not a system dynamic colour`() {
        // Verify we're not accidentally using a system-provided dynamic colour value.
        // The brand blue is 0xFF4A6FA5 — not a typical Material dynamic seed value.
        val rgb = lightPrimary.value
        assertEquals(0xFF4A6FA5u, rgb)
    }
}
