"""Tests for the verse reference and prayer pattern parser."""

import pytest

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

    # ── Chinese guillemets 《》 ────────────────────────────────────────────────

    def test_chinese_guillemet_john(self):
        """Chinese guillemet '《约翰福音》3:16' → John."""
        result = parse_verse_reference("《约翰福音》3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_chinese_guillemet_genesis_with_space(self):
        """Chinese guillemet with space '《创世记》 1:1' → Genesis."""
        result = parse_verse_reference("《创世记》 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_chinese_guillemet_psalms(self):
        """Chinese guillemet '《诗篇》23:1' → Psalms."""
        result = parse_verse_reference("《诗篇》23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_chinese_guillemet_in_sentence(self):
        """Chinese guillemet in sentence context."""
        result = parse_verse_reference("请阅读《约翰福音》3:16")
        assert result is not None
        assert result.book == "John"

    def test_chinese_guillemet_extract_multiple(self):
        """Extract multiple guillemet-wrapped references."""
        results = extract_all_references("《约翰福音》3:16和《诗篇》23:1")
        assert len(results) == 2
        books = {r.book for r in results}
        assert "John" in books
        assert "Psalms" in books

    def test_chinese_genesis_variant_ji(self):
        """Chinese Genesis variant '创世纪' (with 纪) → Genesis."""
        result = parse_verse_reference("《创世纪》1:1")
        assert result is not None
        assert result.book == "Genesis"
        assert result.chapter == 1
        assert result.verse_start == 1

    # ── Chinese 记↔纪 swap variants ──────────────────────────────────────────
    # CUV uses 记 for most OT books but 纪 for Kings.  LLMs frequently swap
    # them because both characters are pronounced jì and mean "record".

    def test_chinese_exodus_ji_variant(self):
        """出埃及纪 (纪 variant) → Exodus."""
        result = parse_verse_reference("出埃及纪 3:14")
        assert result is not None
        assert result.book == "Exodus"

    def test_chinese_leviticus_ji_variant(self):
        """利未纪 (纪 variant) → Leviticus."""
        result = parse_verse_reference("利未纪 19:18")
        assert result is not None
        assert result.book == "Leviticus"

    def test_chinese_numbers_ji_variant(self):
        """民数纪 (纪 variant) → Numbers."""
        result = parse_verse_reference("民数纪 6:24")
        assert result is not None
        assert result.book == "Numbers"

    def test_chinese_deuteronomy_ji_variant(self):
        """申命纪 (纪 variant) → Deuteronomy."""
        result = parse_verse_reference("申命纪 6:4")
        assert result is not None
        assert result.book == "Deuteronomy"

    def test_chinese_joshua_ji_variant(self):
        """约书亚纪 (纪 variant) → Joshua."""
        result = parse_verse_reference("约书亚纪 1:9")
        assert result is not None
        assert result.book == "Joshua"

    def test_chinese_judges_ji_variant(self):
        """士师纪 (纪 variant) → Judges."""
        result = parse_verse_reference("士师纪 6:12")
        assert result is not None
        assert result.book == "Judges"

    def test_chinese_ruth_ji_variant(self):
        """路得纪 (纪 variant) → Ruth."""
        result = parse_verse_reference("路得纪 1:16")
        assert result is not None
        assert result.book == "Ruth"

    def test_chinese_1samuel_ji_variant(self):
        """撒母耳纪上 (纪 variant) → 1 Samuel."""
        result = parse_verse_reference("撒母耳纪上 3:10")
        assert result is not None
        assert result.book == "1 Samuel"

    def test_chinese_2samuel_ji_variant(self):
        """撒母耳纪下 (纪 variant) → 2 Samuel."""
        result = parse_verse_reference("撒母耳纪下 7:16")
        assert result is not None
        assert result.book == "2 Samuel"

    def test_chinese_1kings_ji_variant(self):
        """列王记上 (记 variant) → 1 Kings."""
        result = parse_verse_reference("列王记上 18:1")
        assert result is not None
        assert result.book == "1 Kings"

    def test_chinese_2kings_ji_variant(self):
        """列王记下 (记 variant) → 2 Kings."""
        result = parse_verse_reference("列王记下 5:14")
        assert result is not None
        assert result.book == "2 Kings"

    def test_chinese_ezra_ji_variant(self):
        """以斯拉纪 (纪 variant) → Ezra."""
        result = parse_verse_reference("以斯拉纪 7:10")
        assert result is not None
        assert result.book == "Ezra"

    def test_chinese_nehemiah_ji_variant(self):
        """尼希米纪 (纪 variant) → Nehemiah."""
        result = parse_verse_reference("尼希米纪 8:10")
        assert result is not None
        assert result.book == "Nehemiah"

    def test_chinese_esther_ji_variant(self):
        """以斯帖纪 (纪 variant) → Esther."""
        result = parse_verse_reference("以斯帖纪 4:14")
        assert result is not None
        assert result.book == "Esther"

    def test_chinese_job_ji_variant(self):
        """约伯纪 (纪 variant) → Job."""
        result = parse_verse_reference("约伯纪 1:21")
        assert result is not None
        assert result.book == "Job"

    # ── Chinese Catholic (思高本) name variants ──────────────────────────────
    # LLMs trained on Catholic Chinese texts may produce 思高本 names instead
    # of the CUV/和合本 names.

    def test_chinese_catholic_matthew(self):
        """Catholic 玛窦福音 → Matthew."""
        result = parse_verse_reference("玛窦福音 5:3")
        assert result is not None
        assert result.book == "Matthew"

    def test_chinese_catholic_mark(self):
        """Catholic 马尔谷福音 → Mark."""
        result = parse_verse_reference("马尔谷福音 1:1")
        assert result is not None
        assert result.book == "Mark"

    def test_chinese_catholic_john(self):
        """Catholic 若望福音 → John."""
        result = parse_verse_reference("若望福音 3:16")
        assert result is not None
        assert result.book == "John"

    def test_chinese_catholic_acts(self):
        """Catholic 宗徒大事录 → Acts."""
        result = parse_verse_reference("宗徒大事录 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_chinese_catholic_revelation(self):
        """Catholic 默示录 → Revelation."""
        result = parse_verse_reference("默示录 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_chinese_catholic_1corinthians(self):
        """Catholic 格林多前书 → 1 Corinthians."""
        result = parse_verse_reference("格林多前书 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_chinese_catholic_2corinthians(self):
        """Catholic 格林多后书 → 2 Corinthians."""
        result = parse_verse_reference("格林多后书 5:17")
        assert result is not None
        assert result.book == "2 Corinthians"

    def test_chinese_catholic_1john(self):
        """Catholic 若望一书 → 1 John."""
        result = parse_verse_reference("若望一书 4:8")
        assert result is not None
        assert result.book == "1 John"

    def test_chinese_catholic_2john(self):
        """Catholic 若望二书 → 2 John."""
        result = parse_verse_reference("若望二书 1:6")
        assert result is not None
        assert result.book == "2 John"

    def test_chinese_catholic_3john(self):
        """Catholic 若望三书 → 3 John."""
        result = parse_verse_reference("若望三书 1:4")
        assert result is not None
        assert result.book == "3 John"

    def test_chinese_catholic_james(self):
        """Catholic 雅各伯书 → James."""
        result = parse_verse_reference("雅各伯书 1:5")
        assert result is not None
        assert result.book == "James"

    def test_chinese_catholic_jude(self):
        """Catholic 犹达书 → Jude."""
        result = parse_verse_reference("犹达书 1:3")
        assert result is not None
        assert result.book == "Jude"

    def test_chinese_catholic_guillemet(self):
        """Catholic name inside guillemets: 《默示录》21:4 → Revelation."""
        result = parse_verse_reference("《默示录》21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_chinese_ji_variant_guillemet(self):
        """记↔纪 variant inside guillemets: 《出埃及纪》3:14 → Exodus."""
        result = parse_verse_reference("《出埃及纪》3:14")
        assert result is not None
        assert result.book == "Exodus"

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

    def test_korean_no_space_john(self):
        """Korean John without space '요한복음3:16' → John."""
        result = parse_verse_reference("요한복음3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_korean_no_space_psalms(self):
        """Korean Psalms without space '시편23:1' → Psalms."""
        result = parse_verse_reference("시편23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_korean_no_space_genesis(self):
        """Korean Genesis without space '창세기1:1' → Genesis."""
        result = parse_verse_reference("창세기1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_korean_no_space_revelation(self):
        """Korean Revelation without space '요한계시록21:4' → Revelation."""
        result = parse_verse_reference("요한계시록21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_korean_corner_bracket_john(self):
        """Korean John with corner brackets '「요한복음」3:16' → John."""
        result = parse_verse_reference("「요한복음」3:16")
        assert result is not None
        assert result.book == "John"

    def test_korean_double_corner_bracket_psalms(self):
        """Korean Psalms with double corner brackets '『시편』23:1' → Psalms."""
        result = parse_verse_reference("『시편』23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_korean_revelation_short(self):
        """Korean Revelation short form '계시록 21:4' → Revelation."""
        result = parse_verse_reference("계시록 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_korean_lamentations_short(self):
        """Korean Lamentations short form '애가 3:3' → Lamentations."""
        result = parse_verse_reference("애가 3:3")
        assert result is not None
        assert result.book == "Lamentations"

    def test_korean_acts_short(self):
        """Korean Acts short form '행전 2:38' → Acts."""
        result = parse_verse_reference("행전 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_korean_embedded_no_space(self):
        """Korean ref without space embedded in Korean text."""
        result = parse_verse_reference("성경에서 요한복음3:16을 읽으세요")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_korean_matthew(self):
        """Korean Matthew '마태복음 5:3' → Matthew."""
        result = parse_verse_reference("마태복음 5:3")
        assert result is not None
        assert result.book == "Matthew"

    def test_korean_hebrews(self):
        """Korean Hebrews '히브리서 11:1' → Hebrews."""
        result = parse_verse_reference("히브리서 11:1")
        assert result is not None
        assert result.book == "Hebrews"

    def test_korean_range(self):
        """Korean verse range '요한복음 3:16-18' → John 3:16."""
        result = parse_verse_reference("요한복음 3:16-18")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16
        assert result.verse_end == 18

    def test_korean_corner_bracket_no_space(self):
        """Korean corner bracket without space '「요한복음」3:16' → John."""
        result = parse_verse_reference("「요한복음」3:16")
        assert result is not None
        assert result.book == "John"

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

    # ── Arabic (expanded) ────────────────────────────────────────────────────

    def test_arabic_matthew(self):
        """Arabic Matthew 'متى 5:3' → Matthew."""
        result = parse_verse_reference("متى 5:3")
        assert result is not None
        assert result.book == "Matthew"

    def test_arabic_mark(self):
        """Arabic Mark 'مرقس 1:1' → Mark."""
        result = parse_verse_reference("مرقس 1:1")
        assert result is not None
        assert result.book == "Mark"

    def test_arabic_luke(self):
        """Arabic Luke 'لوقا 2:1' → Luke."""
        result = parse_verse_reference("لوقا 2:1")
        assert result is not None
        assert result.book == "Luke"

    def test_arabic_acts_full(self):
        """Arabic Acts full form 'أعمال الرسل 2:38' → Acts."""
        result = parse_verse_reference("أعمال الرسل 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_arabic_acts_short(self):
        """Arabic Acts short form 'أعمال 2:38' → Acts."""
        result = parse_verse_reference("أعمال 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_arabic_lamentations(self):
        """Arabic Lamentations 'مراثي إرميا 3:22' → Lamentations."""
        result = parse_verse_reference("مراثي إرميا 3:22")
        assert result is not None
        assert result.book == "Lamentations"

    def test_arabic_hebrews(self):
        """Arabic Hebrews 'عبرانيين 11:1' → Hebrews."""
        result = parse_verse_reference("عبرانيين 11:1")
        assert result is not None
        assert result.book == "Hebrews"

    def test_arabic_james(self):
        """Arabic James 'يعقوب 1:2' → James."""
        result = parse_verse_reference("يعقوب 1:2")
        assert result is not None
        assert result.book == "James"

    def test_arabic_range(self):
        """Arabic verse range 'يوحنا 3:16-18' → John 3:16-18."""
        result = parse_verse_reference("يوحنا 3:16-18")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16
        assert result.verse_end == 18

    def test_arabic_eastern_numerals(self):
        """Arabic with Eastern Arabic numerals 'يوحنا ٣:١٦' → John 3:16."""
        result = parse_verse_reference("يوحنا ٣:١٦")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_arabic_eastern_numerals_genesis(self):
        """Arabic Genesis with Eastern Arabic numerals 'تكوين ١:١' → Genesis 1:1."""
        result = parse_verse_reference("تكوين ١:١")
        assert result is not None
        assert result.book == "Genesis"
        assert result.chapter == 1
        assert result.verse_start == 1

    def test_arabic_tashkeel_john(self):
        """Arabic John with tashkeel diacritics 'يُوحَنَّا 3:16' → John."""
        result = parse_verse_reference("يُوحَنَّا 3:16")
        assert result is not None
        assert result.book == "John"

    def test_arabic_guillemet(self):
        """Arabic with guillemets '«يوحنا» 3:16' → John."""
        result = parse_verse_reference("«يوحنا» 3:16")
        assert result is not None
        assert result.book == "John"

    def test_arabic_2_corinthians(self):
        """Arabic 2 Corinthians '2 كورنثوس 5:17' → 2 Corinthians."""
        result = parse_verse_reference("2 كورنثوس 5:17")
        assert result is not None
        assert result.book == "2 Corinthians"

    def test_arabic_song_variant(self):
        """Arabic Song of Solomon LLM variant 'نشيد الأناشيد 2:1' → Song of Solomon."""
        result = parse_verse_reference("نشيد الأناشيد 2:1")
        assert result is not None
        assert result.book == "Song of Solomon"

    # ── Verse-in-sentence tests ───────────────────────────────────────────────

    def test_russian_in_sentence(self):
        """Russian verse reference within a longer sentence."""
        result = parse_verse_reference("Как сказано в Иоанна 3:16 о любви Бога")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    # ── Russian (expanded — abbreviations, ё/е, word-ordinals) ───────────────

    def test_russian_abbreviation_in(self):
        """Russian abbreviation 'Ин 3:16' → John."""
        result = parse_verse_reference("Ин 3:16")
        assert result is not None
        assert result.book == "John"

    def test_russian_abbreviation_mf(self):
        """Russian abbreviation 'Мф 5:3' → Matthew."""
        result = parse_verse_reference("Мф 5:3")
        assert result is not None
        assert result.book == "Matthew"

    def test_russian_abbreviation_mk(self):
        """Russian abbreviation 'Мк 1:1' → Mark."""
        result = parse_verse_reference("Мк 1:1")
        assert result is not None
        assert result.book == "Mark"

    def test_russian_abbreviation_lk(self):
        """Russian abbreviation 'Лк 2:1' → Luke."""
        result = parse_verse_reference("Лк 2:1")
        assert result is not None
        assert result.book == "Luke"

    def test_russian_abbreviation_ps(self):
        """Russian abbreviation 'Пс 23:1' → Psalms."""
        result = parse_verse_reference("Пс 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_russian_abbreviation_rim(self):
        """Russian abbreviation 'Рим 8:28' → Romans."""
        result = parse_verse_reference("Рим 8:28")
        assert result is not None
        assert result.book == "Romans"

    def test_russian_abbreviation_byt(self):
        """Russian abbreviation 'Быт 1:1' → Genesis."""
        result = parse_verse_reference("Быт 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_russian_abbreviation_otkr(self):
        """Russian abbreviation 'Откр 21:4' → Revelation."""
        result = parse_verse_reference("Откр 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_russian_abbreviation_deyan(self):
        """Russian abbreviation 'Деян 2:38' → Acts."""
        result = parse_verse_reference("Деян 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_russian_abbreviation_evr(self):
        """Russian abbreviation 'Евр 11:1' → Hebrews."""
        result = parse_verse_reference("Евр 11:1")
        assert result is not None
        assert result.book == "Hebrews"

    def test_russian_abbreviation_gal(self):
        """Russian abbreviation 'Гал 3:28' → Galatians."""
        result = parse_verse_reference("Гал 3:28")
        assert result is not None
        assert result.book == "Galatians"

    def test_russian_abbreviation_ef(self):
        """Russian abbreviation 'Еф 2:8' → Ephesians."""
        result = parse_verse_reference("Еф 2:8")
        assert result is not None
        assert result.book == "Ephesians"

    def test_russian_abbreviation_iak(self):
        """Russian abbreviation 'Иак 1:2' → James."""
        result = parse_verse_reference("Иак 1:2")
        assert result is not None
        assert result.book == "James"

    def test_russian_yo_variant_iov(self):
        """Russian ё variant 'Иёв 1:1' → Job (ё instead of о)."""
        result = parse_verse_reference("Иёв 1:1")
        assert result is not None
        assert result.book == "Job"

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

    # ── Hindi (expanded) ─────────────────────────────────────────────────────

    def test_hindi_genesis(self):
        """Hindi Genesis 'उत्पत्ति 1:1' → Genesis."""
        result = parse_verse_reference("उत्पत्ति 1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_hindi_psalms(self):
        """Hindi Psalms 'भजन संहिता 23:1' → Psalms."""
        result = parse_verse_reference("भजन संहिता 23:1")
        assert result is not None
        assert result.book == "Psalms"

    def test_hindi_proverbs(self):
        """Hindi Proverbs 'नीतिवचन 3:5' → Proverbs."""
        result = parse_verse_reference("नीतिवचन 3:5")
        assert result is not None
        assert result.book == "Proverbs"

    def test_hindi_revelation(self):
        """Hindi Revelation 'प्रकाशितवाक्य 21:4' → Revelation."""
        result = parse_verse_reference("प्रकाशितवाक्य 21:4")
        assert result is not None
        assert result.book == "Revelation"

    def test_hindi_acts(self):
        """Hindi Acts 'प्रेरितों के काम 2:38' → Acts (3-word with के connector)."""
        result = parse_verse_reference("प्रेरितों के काम 2:38")
        assert result is not None
        assert result.book == "Acts"

    def test_hindi_romans(self):
        """Hindi Romans 'रोमियों 8:28' → Romans."""
        result = parse_verse_reference("रोमियों 8:28")
        assert result is not None
        assert result.book == "Romans"

    def test_hindi_1_corinthians(self):
        """Hindi 1 Corinthians '1 कुरिन्थियों 13:4' → 1 Corinthians."""
        result = parse_verse_reference("1 कुरिन्थियों 13:4")
        assert result is not None
        assert result.book == "1 Corinthians"

    def test_hindi_hebrews(self):
        """Hindi Hebrews 'इब्रानियों 11:1' → Hebrews."""
        result = parse_verse_reference("इब्रानियों 11:1")
        assert result is not None
        assert result.book == "Hebrews"

    def test_hindi_james(self):
        """Hindi James 'याकूब 1:2' → James."""
        result = parse_verse_reference("याकूब 1:2")
        assert result is not None
        assert result.book == "James"

    def test_hindi_range(self):
        """Hindi verse range 'यूहन्ना 3:16-18' → John 3:16-18."""
        result = parse_verse_reference("यूहन्ना 3:16-18")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16
        assert result.verse_end == 18

    def test_hindi_no_space_john(self):
        """Hindi John without space 'यूहन्ना3:16' → John."""
        result = parse_verse_reference("यूहन्ना3:16")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_hindi_no_space_genesis(self):
        """Hindi Genesis without space 'उत्पत्ति1:1' → Genesis."""
        result = parse_verse_reference("उत्पत्ति1:1")
        assert result is not None
        assert result.book == "Genesis"

    def test_hindi_embedded_sentence(self):
        """Hindi ref embedded in Hindi sentence."""
        result = parse_verse_reference("कृपया यूहन्ना 3:16 पढ़ें")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_hindi_devanagari_numerals(self):
        """Hindi with Devanagari numerals 'यूहन्ना ३:१६' → John 3:16."""
        result = parse_verse_reference("यूहन्ना ३:१६")
        assert result is not None
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse_start == 16

    def test_hindi_devanagari_numerals_genesis(self):
        """Hindi Genesis with Devanagari numerals 'उत्पत्ति १:१' → Genesis 1:1."""
        result = parse_verse_reference("उत्पत्ति १:१")
        assert result is not None
        assert result.book == "Genesis"
        assert result.chapter == 1
        assert result.verse_start == 1

    def test_hindi_romans_anusvara_dropped_alias(self):
        """Hindi Romans without trailing anusvara 'रोमियो 5:3-4' → Romans 5:3-4.

        LLMs commonly drop the oblique-case ं ending IRV uses (रोमियों);
        HINDI_ALIASES maps this casual spelling to the same canonical book.
        """
        result = parse_verse_reference("रोमियो 5:3-4")
        assert result is not None
        assert result.book == "Romans"
        assert result.chapter == 5
        assert result.verse_start == 3
        assert result.verse_end == 4

    def test_hindi_galatians_anusvara_dropped_alias(self):
        """Hindi Galatians without trailing anusvara 'गलातियो 5:22' → Galatians."""
        result = parse_verse_reference("गलातियो 5:22")
        assert result is not None
        assert result.book == "Galatians"


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

    def test_comma_separated_citation(self):
        """Comma-separated citations (LLM doesn't always follow the semicolon
        instruction in the prompt) are still fully parsed, not just the first."""
        text = "<!-- VERSES: John 3:16, Romans 8:28, Psalm 23:1 -->"
        results = parse_structured_citations(text)
        assert len(results) == 3
        books = [r.book for r in results]
        assert books == ["John", "Romans", "Psalms"]

    def test_hindi_comma_separated_citation_with_range_and_alias(self):
        """Reported bug: comma-separated Hindi VERSES comment with a verse
        range, where the middle book uses the anusvara-dropped alias spelling
        (रोमियो instead of रोमियों) — all three references, and the full
        range, must be recovered."""
        text = "<!-- VERSES: याकूब 1:3, रोमियो 5:3-4, गलातियों 5:22 -->"
        results = parse_structured_citations(text)
        assert len(results) == 3
        assert [r.book for r in results] == ["James", "Romans", "Galatians"]
        romans = results[1]
        assert romans.chapter == 5
        assert romans.verse_start == 3
        assert romans.verse_end == 4


class TestWrappedReferencesAllLanguages:
    """Bracketed/parenthesized citations — `(John 3:16)`, `[Salmo 23:1]`,
    Chinese fullwidth `（约翰福音 3:16）` — must parse in every supported language.

    Regression: the backend pattern used a positive-whitelist lookbehind that
    omitted `(` / `[`, so wrapped references (the single most common citation
    format) were silently dropped and never resolved from the DB. Per AGENTS.md
    "Multilingual & Multi-Version Correctness", this is checked across all 11
    languages plus numbered books, ranges, and ASCII/fullwidth brackets.
    """

    # (label, wrapped_text, expected_canonical_reference)
    PAREN_CASES = [
        ("en", "Take heart (John 3:16) today.", "John 3:16"),
        ("en-bracket", "Hope [Psalm 23:1] holds.", "Psalms 23:1"),
        ("en-range", "Nothing separates us (Romans 8:38-39).", "Romans 8:38-39"),
        ("en-numbered", "Love (1 Corinthians 13:4) is patient.", "1 Corinthians 13:4"),
        ("it", "Coraggio (Giovanni 3:16).", "John 3:16"),
        ("it-numbered", "Dio è amore (1 Giovanni 4:8).", "1 John 4:8"),
        ("de-comma", "Trost (Johannes 3,16) heute.", "John 3:16"),
        ("de-numbered", "Liebe (1. Korinther 13,4).", "1 Corinthians 13:4"),
        ("es", "Ánimo (Juan 3:16).", "John 3:16"),
        ("fr", "Courage (Jean 3:16).", "John 3:16"),
        ("pt", "Coragem (João 3:16).", "John 3:16"),
        ("ru", "Утешение (Иоанна 3:16).", "John 3:16"),
        ("ar", "تعزية (يوحنا 3:16).", "John 3:16"),
        ("hi", "सांत्वना (यूहन्ना 3:16)।", "John 3:16"),
        ("zh-fullwidth", "安慰（约翰福音 3:16）。", "John 3:16"),
        ("ko", "위로 (요한복음 3:16).", "John 3:16"),
    ]

    @pytest.mark.parametrize("label,text,expected", PAREN_CASES, ids=[c[0] for c in PAREN_CASES])
    def test_parenthesized_reference_parses(self, label, text, expected):
        refs = [str(r) for r in extract_all_references(text)]
        assert expected in refs, f"[{label}] {text!r} -> {refs}, expected {expected}"

    @pytest.mark.parametrize("label,text,expected", PAREN_CASES, ids=[c[0] for c in PAREN_CASES])
    def test_parse_single_parenthesized_reference(self, label, text, expected):
        ref = parse_verse_reference(text)
        assert ref is not None and str(ref) == expected, f"[{label}] got {ref}"

    def test_numbered_book_in_parens_keeps_prefix(self):
        # Regression: "(1 Giovanni 4:8)" previously resolved to "John 4:8" (the
        # "1" was stranded outside the match).
        assert str(parse_verse_reference("(1 Giovanni 4:8)")) == "1 John 4:8"

    def test_unwrapped_references_still_parse(self):
        # The fix must not regress the common unwrapped form.
        assert [str(r) for r in extract_all_references("Isaiah 41:10 and John 3:16")] == [
            "Isaiah 41:10",
            "John 3:16",
        ]

    def test_multiple_parenthesized_references(self):
        refs = [str(r) for r in extract_all_references("vedi (Giovanni 3:16) e (Salmo 23:1)")]
        assert refs == ["John 3:16", "Psalms 23:1"]
