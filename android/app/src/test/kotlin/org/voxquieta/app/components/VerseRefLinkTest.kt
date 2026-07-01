package org.voxquieta.app.components

import org.voxquieta.app.presentation.components.QUOTE_HIGHLIGHT_REGEX
import org.voxquieta.app.presentation.components.buildVerseRefRegex
import org.voxquieta.app.presentation.components.citedVerses
import org.voxquieta.app.presentation.components.handleVerseLink
import org.voxquieta.app.presentation.components.injectVerseLinks
import org.voxquieta.app.presentation.components.injectVerseQuoteHighlights
import org.voxquieta.app.domain.models.Message
import org.voxquieta.app.domain.models.Verse
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
        // "of" connector — Song of Solomon is a real (known) book, linked whole.
        val result1 = injectVerseLinks("Song of Solomon 1:1 is beautiful")
        assertTrue(result1.contains("[Song of Solomon 1:1]"))

        // "de" connector: "Livro de Salmos" ("Book of Psalms") is NOT a canonical book, so the
        // allowlist gate rejects the greedy "Livro de Salmos" over-match and the scan rewinds to
        // the real book "Salmos". (Same outcome the web produces via isKnownBook + rewind.)
        val result2 = injectVerseLinks("Livro de Salmos 23:1")
        assertTrue(result2.contains("[Salmos 23:1]"))
        assertFalse(result2.contains("[Livro de Salmos 23:1]"))
    }

    // ── Connector-word / greedy over-match regression (unified with web) ──────

    @Test
    fun `injectVerseLinks recovers a reference preceded by the connector 'of'`() {
        // Greedy branch used to capture "you of Psalm" and, failing the allowlist gate, drop the
        // real reference. The rewind now recovers it. (Mirrors the web ChatMessage fix.)
        val result = injectVerseLinks("I also want to remind you of Psalm 56:9, which says.")
        assertTrue(result, result.contains("[Psalm 56:9]"))
        assertFalse(result.contains("[you of Psalm"))
    }

    @Test
    fun `injectVerseLinks recovers a reference preceded by the connector in prose`() {
        val result = injectVerseLinks("the promise of Isaiah 41:10 is sure")
        assertTrue(result, result.contains("[Isaiah 41:10]"))
    }

    @Test
    fun `injectVerseLinks recovers a reference hidden by a greedy numbered over-match`() {
        val result = injectVerseLinks("Wie in 1 day of Psalm 56:9 beschrieben.")
        assertTrue(result, result.contains("[Psalm 56:9]"))
        assertFalse(result.contains("[1 day of Psalm"))
    }

    // ── Lowercase references (previously dropped by the uppercase-first regex) ──

    @Test
    fun `injectVerseLinks links a lowercase-emitted reference`() {
        val result = injectVerseLinks("As john 3:16 says, God loves us.")
        assertTrue(result, result.contains("[john 3:16]"))
    }

    @Test
    fun `injectVerseLinks does not link a clock time`() {
        val input = "Wir treffen uns um 14:30 Uhr."
        assertEquals(input, injectVerseLinks(input))
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

    // ── Chinese (CJK) no-space verse detection ────────────────────────────────
    // In Chinese text, there is typically no space between the book name and
    // the chapter number (e.g. "约翰福音10:28" instead of "约翰福音 10:28").

    @Test
    fun `injectVerseLinks wraps Chinese book with no space before chapter`() {
        val input = "约翰福音10:28是重要的经文"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音 10:28", result.contains("[约翰福音 10:28]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese 诗篇 with no space before chapter`() {
        val input = "诗篇23:1是安慰的经文"
        val result = injectVerseLinks(input)
        assertTrue("should link 诗篇 23:1", result.contains("[诗篇 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese 创世记 with no space before chapter`() {
        val input = "创世记1:1是起始"
        val result = injectVerseLinks(input)
        assertTrue("should link 创世记 1:1", result.contains("[创世记 1:1]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese verse range with no space`() {
        val input = "约翰福音3:16-18是重要的"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音 3:16-18", result.contains("[约翰福音 3:16-18]"))
    }

    @Test
    fun `injectVerseLinks wraps multiple Chinese no-space refs separated by 、`() {
        val input = "约翰福音10:28、诗篇23:1都很重要"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音", result.contains("[约翰福音 10:28]"))
        assertTrue("should link 诗篇", result.contains("[诗篇 23:1]"))
    }

    @Test
    fun `injectVerseLinks does not match Latin book with no space (regression)`() {
        val input = "Read John3:16 for hope"
        val result = injectVerseLinks(input)
        assertEquals("Latin no-space should NOT match", input, result)
    }

    @Test
    fun `buildVerseRefRegex with CJK names matches embedded Chinese no-space`() {
        val regex = buildVerseRefRegex(
            emptyList(),
            listOf("约翰福音", "诗篇", "创世记", "耶利米哀歌"),
        )
        val input = "请阅读约翰福音10:28来获得鼓励"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link 约翰福音", result.contains("[约翰福音 10:28]"))
        assertFalse("should NOT match surrounding CJK text", result.contains("[请阅读约翰福音"))
    }

    @Test
    fun `buildVerseRefRegex with CJK names matches real-world Chinese sentence`() {
        val regex = buildVerseRefRegex(
            emptyList(),
            listOf("约翰福音", "诗篇", "创世记", "耶利米哀歌"),
        )
        val input = "这来自圣经，具体是约翰福音10:28、约翰福音3:16等章节"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link first ref", result.contains("[约翰福音 10:28]"))
        assertTrue("should link second ref", result.contains("[约翰福音 3:16]"))
    }

    // ── Chinese guillemet 《》 notation ──────────────────────────────────────
    // Chinese texts commonly wrap book names in guillemets: 《约翰福音》3:16

    @Test
    fun `injectVerseLinks wraps Chinese guillemet notation with space`() {
        val input = "《约翰福音》 3:16是著名的经文"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音 3:16", result.contains("[约翰福音 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps Chinese guillemet notation without space`() {
        val input = "《约翰福音》3:16是著名的经文"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音 3:16", result.contains("[约翰福音 3:16]"))
    }

    @Test
    fun `injectVerseLinks wraps guillemet with verse range`() {
        val input = "《罗马书》8:28-39给我们安慰"
        val result = injectVerseLinks(input)
        assertTrue("should link 罗马书", result.contains("[罗马书 8:28-39]"))
    }

    @Test
    fun `injectVerseLinks wraps multiple guillemet refs`() {
        val input = "《约翰福音》3:16和《诗篇》23:1都很重要"
        val result = injectVerseLinks(input)
        assertTrue("should link 约翰福音", result.contains("[约翰福音 3:16]"))
        assertTrue("should link 诗篇", result.contains("[诗篇 23:1]"))
    }

    @Test
    fun `buildVerseRefRegex with CJK names wraps guillemet in sentence`() {
        val regex = buildVerseRefRegex(
            emptyList(),
            listOf("约翰福音", "诗篇", "创世记"),
        )
        val input = "请阅读《约翰福音》10:28来获得鼓励"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link 约翰福音", result.contains("[约翰福音 10:28]"))
        assertFalse("should NOT match surrounding text", result.contains("[请阅读约翰福音"))
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

    @Test
    fun `injectVerseLinks handles Hindi verse-range followed by और and another book`() {
        // Regression test for web-side bug where the numbered-prefix branch greedily
        // captured "4 और इब्रानियों" starting from the dangling 4 in "1:3-4".
        // Android's regex is not vulnerable because its numbered branch only matches
        // [1-3] prefixes, but we lock this behaviour in with an explicit test.
        val input = "लेवियतियुस 1:3-4 और इब्रानियों 9:22 रोमियों 12:1"
        val result = injectVerseLinks(input)
        assertTrue("should link Leviticus", result.contains("[लेवियतियुस 1:3-4]"))
        assertTrue("should link Hebrews", result.contains("[इब्रानियों 9:22]"))
        assertTrue("should link Romans", result.contains("[रोमियों 12:1]"))
        // Must not create a fake "4 और इब्रानियों" link.
        assertTrue(
            "should not produce greedy '4 और' match",
            !result.contains("[4 और")
        )
    }

    @Test
    fun `injectVerseLinks wraps Hindi alternate transliteration लेवियतियुस`() {
        // This alternate transliteration is a known alias in the bundled book-name map, so it
        // passes the allowlist gate and is linked. Backend HINDI_ALIASES also normalizes
        // लेवियतियुस → Leviticus on tap.
        val input = "लेवियतियुस 1:3 में बलिदान का उल्लेख है"
        val result = injectVerseLinks(input)
        assertTrue(result.contains("[लेवियतियुस 1:3]"))
    }

    // ── Non-English book names: Arabic/Hindi multi-word with dynamic regex ──

    @Test
    fun `buildVerseRefRegex wraps Arabic multi-word Acts أعمال الرسل`() {
        val regex = org.voxquieta.app.presentation.components.buildVerseRefRegex(
            listOf("أعمال الرسل", "مراثي إرميا", "نشيد الأنشاد")
        )
        val input = "أعمال الرسل 2:38 عن المعمودية"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Arabic Acts", result.contains("[أعمال الرسل 2:38]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Arabic multi-word Lamentations مراثي إرميا`() {
        val regex = org.voxquieta.app.presentation.components.buildVerseRefRegex(
            listOf("أعمال الرسل", "مراثي إرميا")
        )
        val input = "مراثي إرميا 3:22 عن الرحمة"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Arabic Lamentations", result.contains("[مراثي إرميا 3:22]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Hindi multi-word Psalms भजन संहिता`() {
        val regex = org.voxquieta.app.presentation.components.buildVerseRefRegex(
            listOf("भजन संहिता", "प्रेरितों के काम")
        )
        val input = "भजन संहिता 23:1 में राहत है"
        val result = injectVerseLinks(input, regex)
        assertTrue("should link Hindi Psalms", result.contains("[भजन संहिता 23:1]"))
    }

    @Test
    fun `buildVerseRefRegex wraps Hindi multi-word Acts प्रेरितों के काम`() {
        val regex = org.voxquieta.app.presentation.components.buildVerseRefRegex(
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

    // ── Bold wrapping (verse reference prominence) ────────────────────────────

    @Test
    fun `injectVerseLinks wraps plain verse ref in bold markdown`() {
        val input = "In John 3:16 we read about God's love."
        val result = injectVerseLinks(input)
        assertTrue("link should be bold", result.contains("**[John 3:16](verse://John/3/16)**"))
    }

    @Test
    fun `injectVerseLinks does not double-bold a ref already wrapped in bold`() {
        // LLM output with explicit bold: **John 3:16** — the ** stays from the original;
        // only the inner text should become a link, not be re-wrapped.
        val input = "See **John 3:16** for hope."
        val result = injectVerseLinks(input)
        // Should linkify but NOT add extra bold markers around the link
        assertTrue("should still create a link", result.contains("[John 3:16](verse://John/3/16)"))
        assertFalse("should not produce quadruple asterisks", result.contains("****"))
    }

    // ── injectVerseQuoteHighlights (no-op since BITB-036) ────────────────────

    @Test
    fun `injectVerseQuoteHighlights is a no-op for verse-adjacent straight quotes`() {
        val input = "**[John 3:16](verse://John/3/16)**: \"For God so loved the world\""
        assertEquals("must be unchanged (highlighting moved to beforeSetMarkdown span layer)", input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for guillemet quotes`() {
        val input = "**[Jean 3:16](verse://Jean/3/16)**: \u00ABCar Dieu a tant aim\u00E9 le monde\u00BB"
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for German low-high quotes`() {
        val input = "**[Johannes 3:16](verse://Johannes/3/16)**: \u201EDenn so hat Gott die Welt geliebt\u201D"
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for plain prose`() {
        val input = "In **[John 3:16](verse://John/3/16)** we find hope and comfort."
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for short quoted strings`() {
        val input = "**[John 3:16](verse://John/3/16)**: \"Hi\""
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op when there are no verse links`() {
        val input = "He said \"For God so loved the world\" with joy."
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op after injectVerseLinks`() {
        val raw = "In John 3:16, \"For God so loved the world that he gave his only Son.\""
        val linked = injectVerseLinks(raw)
        assertTrue("verse ref should be bold link", linked.contains("**[John 3:16](verse://John/3/16)**"))
        assertEquals("injectVerseQuoteHighlights must not alter linked text", linked, injectVerseQuoteHighlights(linked))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for prose-separated quote`() {
        val input = "**[Romans 8:28](verse://Romans/8/28)** reminds us that \"And we know that in all things God works\""
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    @Test
    fun `injectVerseQuoteHighlights is a no-op for cross-paragraph quote`() {
        val input = "**[John 3:16](verse://John/3/16)**\n\n\"For God so loved the world\""
        assertEquals(input, injectVerseQuoteHighlights(input))
    }

    // ── QUOTE_HIGHLIGHT_REGEX ─────────────────────────────────────────

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches straight double quotes`() {
        val match = QUOTE_HIGHLIGHT_REGEX.find("He said \"For God so loved the world\".")
        assertTrue("must match quoted text", match != null)
        assertTrue("must contain the content", match!!.value.contains("For God so loved the world"))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches curly double quotes`() {
        assertTrue(QUOTE_HIGHLIGHT_REGEX.containsMatchIn("\u201CFor God so loved the world\u201D"))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches guillemets`() {
        assertTrue(QUOTE_HIGHLIGHT_REGEX.containsMatchIn("\u00ABCar Dieu a tant aim\u00E9 le monde\u00BB"))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches German low-high quotes`() {
        assertTrue(QUOTE_HIGHLIGHT_REGEX.containsMatchIn("\u201EDenn so hat Gott die Welt geliebt\u201D"))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches all quoted occurrences not just verse-adjacent ones`() {
        val count = QUOTE_HIGHLIGHT_REGEX.findAll("\"first quote here\" and \"second quote here\"").count()
        assertEquals("must find both quotes", 2, count)
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX ignores quotes with fewer than 3 content chars`() {
        assertFalse("short string must not match", QUOTE_HIGHLIGHT_REGEX.containsMatchIn("\"Hi\""))
        assertFalse("two-char string must not match", QUOTE_HIGHLIGHT_REGEX.containsMatchIn("\"OK\""))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches quote adjacent to verse link (web parity)`() {
        val input = "**[John 3:16](verse://John/3/16)**: \"For God so loved the world\""
        assertTrue("must match the quoted part", QUOTE_HIGHLIGHT_REGEX.containsMatchIn(input))
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches CJK corner brackets`() {
        // 「 … 」 — U+300C … U+300D
        assertTrue(
            "must match CJK corner-bracket quote",
            QUOTE_HIGHLIGHT_REGEX.containsMatchIn("「神は世を愛された」"),
        )
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX matches double CJK brackets`() {
        // 《 … 》 — U+300A … U+300B
        assertTrue(
            "must match double CJK-bracket quote",
            QUOTE_HIGHLIGHT_REGEX.containsMatchIn("《神は世を愛された》"),
        )
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX does not match across a newline`() {
        // An opener and closer separated by a newline must NOT produce a match —
        // otherwise the amber highlight would bleed across paragraph breaks.
        val input = "He said \"For God so loved the world\nand gave his only Son\""
        assertFalse(
            "newline inside a quote must break the match",
            QUOTE_HIGHLIGHT_REGEX.containsMatchIn(input),
        )
    }

    @Test
    fun `QUOTE_HIGHLIGHT_REGEX still matches a single-line quote after newline fix`() {
        // Guard: the \n exclusion must not break ordinary single-line matching.
        val input = "First line without quotes\nHe said \"For God so loved the world\""
        assertTrue(
            "single-line quote on the second line must still match",
            QUOTE_HIGHLIGHT_REGEX.containsMatchIn(input),
        )
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

    @Test
    fun `handleVerseLink ignores localizedBook query param and still loads correct chapter`() {
        var calledBook: String? = null
        var calledChapter: Int? = null

        handleVerseLink(
            url = "verse://Exodus/30/22?localizedBook=Esodo",
            preferredTranslation = "ita1927",
        ) { book, chapter, _ ->
            calledBook = book
            calledChapter = chapter
        }

        assertEquals("Exodus", calledBook)
        assertEquals(30, calledChapter)
    }

    @Test
    fun `handleVerseLink chapter-only URL with localizedBook query param still fires`() {
        var calledBook: String? = null
        var calledChapter: Int? = null

        handleVerseLink(
            url = "verse://Psalms/23?localizedBook=Salmi",
            preferredTranslation = null,
        ) { book, chapter, _ ->
            calledBook = book
            calledChapter = chapter
        }

        assertEquals("Psalms", calledBook)
        assertEquals(23, calledChapter)
    }

    // ── Link target resolution from the cited verse list ─────────────────────

    @Test
    fun `injectVerseLinks normalizes localized book via the map before the verse list`() {
        val map = mapOf("Matthäus" to "Matthew")
        val result = injectVerseLinks(
            "wie in Matthäus 5:7",
            verses = emptyList(),
            localizedToEnglish = map,
        )
        assertTrue(result.contains("[Matthäus 5:7]"))
        assertTrue(result.contains("verse://Matthew/5/7"))
    }

    @Test
    fun `injectVerseLinks appends localizedBook query param when book differs from link target`() {
        // "Esodo" is the Italian name; the map resolves it to "Exodus" for the link target.
        // The URL should carry localizedBook=Esodo so parseVerseLink can set it on PendingVerseLink.
        val map = mapOf("Esodo" to "Exodus")
        val result = injectVerseLinks(
            "vedi Esodo 30:22 per la formula",
            verses = emptyList(),
            localizedToEnglish = map,
        )
        assertTrue("display text keeps Italian name", result.contains("[Esodo 30:22]"))
        assertTrue("link target uses English canonical", result.contains("verse://Exodus/30/22"))
        assertTrue("localizedBook query param carries the Italian name", result.contains("localizedBook=Esodo"))
    }

    @Test
    fun `injectVerseLinks does not append localizedBook query param for English book names`() {
        val result = injectVerseLinks("See John 3:16 for hope.")
        assertTrue(result.contains("verse://John/3/16"))
        assertFalse("no localizedBook param needed when book is already English", result.contains("localizedBook="))
    }

    @Test
    fun `injectVerseLinks does not link an unmapped book name (allowlist gate, web parity)`() {
        // "Proverbia" is the Latin/Vulgate name — in no book-name map. Under the unified
        // algorithm the allowlist gate rejects any name that is not a real Bible book, exactly
        // as the web does (the web never linked "Proverbia" either). So the reference is left as
        // plain text, even when the backend cited a verse at that chapter:verse.
        val verses = listOf(
            Verse(book = "Proverbs", chapter = 17, verse = 17, text = "Ein Freund liebt jederzeit"),
        )
        val withVerse = injectVerseLinks("In Proverbia 17:17 steht", verses = verses)
        assertEquals("In Proverbia 17:17 steht", withVerse)

        val withoutVerse = injectVerseLinks("In Proverbia 17:17 steht", verses = emptyList())
        assertEquals("In Proverbia 17:17 steht", withoutVerse)
    }

    // ── citedVerses ──────────────────────────────────────────────────────────

    private fun assistant(content: String, verses: List<Verse>, cited: List<String>) =
        Message(
            id = "m1",
            role = Message.Role.ASSISTANT,
            content = content,
            verses = verses,
            versesCited = cited,
        )

    @Test
    fun `citedVerses returns only the verses named in versesCited`() {
        val verses = listOf(
            Verse(book = "Proverbs", chapter = 17, verse = 17, text = "Ein Freund liebt jederzeit"),
            Verse(book = "John", chapter = 3, verse = 16, text = "Denn so sehr hat Gott die Welt geliebt"),
        )
        val result = citedVerses(assistant("…", verses, cited = listOf("Proverbs 17:17")))
        assertEquals(1, result.size)
        assertEquals("Proverbs", result.first().book)
    }

    @Test
    fun `citedVerses falls back to all verses when versesCited is empty`() {
        val verses = listOf(Verse(book = "Proverbs", chapter = 17, verse = 17, text = "…"))
        val result = citedVerses(assistant("…", verses, cited = emptyList()))
        assertEquals(verses, result)
    }

    @Test
    fun `citedVerses returns empty when the message has no verses`() {
        val result = citedVerses(assistant("…", verses = emptyList(), cited = listOf("John 3:16")))
        assertTrue(result.isEmpty())
    }

    // ── Parenthesized / bracketed citations (cross-parser parity, AGENTS.md) ───
    // The backend parser must detect references wrapped in ( ) [ ] / fullwidth
    // （ ）. This asserts the Android parser — which must stay in sync — links them
    // too. `(Book C:V)` is the single most common citation format.

    @Test
    fun `injectVerseLinks wraps a reference in parentheses`() {
        val result = injectVerseLinks("Take heart (John 3:16) today.")
        assertTrue(result, result.contains("[John 3:16](verse://John/3/16)"))
    }

    @Test
    fun `injectVerseLinks wraps a reference in square brackets`() {
        val result = injectVerseLinks("Hope [Psalm 23:1] holds.")
        assertTrue(result, result.contains("[Psalm 23:1]") || result.contains("[Psalms 23:1]"))
    }

    @Test
    fun `injectVerseLinks wraps an italian reference in parentheses`() {
        val result = injectVerseLinks("Coraggio (Giovanni 3:16).")
        assertTrue(result, result.contains("[Giovanni 3:16]"))
    }
}
