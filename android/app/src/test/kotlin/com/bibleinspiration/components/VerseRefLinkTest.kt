package com.bibleinspiration.components

import com.bibleinspiration.presentation.components.buildVerseRefRegex
import com.bibleinspiration.presentation.components.handleVerseLink
import com.bibleinspiration.presentation.components.injectVerseLinks
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Test

class VerseRefLinkTest {

    // ── injectVerseLinks ──────────────────────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps simple verse reference`() {
        val input = "As Jesus said in John 3:16, God so loved the world."
        val result = injectVerseLinks(input)
        assertTrue("should contain markdown link", result.contains("[John 3:16](verse://John/3/16)"))
        assertTrue("should not contain bare ref", !result.contains("in John 3:16,"))
    }

    @Test
    fun `injectVerseLinks wraps numbered book reference`() {
        val input = "See 1 Corinthians 13:4 for love."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1 Corinthians 13:4]"))
        assertTrue(result.contains("verse://1+Corinthians/13/4") || result.contains("verse://1%20Corinthians/13/4"))
    }

    @Test
    fun `injectVerseLinks wraps verse range reference`() {
        val input = "Romans 8:38-39 tells us nothing can separate us."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Romans 8:38-39]"))
    }

    @Test
    fun `injectVerseLinks leaves plain text unchanged when no verse refs present`() {
        val input = "God is love."
        val result = injectVerseLinks(input)
        assertEquals(input, result)
    }

    @Test
    fun `injectVerseLinks does not double-link already linked verse refs`() {
        val input = "[John 3:16](verse://John/3/16)"
        val result = injectVerseLinks(input)
        // Should remain unchanged — the negative look-behind prevents re-wrapping
        assertEquals(input, result)
    }

    @Test
    fun `injectVerseLinks wraps multiple verse references in one message`() {
        val input = "John 3:16 and Romans 5:8 are key verses."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[John 3:16]"))
        assertTrue(result.contains("[Romans 5:8]"))
    }

    // ── Multi-word book names ────────────────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Song of Solomon`() {
        val input = "Song of Solomon 2:1 speaks of love."
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Song of Solomon 2:1]"))
    }

    @Test
    fun `injectVerseLinks wraps multi-word books with connector words`() {
        // "of" connector — Song of Solomon
        val result1 = injectVerseLinks("Song of Solomon 1:1 is beautiful")
        assertTrue(result1.contains("[Song of Solomon 1:1]"))

        // "de" connector — Portuguese/French books
        val result2 = injectVerseLinks("Livro de Salmos 23:1")
        assertTrue(result2.contains("[Livro de Salmos 23:1]"))
    }

    // ── Non-English book names: German ───────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps German Johannes`() {
        val input = "lies mal Johannes 3:16 für Ermutigung"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Johannes 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps German Römer with umlaut`() {
        val input = "betrachte Römer 8:28"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Römer 8:28]"))
    }

    @Test
    fun `injectVerseLinks wraps German numbered book with period`() {
        val input = "Am Anfang steht 1. Mose 1:1"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1. Mose 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps German book with umlaut and number`() {
        val input = "lese 2. Könige 5:14"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[2. Könige 5:14]"))
    }

    @Test
    fun `injectVerseLinks wraps German Offenbarung`() {
        val input = "Offenbarung 21:4 spricht von neuem Himmel"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Offenbarung 21:4]"))
    }

    // ── Non-English book names: Italian ─────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Italian Giovanni`() {
        val input = "leggi Giovanni 3:16 per incoraggiamento"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Giovanni 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Italian Genesi with accent`() {
        val input = "considera Genesi 1:1"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Genesi 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Italian Salmi`() {
        val input = "Salmi 23:1 è confortante"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Salmi 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Italian Romani`() {
        val input = "Romani 8:28 è un passo importante"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Romani 8:28]"))
    }

    @Test
    fun `injectVerseLinks wraps Italian Apocalisse`() {
        val input = "Apocalisse 21:4 parla di nuova creazione"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Apocalisse 21:4]"))
    }

    // ── Non-English book names: Spanish ──────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Spanish Juan`() {
        val input = "lee Juan 3:16 para aliento"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Juan 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Spanish Génesis with accent`() {
        val input = "Génesis 1:1 es el comienzo"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Génesis 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Spanish Romanos`() {
        val input = "Romanos 8:28 dice que todo coopera"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Romanos 8:28]"))
    }

    @Test
    fun `injectVerseLinks wraps Spanish Apocalipsis`() {
        val input = "Apocalipsis 21:4 habla de nuevo cielo"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Apocalipsis 21:4]"))
    }

    // ── Non-English book names: French ───────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps French Jean`() {
        val input = "lis Jean 3:16 pour encouragement"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Jean 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps French Genèse with accent`() {
        val input = "Genèse 1:1 est le commencement"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Genèse 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps French Romains`() {
        val input = "Romains 8:28 nous encourage"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Romains 8:28]"))
    }

    @Test
    fun `injectVerseLinks wraps French Psaumes`() {
        val input = "Psaumes 23:1 apporte réconfort"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Psaumes 23:1]"))
    }

    // ── Non-English book names: Portuguese ────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Portuguese João with tilde`() {
        val input = "lê João 3:16 para ânimo"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[João 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Portuguese Gênesis with circumflex`() {
        val input = "Gênesis 1:1 é o começo"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Gênesis 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Portuguese Salmos`() {
        val input = "Salmos 23:1 é reconfortante"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Salmos 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Portuguese Apocalipse`() {
        val input = "Apocalipse 21:4 fala de novo céu"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Apocalipse 21:4]"))
    }

    // ── Non-English book names: Russian ──────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Russian single-word book Иоанн`() {
        val input = "читайте Иоанн 3:16"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Иоанн 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Russian Псалтирь`() {
        val input = "Псалтирь 23:1 утешает"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Псалтирь 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Russian two-word book Плач Иеремии second word`() {
        // "Плач Иеремии" has no connector word — only "Иеремии" is captured as book
        // because "Плач" followed by a non-digit word cannot be the full book+chapter pattern.
        val input = "в Плач Иеремии 3:3 написано о страдании"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Иеремии 3:3]"))
    }

    @Test
    fun `injectVerseLinks wraps Russian numbered book`() {
        val input = "1 Коринфянам 13:4 говорит о любви"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1 Коринфянам 13:4]"))
    }

    @Test
    fun `injectVerseLinks wraps Russian Откровение`() {
        val input = "Откровение 21:4 говорит о новом небе"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[Откровение 21:4]"))
    }

    // ── Non-English book names: Chinese (CJK) ─────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Chinese single-character book 约翰`() {
        val input = "约翰福音 3:16是著名的经文"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[约翰福音 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese book 诗篇`() {
        val input = "诗篇 23:1是安慰的经文"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[诗篇 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese 创世记`() {
        val input = "创世记 1:1是起始"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[创世记 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese 耶利米哀歌`() {
        val input = "耶利米哀歌 3:3讲述苦难"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[耶利米哀歌 3:3]"))
    }

    // ── Non-English book names: Korean (Hangul) ─────────────────────────────

    @Test
    fun `injectVerseLinks wraps Korean 요한복음`() {
        val input = "요한복음 3:16은 유명한 구절"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[요한복음 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Korean 시편`() {
        val input = "시편 23:1은 위로의 구절"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[시편 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Korean 창세기`() {
        val input = "창세기 1:1은 시작"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[창세기 1:1]"))
    }

    // ── Non-English book names: Arabic ─────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Arabic single-word book يوحنا`() {
        val input = "كما جاء في يوحنا 3:16 أن الله أحب العالم"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[يوحنا 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Arabic numbered book 1 كورنثوس`() {
        val input = "1 كورنثوس 13:4 عن المحبة"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1 كورنثوس 13:4]"))
    }

    @Test
    fun `injectVerseLinks wraps Arabic Psalms المزامير`() {
        val input = "المزامير 23:1 مزمور الراعي"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[المزامير 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Arabic Revelation الرؤيا`() {
        val input = "الرؤيا 21:4 عن السماء الجديدة"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[الرؤيا 21:4]"))
    }

    // ── Non-English book names: Hindi ────────────────────────────────────────

    @Test
    fun `injectVerseLinks wraps Hindi single-word book यूहन्ना`() {
        val input = "जैसा कि यूहन्ना 3:16 में लिखा है"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[यूहन्ना 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Hindi numbered book 1 कुरिन्थियों`() {
        val input = "1 कुरिन्थियों 13:4 प्रेम के बारे में"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[1 कुरिन्थियों 13:4]"))
    }

    // ── Non-English book names: Arabic/Hindi multi-word with dynamic regex ──

    @Test
    fun `buildVerseRefRegex wraps Arabic multi-word Acts أعمال الرسل`() {
        val regex = com.bibleinspiration.presentation.components.buildVerseRefRegex(
            listOf("أعمال الرسل", "مراثي إرميا", "نشيد الأنشاد")
        )
        val input = "أعمال الرسل 2:38 عن المعمودية"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Arabic Acts", result.contains("[أعمال الرسل 2:38]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Arabic multi-word Lamentations مراثي إرميا`() {
        val regex = com.bibleinspiration.presentation.components.buildVerseRefRegex(
            listOf("أعمال الرسل", "مراثي إرميا")
        )
        val input = "مراثي إرميا 3:22 عن الرحمة"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Arabic Lamentations", result.contains("[مراثي إرميا 3:22]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Hindi multi-word Psalms भजन संहिता`() {
        val regex = com.bibleinspiration.presentation.components.buildVerseRefRegex(
            listOf("भजन संहिता", "प्रेरितों के काम")
        )
        val input = "भजन संहिता 23:1 में राहत है"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Hindi Psalms", result.contains("[भजन संहिता 23:1]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Hindi multi-word Acts प्रेरितों के काम`() {
        val regex = com.bibleinspiration.presentation.components.buildVerseRefRegex(
            listOf("भजन संहिता", "प्रेरितों के काम")
        )
        val input = "प्रेरितों के काम 2:38 बपतिस्मा के बारे में"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Hindi Acts", result.contains("[प्रेरितों के काम 2:38]"))
    }

    // ── Russian Synodal dash-format numbered books ──────────────────────────

    @Test
    fun `injectVerseLinks wraps Russian Synodal dash format 1-я Царств`() {
        val input = "1-я Царств 1:1 рассказывает о Самуиле"
        val result = injectVerseLinks(input)
        assertTrue("should link 1-я Царств", result.contains("[1-я Царств 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Russian Synodal dash format 1-е Коринфянам`() {
        val input = "1-е Коринфянам 13:4 о любви"
        val result = injectVerseLinks(input)
        assertTrue("should link 1-е Коринфянам", result.contains("[1-е Коринфянам 13:4]"))
    }

    // ── Edge cases ──────────────────────────────────────────────────────────

    @Test
    fun `injectVerseLinks does not match standalone chapter-verse without book name`() {
        // "3:16" at the start of text should NOT be matched (no book name)
        val input = "3:16 is a famous verse."
        val result = injectVerseLinks(input)
        // The book name pattern requires at least one \p{L} letter, so "3:16" alone won't match
        assertFalse(result.contains("[3:16]"))
        assertEquals(input, result)
    }

    @Test
    fun `injectVerseLinks handles verse reference at end of text`() {
        val input = "Consider John 3:16"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[John 3:16]"))
    }

    @Test
    fun `injectVerseLinks mixes English and non-English references`() {
        val input = "John 3:16 y Juan 3:16 son idénticos"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[John 3:16]"))
        assertTrue(result.contains("[Juan 3:16]"))
    }

    @Test
    fun `injectVerseLinks links both refs in semicolon-separated list`() {
        // Semicolons are word boundaries in regex, so each ref should be matched independently.
        val input = "John 3:16; Romans 8:28 are famous verses."
        val result = injectVerseLinks(input)
        assertTrue("should link John 3:16", result.contains("[John 3:16]"))
        assertTrue("should link Romans 8:28", result.contains("[Romans 8:28]"))
    }

    @Test
    fun `injectVerseLinks links chapter-only reference with no verse number`() {
        // Chapter-only refs like "Psalm 23" have no colon, so the verse group is empty.
        val input = "read Psalm 23 for comfort."
        val result = injectVerseLinks(input)
        assertTrue("should contain Psalm 23 as link", result.contains("[Psalm 23]"))
        assertFalse("should not append trailing colon for chapter-only ref",
            result.contains("[Psalm 23:]"))
        assertTrue("URL should have no verse segment",
            result.contains("verse://Psalm/23") || result.contains("verse://Psalms/23"))
    }

    // ── handleVerseLink ───────────────────────────────────────────────────────

    @Test
    fun `handleVerseLink calls onLoadChapter with correct book and chapter`() {
        var calledBook: String? = null
        var calledChapter: Int? = null
        var calledTranslation: String? = null

        handleVerseLink(
            url = "verse://John/3/16",
            preferredTranslation = null,
        ) { book, chapter, translation ->
            calledBook = book
            calledChapter = chapter
            calledTranslation = translation
        }

        assertEquals("John", calledBook)
        assertEquals(3, calledChapter)
        assertEquals(null, calledTranslation)
    }

    @Test
    fun `handleVerseLink passes preferredTranslation`() {
        var calledTranslation: String? = "not-set"

        handleVerseLink(
            url = "verse://Romans/5/8",
            preferredTranslation = "KJV",
        ) { _, _, translation ->
            calledTranslation = translation
        }

        assertEquals("KJV", calledTranslation)
    }

    @Test
    fun `handleVerseLink ignores non-verse urls`() {
        var called = false

        handleVerseLink(
            url = "https://example.com",
            preferredTranslation = null,
        ) { _, _, _ -> called = true }

        assertTrue("should not call onLoadChapter for non-verse URL", !called)
    }

    @Test
    fun `handleVerseLink ignores malformed verse url`() {
        var called = false

        handleVerseLink(
            url = "verse://OnlyOneSegment",
            preferredTranslation = null,
        ) { _, _, _ -> called = true }

        assertTrue("should not call onLoadChapter for malformed URL", !called)
    }

    @Test
    fun `handleVerseLink decodes URL-encoded book name`() {
        var calledBook: String? = null

        // 1+Corinthians or 1%20Corinthians — both should decode to "1 Corinthians"
        handleVerseLink(
            url = "verse://1+Corinthians/13/4",
            preferredTranslation = null,
        ) { book, _, _ ->
            calledBook = book
        }

        assertEquals("1 Corinthians", calledBook)
    }

    @Test
    fun `handleVerseLink handles chapter-only URL with no verse segment`() {
        var calledBook: String? = null
        var calledChapter: Int? = null

        // verse://Psalm/23 — no verse segment, should still invoke callback
        handleVerseLink(
            url = "verse://Psalm/23",
            preferredTranslation = null,
        ) { book, chapter, _ ->
            calledBook = book
            calledChapter = chapter
        }

        assertEquals("Psalm", calledBook)
        assertEquals(23, calledChapter)
    }
}
