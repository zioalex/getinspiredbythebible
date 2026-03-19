package com.bibleinspiration.screens

import com.bibleinspiration.presentation.screens.LANGUAGE_OPTIONS
import com.bibleinspiration.presentation.screens.LanguageOption
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for the [LANGUAGE_OPTIONS] list declared in LanguageOptions.kt.
 *
 * Verifies that the options are correctly defined, contain no duplicates, and
 * include all languages expected by the app's localization strategy.
 */
class LanguageOptionsTest {

    // ── Structural integrity ───────────────────────────────────────────────────

    @Test
    fun `LANGUAGE_OPTIONS is not empty`() {
        assertTrue(LANGUAGE_OPTIONS.isNotEmpty())
    }

    @Test
    fun `LANGUAGE_OPTIONS contains exactly 11 languages`() {
        assertEquals(11, LANGUAGE_OPTIONS.size)
    }

    @Test
    fun `all language codes are unique`() {
        val codes = LANGUAGE_OPTIONS.map { it.code }
        assertEquals("Duplicate language codes detected", codes.size, codes.toSet().size)
    }

    @Test
    fun `all display names are unique`() {
        val names = LANGUAGE_OPTIONS.map { it.displayName }
        assertEquals("Duplicate display names detected", names.size, names.toSet().size)
    }

    @Test
    fun `no language option has a blank code`() {
        LANGUAGE_OPTIONS.forEach { option ->
            assertFalse("Blank code found: $option", option.code.isBlank())
        }
    }

    @Test
    fun `no language option has a blank display name`() {
        LANGUAGE_OPTIONS.forEach { option ->
            assertFalse("Blank display name found: $option", option.displayName.isBlank())
        }
    }

    // ── Required languages ────────────────────────────────────────────────────

    @Test
    fun `LANGUAGE_OPTIONS contains English with code en`() {
        val english = LANGUAGE_OPTIONS.find { it.code == "en" }
        assertNotNull("Expected English option", english)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Italian with code it`() {
        val italian = LANGUAGE_OPTIONS.find { it.code == "it" }
        assertNotNull("Expected Italian option", italian)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains German with code de`() {
        val german = LANGUAGE_OPTIONS.find { it.code == "de" }
        assertNotNull("Expected German option", german)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Spanish with code es`() {
        val spanish = LANGUAGE_OPTIONS.find { it.code == "es" }
        assertNotNull("Expected Spanish option", spanish)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains French with code fr`() {
        val french = LANGUAGE_OPTIONS.find { it.code == "fr" }
        assertNotNull("Expected French option", french)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Arabic with code ar`() {
        val arabic = LANGUAGE_OPTIONS.find { it.code == "ar" }
        assertNotNull("Expected Arabic option", arabic)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Portuguese with code pt`() {
        val portuguese = LANGUAGE_OPTIONS.find { it.code == "pt" }
        assertNotNull("Expected Portuguese option", portuguese)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Russian with code ru`() {
        val russian = LANGUAGE_OPTIONS.find { it.code == "ru" }
        assertNotNull("Expected Russian option", russian)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Chinese with code zh`() {
        val chinese = LANGUAGE_OPTIONS.find { it.code == "zh" }
        assertNotNull("Expected Chinese option", chinese)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Hindi with code hi`() {
        val hindi = LANGUAGE_OPTIONS.find { it.code == "hi" }
        assertNotNull("Expected Hindi option", hindi)
    }

    @Test
    fun `LANGUAGE_OPTIONS contains Korean with code ko`() {
        val korean = LANGUAGE_OPTIONS.find { it.code == "ko" }
        assertNotNull("Expected Korean option", korean)
    }

    // ── BCP-47 format ─────────────────────────────────────────────────────────

    @Test
    fun `all language codes are valid BCP-47 two-letter codes`() {
        val bcp47Pattern = Regex("^[a-z]{2,3}(-[A-Z]{2})?$")
        LANGUAGE_OPTIONS.forEach { option ->
            assertTrue(
                "Code '${option.code}' does not match BCP-47 pattern",
                bcp47Pattern.matches(option.code),
            )
        }
    }

    // ── English is first ──────────────────────────────────────────────────────

    @Test
    fun `English is the first option in the list`() {
        assertEquals("en", LANGUAGE_OPTIONS.first().code)
    }

    // ── Data class equality ───────────────────────────────────────────────────

    @Test
    fun `LanguageOption data class equality works correctly`() {
        val opt1 = LanguageOption("en", "🇬🇧 English")
        val opt2 = LanguageOption("en", "🇬🇧 English")
        assertEquals(opt1, opt2)
    }

    @Test
    fun `LanguageOption data class distinguishes different codes`() {
        val opt1 = LanguageOption("en", "English")
        val opt2 = LanguageOption("it", "English")
        assertFalse(opt1 == opt2)
    }
}
