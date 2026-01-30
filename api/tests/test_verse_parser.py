"""Tests for the verse reference and prayer pattern parser."""

from utils.verse_parser import (
    VerseReference,
    extract_references,
    find_prayer_reference,
    is_verse_lookup_request,
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
