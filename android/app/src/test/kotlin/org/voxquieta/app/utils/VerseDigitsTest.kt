package org.voxquieta.app.utils

import org.junit.Assert.assertEquals
import org.junit.Test

/** Unit tests for the ASCII normalisation helpers in VerseDigits.kt (BITB-179). */
class VerseDigitsTest {

    @Test
    fun `normalizeVerseDigits maps every digit of every grammar range to ASCII`() {
        for (range in VerseGrammar.NON_ASCII_DIGIT_RANGES) {
            val written = (range.start..range.end).joinToString("")
            assertEquals(range.label, "0123456789", normalizeVerseDigits(written))
        }
    }

    @Test
    fun `normalizeVerseDigits handles fullwidth, Devanagari and Eastern Arabic digits`() {
        assertEquals("3", normalizeVerseDigits("３"))
        assertEquals("16", normalizeVerseDigits("१६"))
        assertEquals("28", normalizeVerseDigits("٢٨"))
    }

    @Test
    fun `normalizeVerseDigits leaves ASCII and other characters unchanged`() {
        assertEquals("John 3:16", normalizeVerseDigits("John 3:16"))
        assertEquals("约翰福音3：16", normalizeVerseDigits("约翰福音3：16"))
    }

    @Test
    fun `normalizeRangeSeparators maps every range separator to a hyphen`() {
        for (sep in VerseGrammar.RANGE_SEPARATORS) {
            assertEquals("3-12", normalizeRangeSeparators("3${sep}12"))
        }
    }

    @Test
    fun `normalizeRangeSeparators leaves a plain number unchanged`() {
        assertEquals("16", normalizeRangeSeparators("16"))
    }
}
