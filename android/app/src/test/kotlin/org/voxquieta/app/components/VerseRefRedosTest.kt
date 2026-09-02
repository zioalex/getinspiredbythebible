package org.voxquieta.app.components

import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.components.DEFAULT_VERSE_REF_REGEX
import org.voxquieta.app.presentation.components.buildVerseRefRegex
import org.voxquieta.app.presentation.components.injectVerseLinks
import org.voxquieta.app.presentation.components.referencedVerses
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.system.measureTimeMillis

// ── ReDoS regression (BITB-114 / Android follow-up to BITB-108) ────────────
//
// ChatMessageItem's BOOK_NAME and VersesPanel's CITED_BOOK_NAME both had a
// multi-word book-name "connector" branch
// (`(?:\s+(?:of|de|des|...)\s+[\p{L}...])*`) with an unbounded `*` on the
// connector-repeat group. That let adversarial input (repeated " of aa"
// segments in chat message text — model output or pasted text) drive Java's
// backtracking regex engine into superlinear-time blowup, mirroring the web
// finding fixed in BITB-108 (frontend/src/lib/versePatterns.ts). Bounding
// both groups to {0,3} closes this without affecting real book names: the
// max connector count found in any supported book name (see
// LocalizedBookToEnglish.kt) is 1 (e.g. "Song of Solomon", "Cantico dei
// Cantici"). {0,3} (not {1,3} — these groups are zero-or-more, not
// one-or-more) keeps 3x headroom over that while eliminating the unbounded
// blowup. See docs/BACKLOG_STORIES/BITB-114-android-verse-parser-redos.md.
//
// These are permanent regression guards: if either bound is ever widened
// back to `*`/`+`, the timing tests should start timing out / blowing their
// budget, and the cap-enforcement tests should start failing.
class VerseRefRedosTest {

    // ── Timing: adversarial 'of'-chain input stays fast ─────────────────────

    @Test(timeout = 5000)
    fun `DEFAULT_VERSE_REF_REGEX matches an adversarial 'of'-chain within budget`() {
        // ~120,000 chars — large enough to clearly separate O(n) from
        // O(n^2)/superlinear behaviour, but still fast to run under the fix.
        val input = "aa" + " of aa".repeat(20000) + "!"
        val elapsed = measureTimeMillis {
            DEFAULT_VERSE_REF_REGEX.findAll(input).count()
        }
        // Not asserting on match content: this adversarial nonsense text has no trailing
        // chapter:verse digits, so it never matches at all. Only timing matters here — with
        // the bounded connector group this completes in low tens of ms; with the old
        // unbounded `*` it degraded into superlinear blowup, so a generous 500ms budget still
        // clearly catches a regression.
        assertTrue("expected < 500ms, was ${elapsed}ms", elapsed < 500)
    }

    @Test(timeout = 5000)
    fun `buildVerseRefRegex generic fallback matches an adversarial 'of'-chain within budget`() {
        // A non-empty multiWordNames list forces the dynamic (non-default) regex-building
        // path, which embeds the same BOOK_NAME connector group three more times. The
        // adversarial input below doesn't match the explicit multi-word name, so it exercises
        // the generic fallback branch (genericBookName) instead.
        val regex = buildVerseRefRegex(multiWordNames = listOf("First Samuel"))
        val input = "aa" + " of aa".repeat(20000) + "!"
        val elapsed = measureTimeMillis {
            regex.findAll(input).count()
        }
        assertTrue("expected < 500ms, was ${elapsed}ms", elapsed < 500)
    }

    @Test(timeout = 5000)
    fun `referencedVerses matches an adversarial 'of'-chain assistant message within budget`() {
        val input = "aa" + " of aa".repeat(20000) + "!"
        val messages = listOf(Message(id = "1", role = Message.Role.ASSISTANT, content = input))
        val elapsed = measureTimeMillis {
            referencedVerses(allVerses = emptyList(), messages = messages)
        }
        assertTrue("expected < 500ms, was ${elapsed}ms", elapsed < 500)
    }

    // ── Connector-repeat cap ({0,3}) is enforced, not just documented ───────
    //
    // These don't, on their own, prove the bound is doing the work if tested only against
    // real book names (those resolve via other means regardless of the bound). Instead they
    // exercise the connector branch directly with synthetic (non-book) chained phrases, so
    // they fail if either bound is ever widened back to unbounded.

    @Test
    fun `DEFAULT_VERSE_REF_REGEX refuses a 4th connector repeat from the same start`() {
        val match = DEFAULT_VERSE_REF_REGEX.find("Xylo of Zorp of Quix of Wobble of Nix 3:16")
        checkNotNull(match) { "expected some (shorter) match to still be found" }
        // Alt 2 (no numbered prefix) populates group 4 with the book name.
        val book = match.groupValues[4]
        assertNotEquals(
            "must not capture the full unbounded 5-word chain",
            "Xylo of Zorp of Quix of Wobble of Nix",
            book,
        )
        // The match instead starts one word later, using exactly 3 connector repeats (the
        // cap) from "Zorp" instead of 4 from "Xylo" — that shift in *where the match starts*
        // is the bound in action, same as the web regression test.
        assertEquals("Zorp of Quix of Wobble of Nix", book)
    }

    @Test
    fun `DEFAULT_VERSE_REF_REGEX still allows up to 3 chained connector words`() {
        assertEquals(
            "Xylo of Zorp of Quix of Wobble",
            DEFAULT_VERSE_REF_REGEX.find("Xylo of Zorp of Quix of Wobble 3:16")?.groupValues?.get(4),
        )
    }

    @Test
    fun `referencedVerses connector cap is enforced for CITED_BOOK_NAME`() {
        val chained = "Xylo of Zorp of Quix of Wobble of Nix"
        val trimmed = "Zorp of Quix of Wobble of Nix"
        val message = Message(id = "1", role = Message.Role.ASSISTANT, content = "$chained 3:16")
        val fullChainVerse = Verse(book = chained, chapter = 3, verse = 16, text = "")
        val trimmedVerse = Verse(book = trimmed, chapter = 3, verse = 16, text = "")

        val result = referencedVerses(listOf(fullChainVerse, trimmedVerse), listOf(message))

        assertTrue(
            "the {0,3}-capped match should surface the trimmed-suffix verse",
            result.contains(trimmedVerse),
        )
        assertTrue(
            "the full unbounded chain must not be captured as a single book name",
            !result.contains(fullChainVerse),
        )
    }

    // ── Legitimate multi-connector book names still match after the {0,3} bound ─

    @Test
    fun `injectVerseLinks still wraps a real multi-word book name with a connector`() {
        val result = injectVerseLinks("Song of Solomon 2:1 speaks of love.")
        assertTrue(result.contains("[Song of Solomon 2:1]"))
    }

    @Test
    fun `referencedVerses still matches a real multi-word book name with a connector`() {
        val verse = Verse(book = "Song of Solomon", chapter = 1, verse = 1, text = "")
        val message = Message(
            id = "1",
            role = Message.Role.ASSISTANT,
            content = "Song of Solomon 1:1 is beautiful",
        )
        assertTrue(referencedVerses(listOf(verse), listOf(message)).contains(verse))
    }
}
