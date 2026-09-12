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

    @Test(timeout = 5000)
    fun `ChatMessageItem numbered-prefix branch handles adversarial trailing words within budget`() {
        // The leading "1 " forces Alt 1. Its trailing-word repeat group is now bounded to
        // {0,3} by BITB-117 (was unbounded `*`, flagged as residual risk by BITB-114) — this
        // is a genuine adversarial benchmark at the same scale as the connector-group tests
        // above, not just a small sanity check.
        val input = "1 Aa" + " Aa".repeat(20000) + "!"
        val elapsed = measureTimeMillis {
            DEFAULT_VERSE_REF_REGEX.findAll(input).count()
        }
        assertTrue("expected < 500ms, was ${elapsed}ms", elapsed < 500)
    }

    @Test(timeout = 5000)
    fun `VersesPanel numbered-prefix branch handles adversarial trailing words within budget`() {
        val input = "1 Aa" + " Aa".repeat(20000) + "!"
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

    // ── Alt-1 numbered-prefix trailing-word cap ({0,3}) is enforced (BITB-117) ──────
    //
    // Mirrors the connector-cap tests above, but for the *other* group BITB-114 flagged as
    // residual: the Alt-1 numbered-prefix trailing-word group (after $BOOK_NAME / after
    // $CITED_BOOK_NAME), now also bounded to {0,3}. Traced against both the Kotlin regex
    // semantics and a Node.js cross-check (Unicode-property-escape regex, `u` flag) before
    // writing these assertions.

    @Test
    fun `DEFAULT_VERSE_REF_REGEX refuses a 4th Alt-1 trailing word from the same start`() {
        val match = DEFAULT_VERSE_REF_REGEX.find("1 Xylo Zorp Quix Wobble Nix 3:16")
        checkNotNull(match) { "expected some (shorter) match to still be found" }
        // 4 trailing words after "Xylo" (Zorp, Quix, Wobble, Nix) is one over the {0,3} cap,
        // so Alt 1 cannot match the whole numbered-prefix phrase under any backtrack split.
        // The overall match instead falls through to Alt 2, which picks up just "Nix 3:16"
        // ("Nix" alone qualifies as a BOOK_NAME) -- proving the earlier words were NOT
        // absorbed into one unbounded Alt-1 match.
        assertEquals("Nix 3:16", match.value)
        assertEquals("Nix", match.groupValues[4])
    }

    @Test
    fun `DEFAULT_VERSE_REF_REGEX still allows exactly 3 chained Alt-1 trailing words`() {
        assertEquals(
            "1 Xylo Zorp Quix Wobble",
            DEFAULT_VERSE_REF_REGEX.find("1 Xylo Zorp Quix Wobble 3:16")?.groupValues?.get(1),
        )
    }

    @Test
    fun `referencedVerses Alt-1 trailing-word cap is enforced for CITED_BOOK_NAME`() {
        // CITED_BOOK_NAME requires each word to start with an uppercase/caseless letter
        // (\p{Lu}\p{Lo}), so use word-initial-capital synthetic words. VersesPanel's Alt-1
        // prefix separator is `[\s.][\s]?` (less flexible than ChatMessageItem's), but a
        // plain "1 " still satisfies it.
        val message = Message(
            id = "1",
            role = Message.Role.ASSISTANT,
            content = "1 Xylo Zorp Quix Wobble Nix 3:16",
        )
        val fullChainVerse =
            Verse(book = "1 Xylo Zorp Quix Wobble Nix", chapter = 3, verse = 16, text = "")
        val trimmedVerse = Verse(book = "Nix", chapter = 3, verse = 16, text = "")

        val result = referencedVerses(listOf(fullChainVerse, trimmedVerse), listOf(message))

        assertTrue(
            "the {0,3}-capped Alt-1 match should fall through to Alt-2's trimmed book name",
            result.contains(trimmedVerse),
        )
        assertTrue(
            "the full 4-trailing-word chain must not be captured as a single Alt-1 match",
            !result.contains(fullChainVerse),
        )
    }

    @Test
    fun `referencedVerses still allows exactly 3 chained Alt-1 trailing words for CITED_BOOK_NAME`() {
        val verse = Verse(book = "1 Xylo Zorp Quix Wobble", chapter = 3, verse = 16, text = "")
        val message = Message(
            id = "1",
            role = Message.Role.ASSISTANT,
            content = "1 Xylo Zorp Quix Wobble 3:16",
        )
        assertTrue(referencedVerses(listOf(verse), listOf(message)).contains(verse))
    }

    // ── Real numbered multi-word names still match after the BITB-117 bound ─────────

    @Test
    fun `referencedVerses matches real numbered multi-word Arabic book name after the BITB-117 bound`() {
        // "1 أخبار الأيام" = "1 Chronicles": "أخبار" is matched by CITED_BOOK_NAME, "الأيام"
        // is the one trailing word the {0,3}-bounded group must still match.
        val verse = Verse(book = "1 أخبار الأيام", chapter = 1, verse = 1, text = "")
        val message = Message(
            id = "1",
            role = Message.Role.ASSISTANT,
            content = "1 أخبار الأيام 1:1 يقول كذا",
        )
        assertTrue(referencedVerses(listOf(verse), listOf(message)).contains(verse))
    }

    @Test
    fun `injectVerseLinks still wraps a real numbered multi-word Arabic book name after the BITB-117 bound`() {
        val result = injectVerseLinks("1 أخبار الأيام 1:1 يقول كذا")
        assertTrue(result.contains("[1 أخبار الأيام 1:1]"))
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

    @Test
    fun `injectVerseLinks preserves supported multilingual connector book names`() {
        val references = listOf(
            "Cantico dei Cantici 2:1",
            "Cantique des Cantiques 2:1",
            "Cântico dos Cânticos 2:1",
            "प्रेरितों के काम 2:1",
        )

        references.forEach { reference ->
            assertTrue(
                "expected $reference to be linked",
                injectVerseLinks(reference).contains("[$reference]"),
            )
        }
    }

    @Test
    fun `referencedVerses preserves supported multilingual connector book names`() {
        val cases = listOf(
            Triple("Cantico dei Cantici", "Song of Solomon", "Italian"),
            Triple("Cantique des Cantiques", "Song of Solomon", "French"),
            Triple("Cântico dos Cânticos", "Song of Solomon", "Portuguese"),
        )

        cases.forEach { (localizedBook, canonicalBook, language) ->
            val verse = Verse(book = canonicalBook, chapter = 2, verse = 1, text = "")
            val message = Message(
                id = language,
                role = Message.Role.ASSISTANT,
                content = "$localizedBook 2:1",
            )
            assertTrue(
                "expected $language connector book to remain referenced",
                referencedVerses(listOf(verse), listOf(message)).contains(verse),
            )
        }
    }
}
