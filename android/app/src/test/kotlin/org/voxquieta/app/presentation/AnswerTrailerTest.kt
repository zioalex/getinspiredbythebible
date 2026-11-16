package org.voxquieta.app.presentation

import org.junit.Assert.assertEquals
import org.junit.Test
import org.voxquieta.app.presentation.viewmodels.stripAnswerTrailer

/** BITB-320: a leaked machine trailer must never be shown when finalize fails. */
class AnswerTrailerTest {

    @Test
    fun `plain text is unchanged`() {
        assertEquals("God is near (John 3:16).", stripAnswerTrailer("God is near (John 3:16)."))
    }

    @Test
    fun `complete verses trailer is stripped`() {
        assertEquals(
            "Peace be with you.",
            stripAnswerTrailer("Peace be with you.\n<!-- VERSES: John 14:27; Psalm 23:1 -->"),
        )
    }

    @Test
    fun `verses and followups trailers are both stripped`() {
        assertEquals(
            "Peace.",
            stripAnswerTrailer("Peace.\n<!-- VERSES: John 14:27 -->\n<!-- FOLLOWUPS: a|b|c -->"),
        )
    }

    @Test
    fun `half received followups trailer is stripped`() {
        assertEquals("Peace.", stripAnswerTrailer("Peace.\n<!-- FOLLOWUPS: What does this me"))
    }

    @Test
    fun `partial comment opener at the end is stripped`() {
        assertEquals("Peace.", stripAnswerTrailer("Peace.\n<!--"))
        assertEquals("Peace.", stripAnswerTrailer("Peace. <!-"))
        assertEquals("Peace.", stripAnswerTrailer("Peace. <!"))
    }

    @Test
    fun `non-ASCII text with a trailer keeps the text`() {
        assertEquals(
            "神爱世人（约翰福音3:16）。",
            stripAnswerTrailer("神爱世人（约翰福音3:16）。\n<!-- VERSES: John 3:16 -->"),
        )
        assertEquals(
            "الرب راعيّ.",
            stripAnswerTrailer("الرب راعيّ. <!-- FOLLOWUPS: ماذا تعني؟|لماذا؟ -->"),
        )
    }

    @Test
    fun `an unrelated closed html comment in the middle is kept`() {
        val text = "A <!-- note --> B."
        assertEquals(text, stripAnswerTrailer(text))
    }
}
