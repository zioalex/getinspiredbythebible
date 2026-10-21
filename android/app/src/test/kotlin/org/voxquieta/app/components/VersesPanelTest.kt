package org.voxquieta.app.components

import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
import org.voxquieta.app.presentation.components.referencedVerses
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

class VersesPanelTest {

    private fun assistantMsg(content: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.ASSISTANT,
        content = content,
    )

    private fun userMsg(content: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.USER,
        content = content,
    )

    private fun verse(book: String, chapter: Int, verseNum: Int, translation: String = "kjv") =
        Verse(book = book, chapter = chapter, verse = verseNum, text = "text", translation = translation)

    // ─────────────────────────────────────────────────────────────────────────

    @Test
    fun `referencedVerses returns verse explicitly cited in assistant message`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("See John 3:16 for more context."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses excludes verse not cited in any message`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val messages = listOf(assistantMsg("See John 3:16 for hope."))

        val result = referencedVerses(listOf(john316, psalms23), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses returns empty list when allVerses is empty`() {
        val messages = listOf(assistantMsg("John 3:16 is a great verse."))

        val result = referencedVerses(emptyList(), messages)

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses returns empty list when messages list is empty`() {
        val john316 = verse("John", 3, 16)

        val result = referencedVerses(listOf(john316), emptyList())

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses returns all verses when all are cited`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val genesis11 = verse("Genesis", 1, 1)
        val messages = listOf(
            assistantMsg("As written in John 3:16 and Psalms 23:1, also Genesis 1:1."),
        )

        val result = referencedVerses(listOf(john316, psalms23, genesis11), messages)

        assertEquals(3, result.size)
    }

    @Test
    fun `referencedVerses ignores user messages for citation matching`() {
        val john316 = verse("John", 3, 16)
        // Cite the verse only in a user message — should NOT count as referenced
        val messages = listOf(
            userMsg("Can you explain John 3:16?"),
            assistantMsg("It speaks about God's love for humanity."),
        )

        val result = referencedVerses(listOf(john316), messages)

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses aggregates citations across multiple assistant messages`() {
        val john316 = verse("John", 3, 16)
        val psalms23 = verse("Psalms", 23, 1)
        val messages = listOf(
            assistantMsg("First, consider John 3:16."),
            assistantMsg("Also, Psalms 23:1 brings comfort."),
        )

        val result = referencedVerses(listOf(john316, psalms23), messages)

        assertEquals(2, result.size)
    }

    @Test
    fun `referencedVerses matches verse range reference eg John 3 16-17`() {
        val john316 = verse("John", 3, 16)
        // The regex captures "John 3:16-17"; the cited start verse (3:16) is matched exactly
        val messages = listOf(assistantMsg("Read John 3:16-17 carefully."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
        assertEquals(john316, result[0])
    }

    @Test
    fun `referencedVerses handles book names with numeric prefix`() {
        val firstCor13 = verse("1 Corinthians", 13, 4)
        val messages = listOf(assistantMsg("Love is patient — see 1 Corinthians 13:4."))

        val result = referencedVerses(listOf(firstCor13), messages)

        assertEquals(1, result.size)
        assertEquals(firstCor13, result[0])
    }

    @Test
    fun `referencedVerses does not return duplicates when same verse cited twice in one message`() {
        val john316 = verse("John", 3, 16)
        // Cited twice in a single message; the verse object is in the list once
        val messages = listOf(assistantMsg("John 3:16 is important. Again, John 3:16."))

        val result = referencedVerses(listOf(john316), messages)

        assertEquals(1, result.size)
    }

    // ── Multi-word book names ────────────────────────────────────────────────

    @Test
    fun `referencedVerses matches multi-word book Song of Solomon`() {
        val song21 = verse("Song of Solomon", 2, 1)
        val messages = listOf(assistantMsg("Song of Solomon 2:1 speaks of love."))

        val result = referencedVerses(listOf(song21), messages)

        assertEquals(1, result.size)
        assertEquals(song21, result[0])
    }

    @Test
    fun `referencedVerses matches Song of Solomon with verse range`() {
        val song21 = verse("Song of Solomon", 2, 1)
        val messages = listOf(assistantMsg("Read Song of Solomon 2:1-5 for the wedding."))

        val result = referencedVerses(listOf(song21), messages)

        assertEquals(1, result.size)
    }

    // ── Non-Latin book names ─────────────────────────────────────────────────
    // NOTE: referencedVerses compares the regex-extracted book name (from the message)
    // against Verse.book (the backend's English name). Cross-language matching
    // (e.g. "Johannes" vs "John") is not supported — those tests are intentionally
    // omitted. These tests verify that the regex correctly extracts the citation
    // from non-Latin text, using the SAME book name in both the message and the verse.

    @Test
    fun `referencedVerses matches same-language citation with Unicode book name`() {
        // When the verse.book matches the localized name in the message, it works.
        val verse = verse("Иоанн", 3, 16)
        val messages = listOf(assistantMsg("читайте Иоанн 3:16 для вдохновения."))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
        assertEquals(verse, result[0])
    }

    @Test
    fun `referencedVerses matches CJK book name when verse book matches`() {
        val verse = verse("约翰福音", 3, 16)
        val messages = listOf(assistantMsg("约翰福音 3:16是著名的经文。"))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Traditional Chinese book name via the Simplified-keyed API map (BITB-110)`() {
        // The regex-extracted rawBook is Traditional ("約翰福音"); localizedToEnglish is
        // keyed Simplified only ("约翰福音"), as the backend always returns it. A direct lookup
        // misses, so referencedVerses must retry the normalized (Simplified) form to resolve
        // "John" and match verse.book.
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("約翰福音 3:16是著名的经文。"))

        val result = referencedVerses(
            listOf(john316),
            messages,
            localizedToEnglish = mapOf("约翰福音" to "John"),
        )

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches mixed-script Chinese book name (Traditional 創 plus Simplified 世记, BITB-110)`() {
        val genesis11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("創世记 1:1是起始。"))

        val result = referencedVerses(
            listOf(genesis11),
            messages,
            localizedToEnglish = mapOf("创世记" to "Genesis"),
        )

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches Traditional Chinese from bundled map when API map is empty`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("約翰福音 3:16是著名的經文。"))

        val result = referencedVerses(listOf(john316), messages, localizedToEnglish = emptyMap())

        assertEquals(listOf(john316), result)
    }

    @Test
    fun `referencedVerses matches mixed-script Chinese from bundled map when API map is empty`() {
        val genesis11 = verse("Genesis", 1, 1)
        val messages = listOf(assistantMsg("創世记 1:1是起始。"))

        val result = referencedVerses(listOf(genesis11), messages, localizedToEnglish = emptyMap())

        assertEquals(listOf(genesis11), result)
    }

    @Test
    fun `referencedVerses matches Korean book name when verse book matches`() {
        val verse = verse("요한복음", 3, 16)
        val messages = listOf(assistantMsg("요한복음 3:16은 유명한 구절입니다."))

        val result = referencedVerses(listOf(verse), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German book with umlaut when verse book matches`() {
        val rom828 = verse("Römer", 8, 28)
        val messages = listOf(assistantMsg("Römer 8:28 ist ein wichtiger Vers."))

        val result = referencedVerses(listOf(rom828), messages)

        assertEquals(1, result.size)
    }

    @Test
    fun `referencedVerses matches German numbered book 1 Mose with period`() {
        val gen11 = verse("1. Mose", 1, 1)
        val messages = listOf(assistantMsg("am Anfang steht 1. Mose 1:1."))

        val result = referencedVerses(listOf(gen11), messages)

        assertEquals(1, result.size)
    }

    // ── Edge cases ──────────────────────────────────────────────────────────

    @Test
    fun `referencedVerses does not match chapter-verse without book name`() {
        val john316 = verse("John", 3, 16)
        val messages = listOf(assistantMsg("Verse 3:16 is well known."))

        val result = referencedVerses(listOf(john316), messages)

        // "Verse 3:16" should NOT match — no valid book name before "3:16"
        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses matches mixed-language message with same-lang verse names`() {
        val john316 = verse("John", 3, 16)
        val rom828 = verse("Römer", 8, 28)
        // Message mixes English and German; verse names match the respective language
        val messages = listOf(assistantMsg("John 3:16 und Römer 8:28 sind wichtige Verse."))

        val result = referencedVerses(listOf(john316, rom828), messages)

        assertEquals(2, result.size)
    }

    // ── Shared-grammar cross-language coverage (BITB-164) ───────────────────

    /** (language, text, canonical English book, chapter, first verse). */
    private data class CitedCase(
        val lang: String,
        val text: String,
        val book: String,
        val chapter: Int,
        val verse: Int,
    )

    private val crossLanguageCases = listOf(
        CitedCase("en", "(John 3:16)", "John", 3, 16),
        CitedCase("en", "Romans 8:28\u201330", "Romans", 8, 28),
        CitedCase("it", "Giovanni 3,16", "John", 3, 16),
        CitedCase("it", "Cantico dei Cantici 2:1", "Song of Solomon", 2, 1),
        CitedCase("de", "R\u00f6mer 13,1\u20132", "Romans", 13, 1),
        CitedCase("de", "1. Mose 1:1", "Genesis", 1, 1),
        CitedCase("es", "[Juan 3:16]", "John", 3, 16),
        CitedCase("fr", "Jean 3,16", "John", 3, 16),
        CitedCase("pt", "Jo\u00e3o 3:16", "John", 3, 16),
        CitedCase("pt", "C\u00e2ntico dos C\u00e2nticos 2:1", "Song of Solomon", 2, 1),
        CitedCase("ar", "\u064a\u0648\u062d\u0646\u0627 \u0663:\u0661\u0666", "John", 3, 16),
        CitedCase("ar", "1 \u0623\u062e\u0628\u0627\u0631 \u0627\u0644\u0623\u064a\u0627\u0645 1:1", "1 Chronicles", 1, 1),
        CitedCase("ru", "\u0418\u043e\u0430\u043d\u043d\u0430 3:16", "John", 3, 16),
        CitedCase("ru", "1-\u0435 \u041a\u043e\u0440\u0438\u043d\u0444\u044f\u043d\u0430\u043c 13:4", "1 Corinthians", 13, 4),
        CitedCase("zh", "\u300a\u7ea6\u7ff0\u798f\u97f3\u300b3:16", "John", 3, 16),
        CitedCase("zh", "\uff08\u7ea6\u7ff0\u798f\u97f3 3:16\uff09", "John", 3, 16),
        CitedCase("zh", "\u8bf7\u9605\u8bfb\u7ea6\u7ff0\u798f\u97f310:28\u6765\u83b7\u5f97\u9f13\u52b1", "John", 10, 28),
        CitedCase("hi", "\u092f\u0942\u0939\u0928\u094d\u0928\u093e \u096b:\u0968\u096a", "John", 5, 24),
        CitedCase("hi", "\u0930\u094b\u092e\u093f\u092f\u094b\u0902 12:1-2", "Romans", 12, 1),
        CitedCase("ko", "\u300c\uc694\ud55c\ubcf5\uc74c\u300d3:16", "John", 3, 16),
        CitedCase("ko", "\uc694\ud55c\ubcf5\uc74c3:16", "John", 3, 16),
    )

    @Test
    fun `referencedVerses resolves cited references in all 11 languages via the shared grammar`() {
        val languages = setOf("en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko")
        assertEquals(languages, crossLanguageCases.map { it.lang }.toSet())

        val failures = mutableListOf<String>()
        for (c in crossLanguageCases) {
            val target = verse(c.book, c.chapter, c.verse)
            // Same-book, same-chapter "prefix" distractor (e.g. John 3:1 for a John 3:16 cite):
            // the old startsWith matching wrongly surfaced it.
            val distractorVerse = if (c.verse >= 10) c.verse / 10 else c.verse * 10 + 1
            val distractor = verse(c.book, c.chapter, distractorVerse)
            val msgs = listOf(assistantMsg("${c.text} \u2014 text"))
            val result = referencedVerses(listOf(distractor, target), msgs, emptyMap())
            if (result != listOf(target)) {
                failures += "[${c.lang}] '${c.text}': expected [$target], got $result"
            }
        }
        assertTrue("Cross-language mismatches:\n" + failures.joinToString("\n"), failures.isEmpty())
    }

    @Test
    fun `referencedVerses is version-faithful - matches on reference not on verse text or translation`() {
        val kjv = Verse(book = "John", chapter = 3, verse = 16, text = "kjv text", translation = "kjv")
        val web = Verse(book = "John", chapter = 3, verse = 16, text = "web text", translation = "web")

        assertEquals(listOf(kjv), referencedVerses(listOf(kjv), listOf(assistantMsg("John 3:16"))))
        assertEquals(listOf(web), referencedVerses(listOf(web), listOf(assistantMsg("John 3:16"))))
    }

    @Test
    fun `referencedVerses cited John 3-16 does not surface John 3-1`() {
        val john31 = verse("John", 3, 1)
        val john316 = verse("John", 3, 16)

        val result = referencedVerses(listOf(john31, john316), listOf(assistantMsg("John 3:16")))

        assertEquals(listOf(john316), result)
    }

    @Test
    fun `referencedVerses ignores German decimal-like numbers`() {
        val john350 = verse("John", 3, 50)

        val result = referencedVerses(listOf(john350), listOf(assistantMsg("Ich habe 3,50 Euro")))

        assertTrue(result.isEmpty())
    }

    @Test
    fun `referencedVerses does not duplicate verses and keeps input order`() {
        val john316 = verse("John", 3, 16)
        val rom828 = verse("Romans", 8, 28)

        val result = referencedVerses(
            listOf(rom828, john316),
            listOf(assistantMsg("John 3:16, Romans 8:28 and again John 3:16")),
        )

        assertEquals(listOf(rom828, john316), result)
    }

    @Test
    fun `referencedVerses recovers a reference hidden inside a greedy over-match`() {
        val psalm569 = verse("Psalms", 56, 9)

        val result = referencedVerses(listOf(psalm569), listOf(assistantMsg("trust you of Psalm 56:9")))

        // "Psalm" is the singular alias for Psalms in the bundled map.
        assertEquals(listOf(psalm569), result)
    }

    @Test
    fun `referencedVerses does not rewind a numbered-book citation into its unnumbered suffix`() {
        // Only John 3:16 is in allVerses; the message cites 1 John 3:16. The rewind must not
        // re-match the "John 3:16" suffix of a real (known) book name -- in any language.
        val john316 = verse("John", 3, 16)
        for (text in listOf("As 1 John 3:16 says", "Wie 1. Johannes 3:16 sagt", "Come dice 1 Giovanni 3:16")) {
            assertTrue(text, referencedVerses(listOf(john316), listOf(assistantMsg(text))).isEmpty())
        }
    }

    // ── Server versesCited path (BITB-166: exact match, not startsWith) ─────

    private fun citedMsg(vararg cited: String) = Message(
        id = UUID.randomUUID().toString(),
        role = Message.Role.ASSISTANT,
        content = "ignored when versesCited present",
        versesCited = cited.toList(),
    )

    @Test
    fun `referencedVerses server path John 3 16 excludes 3 1 and 3 160`() {
        val all = listOf(verse("John", 3, 1), verse("John", 3, 16), verse("John", 3, 160))

        val result = referencedVerses(all, listOf(citedMsg("John 3:16")))

        assertEquals(listOf(16), result.map { it.verse })
    }

    @Test
    fun `referencedVerses server path range matches every verse inside it`() {
        val all = listOf(verse("Romans", 8, 2), verse("Romans", 8, 28), verse("Romans", 8, 30), verse("Romans", 8, 31))

        val result = referencedVerses(all, listOf(citedMsg("Romans 8:28-30")))

        assertEquals(listOf(28, 30), result.map { it.verse })
    }

    @Test
    fun `referencedVerses server path ignores unparseable citations`() {
        val all = listOf(verse("John", 3, 16))

        assertTrue(referencedVerses(all, listOf(citedMsg("John 3"))).isEmpty())
    }
}
