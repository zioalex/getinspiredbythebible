"""Tests for the verse reference and prayer pattern parser."""

from utils.verse_parser import (
    VerseReference,
    extract_all_references,
    extract_references,
    find_prayer_reference,
    is_verse_lookup_request,
    parse_structured_citations,
    parse_verse_reference,
)


class TestParseVerseReference:
    """Tests for parse_verse_reference function."""

    def test_simple_verse(self):
        """Test parsing a simple verse reference."""
        result = parse_verse_reference("John 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16
        assert result.verse_end is None

    def test_verse_range(self):
        """Test parsing a verse range."""
        result = parse_verse_reference("Romans 8:28-30")
        assert result is not None
        assert result.book == "Romans"
        assert result.chapter == 8
        assert result.verse_start == 28
        assert result.verse_end == 30

    def test_numbered_book(self):
        """Test parsing numbered books like 1 Corinthians."""
        result = parse_verse_reference("1 Corinthians 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"
        assert result.chapter == 13
        assert result.verse_start == 4

    def test_abbreviated_book(self):
        """Test parsing abbreviated book names."""
        result = parse_verse_reference("Jn 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_psalms_abbreviated(self):
        """Test parsing Psalms with abbreviation."""
        result = parse_verse_reference("Ps 23:1")
        assert result is not None
        assert result.book == "Psalms"
        assert result.chapter == 23
        assert result.verse_start == 1

    def test_italian_book_name(self):
        """Test parsing Italian book names."""
        result = parse_verse_reference("Giovanni 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_german_comma_separator(self):
        """Test parsing German style with comma."""
        result = parse_verse_reference("Johannes 3,16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_verse_in_sentence(self):
        """Test finding verse in a sentence."""
        result = parse_verse_reference("What does John 3:16 mean?")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_no_verse_found(self):
        """Test when no verse reference is present."""
        result = parse_verse_reference("I need some encouragement today")
        assert result is None

    def test_invalid_book_name(self):
        """Test with invalid book name."""
        result = parse_verse_reference("Notabook 3:16")
        assert result is None

    def test_matthew_abbreviated(self):
        """Test parsing Matthew with abbreviation."""
        result = parse_verse_reference("Matt 5:3")
        assert result is not None
        assert result.book == "Matthew"

    def test_genesis_abbreviated(self):
        """Test parsing Genesis with abbreviation."""
        result = parse_verse_reference("Gen 1:1")
        assert result is not None
        assert result.book == "Genesis"


class TestFindPrayerReference:
    """Tests for find_prayer_reference function."""

    def test_lords_prayer(self):
        """Test finding Lord's Prayer reference."""
        result = find_prayer_reference("Tell me about the Lord's Prayer")
        assert result is not None
        assert result.name == "Lord's Prayer"
        assert "Matthew 6:9-13" in result.reference

    def test_our_father(self):
        """Test finding Our Father reference."""
        result = find_prayer_reference("What is the Our Father prayer?")
        assert result is not None
        assert result.name == "Lord's Prayer"

    def test_psalm_23(self):
        """Test finding Psalm 23 reference."""
        result = find_prayer_reference("Explain psalm 23 to me")
        assert result is not None
        assert result.name == "Psalm 23"

    def test_ten_commandments(self):
        """Test finding Ten Commandments reference."""
        result = find_prayer_reference("List the Ten Commandments")
        assert result is not None
        assert result.name == "Ten Commandments"

    def test_beatitudes(self):
        """Test finding Beatitudes reference."""
        result = find_prayer_reference("What are the Beatitudes?")
        assert result is not None
        assert result.name == "Beatitudes"

    def test_love_chapter(self):
        """Test finding Love Chapter reference."""
        result = find_prayer_reference("Read me the love chapter")
        assert result is not None
        assert result.name == "Love Chapter"

    def test_no_prayer_found(self):
        """Test when no prayer reference is present."""
        result = find_prayer_reference("I'm feeling anxious")
        assert result is None

    def test_italian_lords_prayer(self):
        """Test finding Italian Lord's Prayer reference."""
        result = find_prayer_reference("Dimmi del Padre Nostro")
        assert result is not None
        assert result.name == "Lord's Prayer"

    def test_hail_mary_not_biblical(self):
        """Test that Hail Mary is correctly marked as non-biblical."""
        result = find_prayer_reference("Tell me about the Hail Mary")
        assert result is not None
        assert result.name == "Hail Mary"
        assert result.is_biblical is False
        assert result.reference == ""

    def test_ave_maria_not_biblical(self):
        """Test that Ave Maria is correctly marked as non-biblical."""
        result = find_prayer_reference("What is the Ave Maria?")
        assert result is not None
        assert result.name == "Hail Mary"
        assert result.is_biblical is False

    def test_serenity_prayer_not_biblical(self):
        """Test that Serenity Prayer is correctly marked as non-biblical."""
        result = find_prayer_reference("Recite the serenity prayer")
        assert result is not None
        assert result.name == "Serenity Prayer"
        assert result.is_biblical is False

    def test_lords_prayer_is_biblical(self):
        """Test that Lord's Prayer is correctly marked as biblical."""
        result = find_prayer_reference("Tell me about the Lord's Prayer")
        assert result is not None
        assert result.is_biblical is True
        assert result.reference == "Matthew 6:9-13"

    def test_psalm_23_is_biblical(self):
        """Test that Psalm 23 is correctly marked as biblical."""
        result = find_prayer_reference("What is Psalm 23?")
        assert result is not None
        assert result.is_biblical is True
        assert result.reference == "Psalms 23:1-6"


class TestExtractReferences:
    """Tests for extract_references function."""

    def test_verse_only(self):
        """Test extracting just a verse reference."""
        verses, prayer = extract_references("Explain John 3:16")
        assert len(verses) == 1
        assert verses[0].book == "John"
        assert prayer is None

    def test_prayer_only(self):
        """Test extracting just a prayer reference."""
        verses, prayer = extract_references("What is the Lord's Prayer?")
        # Prayer with reference should also add verse
        assert len(verses) == 1  # Matthew 6:9-13
        assert prayer is not None
        assert prayer.name == "Lord's Prayer"

    def test_both_verse_and_prayer(self):
        """Test with both types of references."""
        verses, prayer = extract_references("How does Psalm 23 relate to the Lord's Prayer?")
        assert len(verses) >= 1
        assert prayer is not None


class TestIsVerseLookupRequest:
    """Tests for is_verse_lookup_request function."""

    def test_what_does_verse_say(self):
        """Test 'what does X say' pattern."""
        assert is_verse_lookup_request("What does John 3:16 say?") is True

    def test_explain_verse(self):
        """Test 'explain X' pattern."""
        assert is_verse_lookup_request("Explain Romans 8:28") is True

    def test_tell_me_about_prayer(self):
        """Test 'tell me about X' pattern."""
        assert is_verse_lookup_request("Tell me about the Lord's Prayer") is True

    def test_meaning_of_verse(self):
        """Test 'meaning of X' pattern."""
        assert is_verse_lookup_request("What is the meaning of Psalm 23?") is True

    def test_show_me_verse(self):
        """Test 'show me X' pattern."""
        assert is_verse_lookup_request("Show me 1 Corinthians 13:4-7") is True

    def test_just_verse_reference(self):
        """Test just mentioning a verse."""
        assert is_verse_lookup_request("John 3:16") is True

    def test_general_question(self):
        """Test general question without verse."""
        assert is_verse_lookup_request("I'm feeling anxious today") is False

    def test_encouragement_request(self):
        """Test encouragement request without specific verse."""
        assert is_verse_lookup_request("Can you encourage me?") is False

    def test_italian_lookup(self):
        """Test Italian verse lookup pattern."""
        assert is_verse_lookup_request("Cosa dice Giovanni 3:16?") is True


class TestVerseReferenceStr:
    """Tests for VerseReference string representation."""

    def test_single_verse_str(self):
        """Test string representation of single verse."""
        ref = VerseReference(book="John", chapter=3, verse_start=16)
        assert str(ref) == "John 3:16"

    def test_verse_range_str(self):
        """Test string representation of verse range."""
        ref = VerseReference(book="Romans", chapter=8, verse_start=28, verse_end=30)
        assert str(ref) == "Romans 8:28-30"


class TestParseVerseReferenceNonEnglish:
    """End-to-end parse_verse_reference() tests for non-English book names.

    Values are taken directly from the canonical translation_registry.py dicts
    and EXTRA_REVERSE_MAPPINGS, so any regression in those dicts will be caught.
    """

    # ── Russian ──────────────────────────────────────────────────────────────

    def test_russian_genitive_john(self):
        """Russian genitive citation form 'Иоанна 3:16' → John."""
        result = parse_verse_reference("Иоанна 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_russian_nominative_john(self):
        """Russian nominative canonical form 'Иоанн 3:16' → John."""
        result = parse_verse_reference("Иоанн 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_russian_nominative_psaltir(self):
        """Russian Psalms nominative 'Псалтирь 23:1' → Psalms."""
        result = parse_verse_reference("Псалтирь 23:1")
        assert result is not None
        assert result.book == "Psalms"
        assert result.chapter == 23
        assert result.verse_start == 1

    def test_russian_genitive_psaltiri(self):
        """Russian Psalms genitive 'Псалтири 23:1' → Psalms."""
        result = parse_verse_reference("Псалтири 23:1")
        assert result is not None
        assert result.book == "Psalms"
        assert result.chapter == 23
        assert result.verse_start == 1

    def test_russian_genesis_nominative(self):
        """Russian Genesis nominative 'Бытие 1:1' → Genesis."""
        result = parse_verse_reference("Бытие 1:1")
        assert result is not None
        assert result.book == "Genesis"
        assert result.chapter == 1
        assert result.verse_start == 1

    def test_russian_genesis_genitive(self):
        """Russian Genesis genitive 'Бытия 1:1' → Genesis."""
        result = parse_verse_reference("Бытия 1:1")
        assert result is not None
        assert result.book == "Genesis"
        assert result.chapter == 1
        assert result.verse_start == 1

    def test_russian_matthew_genitive(self):
        """Russian Matthew genitive 'Матфея 5:3' → Matthew."""
        result = parse_verse_reference("Матфея 5:3")
        assert result is not None
        assert result.book == "Matthew"
        assert result.chapter == 5
        assert result.verse_start == 3

    def test_russian_revelation_genitive(self):
        """Russian Revelation genitive 'Откровения 21:4' → Revelation."""
        result = parse_verse_reference("Откровения 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_russian_revelation_nominative(self):
        """Russian Revelation nominative 'Откровение 21:4' → Revelation."""
        result = parse_verse_reference("Откровение 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_russian_acts_short(self):
        """Russian Acts short 'Деяния 2:38' → Acts."""
        result = parse_verse_reference("Деяния 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_russian_acts_genitive(self):
        """Russian Acts genitive 'Деяний 2:38' → Acts."""
        result = parse_verse_reference("Деяний 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_russian_lamentations_two_words(self):
        """Russian Lamentations 'Плач Иеремии 3:3' → Lamentations."""
        result = parse_verse_reference("Плач Иеремии 3:3")
        assert result is not None
        assert result.book == "Lamentations"

    def test_russian_corinthians_no_dash_alias(self):
        """Russian '1 Коринфянам 13:4' (no-dash alias) → 1 Corinthians."""
        result = parse_verse_reference("1 Коринфянам 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"
        assert result.chapter == 13
        assert result.verse_start == 4

    def test_russian_1_samuel_synodal_canonical(self):
        """Russian Synodal '1-я Царств 3:1' → 1 Samuel."""
        result = parse_verse_reference("1-я Царств 3:1")
        assert result is not None
        assert result.book == "1 Samuel"

    def test_russian_1_kings_synodal_canonical(self):
        """Russian Synodal '3-я Царств 18:1' → 1 Kings."""
        result = parse_verse_reference("3-я Царств 18:1")
        assert result is not None
        assert result.book == "1 Kings"

    # ── Chinese ───────────────────────────────────────────────────────────────

    def test_chinese_john(self):
        """Chinese John '约翰福音 3:16' → John."""
        # ENGLISH_TO_CHINESE["John"] = "约翰福音"
        result = parse_verse_reference("约翰福音 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_chinese_genesis(self):
        """Chinese Genesis '创世记 1:1' → Genesis."""
        result = parse_verse_reference("创世记 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_chinese_psalms(self):
        """Chinese Psalms '诗篇 23:1' → Psalms."""
        result = parse_verse_reference("诗篇 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_chinese_1_corinthians(self):
        """Chinese 1 Corinthians '哥林多前书 13:4' → 1 Corinthians."""
        result = parse_verse_reference("哥林多前书 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_chinese_revelation_traditional(self):
        """Chinese Revelation traditional '啟示錄 21:4' → Revelation."""
        result = parse_verse_reference("啟示錄 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_chinese_revelation_simplified_alias(self):
        """Chinese Revelation simplified alias '启示录 21:4' → Revelation."""
        result = parse_verse_reference("启示录 21:4")
        assert result is not None
        assert result.book == "Revelation"

    # ── Korean ────────────────────────────────────────────────────────────────

    def test_korean_john(self):
        """Korean John '요한복음 3:16' → John."""
        # ENGLISH_TO_KOREAN["John"] = "요한복음"
        result = parse_verse_reference("요한복음 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_korean_genesis(self):
        """Korean Genesis '창세기 1:1' → Genesis."""
        result = parse_verse_reference("창세기 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_korean_psalms(self):
        """Korean Psalms '시편 23:1' → Psalms."""
        result = parse_verse_reference("시편 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_korean_1_corinthians(self):
        """Korean 1 Corinthians '고린도전서 13:4' → 1 Corinthians."""
        result = parse_verse_reference("고린도전서 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_korean_revelation(self):
        """Korean Revelation '요한계시록 21:4' → Revelation."""
        result = parse_verse_reference("요한계시록 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_korean_lamentations_with_space(self):
        """Korean Lamentations with space '예레미야 애가 3:3' → Lamentations."""
        result = parse_verse_reference("예레미야 애가 3:3")
        assert result is not None
        assert result.book == "Lamentations"

    def test_korean_lamentations_no_space_alias(self):
        """Korean Lamentations no-space alias '예레미야애가 3:3' → Lamentations."""
        result = parse_verse_reference("예레미야애가 3:3")
        assert result is not None
        assert result.book == "Lamentations"

    # ── Italian ───────────────────────────────────────────────────────────────

    def test_italian_john(self):
        """Italian John 'Giovanni 3:16' → John."""
        result = parse_verse_reference("Giovanni 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_italian_genesis(self):
        """Italian Genesis 'Genesi 1:1' → Genesis."""
        result = parse_verse_reference("Genesi 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_italian_psalms(self):
        """Italian Psalms 'Salmi 23:1' → Psalms."""
        result = parse_verse_reference("Salmi 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_italian_1_corinthians(self):
        """Italian 1 Corinthians '1 Corinzi 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1 Corinzi 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_italian_revelation(self):
        """Italian Revelation 'Apocalisse 21:4' → Revelation."""
        result = parse_verse_reference("Apocalisse 21:4")
        assert result is not None
        assert result.book == "Revelation"

    # ── German ────────────────────────────────────────────────────────────────

    def test_german_john(self):
        """German John 'Johannes 3:16' → John."""
        result = parse_verse_reference("Johannes 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_german_john_comma_separator(self):
        """German John with comma separator 'Johannes 3,16' → John."""
        result = parse_verse_reference("Johannes 3,16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_german_genesis_numbered(self):
        """German Genesis '1. Mose 1:1' → Genesis."""
        result = parse_verse_reference("1. Mose 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_german_psalms(self):
        """German Psalms 'Psalmen 23:1' → Psalms."""
        result = parse_verse_reference("Psalmen 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_german_1_corinthians(self):
        """German 1 Corinthians '1. Korinther 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1. Korinther 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_german_revelation(self):
        """German Revelation 'Offenbarung 21:4' → Revelation."""
        result = parse_verse_reference("Offenbarung 21:4")
        assert result is not None
        assert result.book == "Revelation"

    # ── Spanish ───────────────────────────────────────────────────────────────

    def test_spanish_john(self):
        """Spanish John 'Juan 3:16' → John."""
        result = parse_verse_reference("Juan 3:16")
        assert result is not None
        assert result.book == "John"

    def test_spanish_genesis(self):
        """Spanish Genesis 'Génesis 1:1' → Genesis."""
        result = parse_verse_reference("Génesis 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_spanish_psalms(self):
        """Spanish Psalms 'Salmos 23:1' → Psalms."""
        result = parse_verse_reference("Salmos 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_spanish_1_corinthians(self):
        """Spanish 1 Corinthians '1 Corintios 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1 Corintios 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    # ── French ────────────────────────────────────────────────────────────────

    def test_french_john(self):
        """French John 'Jean 3:16' → John."""
        result = parse_verse_reference("Jean 3:16")
        assert result is not None
        assert result.book == "John"

    def test_french_genesis(self):
        """French Genesis 'Genèse 1:1' → Genesis."""
        result = parse_verse_reference("Genèse 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_french_psalms(self):
        """French Psalms 'Psaumes 23:1' → Psalms."""
        result = parse_verse_reference("Psaumes 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_french_1_corinthians(self):
        """French 1 Corinthians '1 Corinthiens 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1 Corinthiens 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    # ── Portuguese ────────────────────────────────────────────────────────────

    def test_portuguese_john(self):
        """Portuguese John 'João 3:16' → John."""
        result = parse_verse_reference("João 3:16")
        assert result is not None
        assert result.book == "John"

    def test_portuguese_genesis(self):
        """Portuguese Genesis 'Gênesis 1:1' → Genesis."""
        result = parse_verse_reference("Gênesis 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_portuguese_psalms(self):
        """Portuguese Psalms 'Salmos 23:1' → Psalms."""
        result = parse_verse_reference("Salmos 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_portuguese_1_corinthians(self):
        """Portuguese 1 Corinthians '1 Coríntios 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1 Coríntios 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    # ── Arabic ────────────────────────────────────────────────────────────────

    def test_arabic_john(self):
        """Arabic John 'يوحنا 3:16' → John."""
        result = parse_verse_reference("يوحنا 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_arabic_genesis(self):
        """Arabic Genesis 'تكوين 1:1' → Genesis."""
        result = parse_verse_reference("تكوين 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_arabic_psalms_canonical(self):
        """Arabic Psalms canonical form 'المزامير 23:1' → Psalms."""
        result = parse_verse_reference("المزامير 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_arabic_psalms_singular_citation(self):
        """Arabic Psalms singular citation 'مزمور 139:12' → Psalms."""
        result = parse_verse_reference("مزمور 139:12")
        assert result is not None
        assert result.book == "Psalms"
        assert result.chapter == 139
        assert result.verse_start == 12

    def test_arabic_psalms_plural_no_article(self):
        """Arabic Psalms plural without article 'مزامير 23:1' → Psalms."""
        result = parse_verse_reference("مزامير 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_arabic_proverbs_no_article(self):
        """Arabic Proverbs without article 'أمثال 3:5' → Proverbs."""
        result = parse_verse_reference("أمثال 3:5")
        assert result is not None
        assert result.book == "Proverbs"

    def test_arabic_revelation_no_article(self):
        """Arabic Revelation without article 'رؤيا 21:4' → Revelation."""
        result = parse_verse_reference("رؤيا 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_arabic_judges_no_article(self):
        """Arabic Judges without article 'قضاة 4:4' → Judges."""
        result = parse_verse_reference("قضاة 4:4")
        assert result is not None
        assert result.book == "Judges"

    def test_arabic_1_samuel(self):
        """Arabic 1 Samuel '1 صموئيل 17:45' → 1 Samuel."""
        result = parse_verse_reference("1 صموئيل 17:45")
        assert result is not None
        assert result.book == "1 Samuel"

    def test_arabic_in_sentence(self):
        """Arabic verse reference within a longer sentence."""
        result = parse_verse_reference("كما جاء في مزمور 139:12 عن نور الله")
        assert result is not None
        assert result.book == "Psalms"
        assert result.chapter == 139
        assert result.verse_start == 12

    # ── Verse-in-sentence tests ───────────────────────────────────────────────

    def test_russian_in_sentence(self):
        """Russian verse reference within a longer sentence."""
        result = parse_verse_reference("Как сказано в Иоанна 3:16 о любви Бога")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_chinese_in_sentence(self):
        """Chinese verse reference within a longer sentence."""
        result = parse_verse_reference("经文 约翰福音 3:16 所说")
        assert result is not None
        assert result.book == "John"

    def test_korean_in_sentence(self):
        """Korean verse reference within a longer sentence."""
        result = parse_verse_reference("성경 요한복음 3:16 말씀")
        assert result is not None
        assert result.book == "John"

    def test_chinese_preceded_by_cjk_text(self):
        """Chinese book name preceded by other CJK chars (CJK lookbehind fix)."""
        result = parse_verse_reference("根据约翰福音 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_hindi_in_sentence(self):
        """Hindi verse reference within a longer sentence."""
        result = parse_verse_reference("यूहन्ना 3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16


class TestExtractAllReferences:
    """Tests for extract_all_references function (multi-verse extraction)."""

    def test_single_verse(self):
        """Single verse returns one result."""
        results = extract_all_references("John 3:16")
        assert len(results) == 1
        assert results[0].book == "John"

    def test_multiple_verses(self):
        """Multiple verses in text are all extracted."""
        text = "As it says in John 3:16 and also Romans 8:28, we have hope."
        results = extract_all_references(text)
        assert len(results) == 2
        books = {r.book for r in results}
        assert "John" in books
        assert "Romans" in books

    def test_many_verses(self):
        """Many verses in a response are all found."""
        text = "Consider John 3:16, Romans 8:28, Psalm 23:1, " "and Genesis 1:1 for encouragement."
        results = extract_all_references(text)
        assert len(results) == 4

    def test_deduplication(self):
        """Same verse mentioned twice is only returned once."""
        text = "John 3:16 is wonderful. Yes, John 3:16 is amazing."
        results = extract_all_references(text)
        assert len(results) == 1

    def test_no_verses(self):
        """Text with no verses returns empty list."""
        results = extract_all_references("I need some encouragement today")
        assert results == []

    def test_chinese_multiple(self):
        """Multiple Chinese verses are extracted."""
        text = "根据约翰福音 3:16 和罗马书 8:28"
        results = extract_all_references(text)
        assert len(results) == 2
        books = {r.book for r in results}
        assert "John" in books
        assert "Romans" in books

    def test_mixed_languages(self):
        """Mixed English and localized verse refs in same text."""
        text = "Giovanni 3:16 is the same as John 3:16"
        results = extract_all_references(text)
        # Both match "John" — deduplicated
        assert len(results) == 1
        assert results[0].book == "John"


class TestParseStructuredCitations:
    """Tests for parse_structured_citations function."""

    def test_single_citation(self):
        """Parse single citation from HTML comment."""
        text = "Some response text.\n<!-- VERSES: John 3:16 -->"
        results = parse_structured_citations(text)
        assert len(results) == 1
        assert results[0].book == "John"
        assert results[0].chapter == 3
        assert results[0].verse_start == 16

    def test_multiple_citations(self):
        """Parse multiple semicolon-separated citations."""
        text = "Response.\n<!-- VERSES: John 3:16; Romans 8:28; Psalm 23:1 -->"
        results = parse_structured_citations(text)
        assert len(results) == 3
        books = [r.book for r in results]
        assert books == ["John", "Romans", "Psalms"]

    def test_no_comment(self):
        """No VERSES comment returns empty list."""
        text = "Just a normal response without citations."
        results = parse_structured_citations(text)
        assert results == []

    def test_empty_comment(self):
        """Empty VERSES comment returns empty list."""
        text = "Response.\n<!-- VERSES:  -->"
        results = parse_structured_citations(text)
        assert results == []

    def test_verse_range_in_citation(self):
        """Verse range in structured citation."""
        text = "<!-- VERSES: Romans 8:28-30 -->"
        results = parse_structured_citations(text)
        assert len(results) == 1
        assert results[0].verse_end == 30

    def test_citation_with_extra_whitespace(self):
        """Citations with extra whitespace are handled."""
        text = "<!--  VERSES:  John 3:16 ;  Romans 8:28  -->"
        results = parse_structured_citations(text)
        assert len(results) == 2

    def test_citation_in_middle_of_text(self):
        """VERSES comment embedded in longer text."""
        text = (
            "Here is my response about love.\n\n<!-- VERSES: 1 Corinthians 13:4 -->\n\nMore text."
        )
        results = parse_structured_citations(text)
        assert len(results) == 1
        assert results[0].book == "1 Corinthians"
