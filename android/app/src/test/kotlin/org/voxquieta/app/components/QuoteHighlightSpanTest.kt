package org.voxquieta.app.components

import android.text.SpannableString
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.text.style.ReplacementSpan
import android.text.style.StyleSpan
import android.text.style.TypefaceSpan
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.voxquieta.app.presentation.components.applyQuoteHighlights

/**
 * Tests for [applyQuoteHighlights].
 *
 * The previous implementation used a custom [ReplacementSpan], which the platform treats as
 * one atomic, unbreakable glyph — so a long quote could not wrap and was clipped at the
 * bubble's right edge (the "cut text" bug). These tests assert the replacement uses standard
 * inline spans that the text engine lays out and wraps, and that NO [ReplacementSpan] is
 * applied. Robolectric provides the real `android.text` span classes.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], application = android.app.Application::class)
class QuoteHighlightSpanTest {

    private fun spansOf(text: String): SpannableString {
        val s = SpannableString(text)
        applyQuoteHighlights(s)
        return s
    }

    @Test
    fun `applies wrappable inline spans over a quoted passage`() {
        val s = spansOf("Er sagte: \"Selig sind die Barmherzigen\" heute.")
        val spans = s.getSpans(0, s.length, Any::class.java)
        assertTrue("expected a background span", spans.any { it is BackgroundColorSpan })
        assertTrue("expected a foreground span", spans.any { it is ForegroundColorSpan })
        assertTrue("expected an italic style span", spans.any { it is StyleSpan })
        assertTrue("expected a serif typeface span", spans.any { it is TypefaceSpan })
    }

    @Test
    fun `does not apply any ReplacementSpan (so long quotes can wrap)`() {
        val long = "\"" + "Selig sind die Barmherzigen, denn sie werden Barmherzigkeit " +
            "erlangen und sollen getröstet werden in Ewigkeit" + "\""
        val s = spansOf("Wie geschrieben steht: $long und so weiter.")
        val replacementSpans = s.getSpans(0, s.length, ReplacementSpan::class.java)
        assertEquals("no ReplacementSpan must be used", 0, replacementSpans.size)
    }

    @Test
    fun `spans cover only the quoted range, not surrounding prose`() {
        val text = "Er sagte: \"Selig sind die Barmherzigen\" heute."
        val s = spansOf(text)
        val bg = s.getSpans(0, s.length, BackgroundColorSpan::class.java)
        assertEquals(1, bg.size)
        val start = s.getSpanStart(bg[0])
        val end = s.getSpanEnd(bg[0])
        assertEquals(text.indexOf('"'), start)
        assertEquals(text.lastIndexOf('"') + 1, end)
    }

    @Test
    fun `highlights German low-high quotes`() {
        // „ … " (U+201E … U+201D)
        val s = spansOf("Es steht: „Denn so hat Gott die Welt geliebt”.")
        assertTrue(
            s.getSpans(0, s.length, BackgroundColorSpan::class.java).isNotEmpty(),
        )
    }

    @Test
    fun `highlights guillemet quotes`() {
        // « … » (French/other) — U+00AB … U+00BB
        val s = spansOf("Il dit «Car Dieu a tant aimé le monde».")
        assertTrue(
            s.getSpans(0, s.length, BackgroundColorSpan::class.java).isNotEmpty(),
        )
    }

    @Test
    fun `applies independent span sets to multiple quotes`() {
        val s = spansOf("\"first quote here\" and \"second quote here\"")
        assertEquals(2, s.getSpans(0, s.length, BackgroundColorSpan::class.java).size)
    }

    @Test
    fun `leaves prose without quotes untouched`() {
        val s = spansOf("Gott ist die Liebe und es gibt keine Furcht.")
        assertEquals(0, s.getSpans(0, s.length, Any::class.java).size)
    }

    @Test
    fun `highlights CJK corner-bracket quotes`() {
        // 「 … 」 — U+300C … U+300D
        val s = spansOf("彼は言った「神は世を愛された」")
        assertTrue(
            s.getSpans(0, s.length, BackgroundColorSpan::class.java).isNotEmpty(),
        )
    }

    @Test
    fun `highlights double CJK-bracket quotes`() {
        // 《 … 》 — U+300A … U+300B
        val s = spansOf("彼は言った《神は世を愛された》")
        assertTrue(
            s.getSpans(0, s.length, BackgroundColorSpan::class.java).isNotEmpty(),
        )
    }

    @Test
    fun `does not highlight across a newline`() {
        // A quote opener and closer separated by a newline must not be highlighted —
        // the amber span must stay within a single paragraph.
        val s = spansOf("He said \"For God so loved the world\nand gave his only Son\"")
        assertEquals(
            "a quote spanning a paragraph break must not be highlighted",
            0,
            s.getSpans(0, s.length, BackgroundColorSpan::class.java).size,
        )
    }

    @Test
    fun `applies the exact amber background and dark-amber foreground colors`() {
        // Guards the hardcoded web-parity colors: bg-amber-50 background, amber-900 text.
        val s = spansOf("Er sagte: \"Selig sind die Barmherzigen\" heute.")
        val bg = s.getSpans(0, s.length, BackgroundColorSpan::class.java)
        val fg = s.getSpans(0, s.length, ForegroundColorSpan::class.java)
        assertEquals(1, bg.size)
        assertEquals(1, fg.size)
        assertEquals(0xFFFFFBEB.toInt(), bg[0].backgroundColor)
        assertEquals(0xFF78350F.toInt(), fg[0].foregroundColor)
    }

    @Test
    fun `applies an italic serif typeface over the quote`() {
        // Guards the StyleSpan(ITALIC) + TypefaceSpan("serif") web-parity styling.
        val s = spansOf("Er sagte: \"Selig sind die Barmherzigen\" heute.")
        val style = s.getSpans(0, s.length, StyleSpan::class.java)
        val face = s.getSpans(0, s.length, TypefaceSpan::class.java)
        assertEquals(1, style.size)
        assertEquals(android.graphics.Typeface.ITALIC, style[0].style)
        assertEquals(1, face.size)
        assertEquals("serif", face[0].family)
    }

    @Test
    fun `all four span types cover the identical quoted range`() {
        // The existing range test only checks BackgroundColorSpan; lock the other three
        // to the same start/end so styling can never drift apart from the highlight.
        val text = "Er sagte: \"Selig sind die Barmherzigen\" heute."
        val s = spansOf(text)
        val expectedStart = text.indexOf('"')
        val expectedEnd = text.lastIndexOf('"') + 1
        listOf(
            BackgroundColorSpan::class.java,
            ForegroundColorSpan::class.java,
            StyleSpan::class.java,
            TypefaceSpan::class.java,
        ).forEach { type ->
            val span = s.getSpans(0, s.length, type).single()
            assertEquals(expectedStart, s.getSpanStart(span))
            assertEquals(expectedEnd, s.getSpanEnd(span))
        }
    }

    @Test
    fun `does not highlight quotes shorter than three content chars`() {
        // Mirrors the {3,} minimum in QUOTE_HIGHLIGHT_REGEX at the span-application layer.
        val s = spansOf("He replied \"Hi\" and left.")
        assertEquals(0, s.getSpans(0, s.length, BackgroundColorSpan::class.java).size)
    }

    @Test
    fun `applies a full independent span set to each of multiple quotes`() {
        // Existing multi-quote test asserts only the background count; extend to all four
        // styling spans so a second quote is never partially styled.
        val s = spansOf("\"first quote here\" and \"second quote here\"")
        assertEquals(2, s.getSpans(0, s.length, BackgroundColorSpan::class.java).size)
        assertEquals(2, s.getSpans(0, s.length, ForegroundColorSpan::class.java).size)
        assertEquals(2, s.getSpans(0, s.length, StyleSpan::class.java).size)
        assertEquals(2, s.getSpans(0, s.length, TypefaceSpan::class.java).size)
    }
}
