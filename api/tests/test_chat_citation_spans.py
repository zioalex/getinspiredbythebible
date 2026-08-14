"""BITB-086 — server-emitted citation spans (``extract_citation_spans``).

Unit tests for locating verse citations in the *final* answer text so a
client can linkify them without its own regex. The chat-stream integration
tests (spans align with the completion event, computed post-grounding) live
in ``test_chat_coverage.py::TestChatServiceChatStream`` alongside the rest of
the streaming-completion assertions.
"""

import pytest

from utils.verse_parser import extract_citation_spans


def _assert_self_verifying(text: str, span) -> None:
    """A client asserts message[start:end] == text using UTF-16 code units —
    reproduce that check here against the Python-side offsets."""
    encoded = text.encode("utf-16-le")
    substring = encoded[span.start * 2 : span.end * 2].decode("utf-16-le")
    assert substring == span.text, (
        f"span {span!r} does not self-verify against {text!r}: "
        f"decoded {substring!r} != span.text {span.text!r}"
    )


class TestExtractCitationSpansMultilingual:
    """One citation per language, per the story's 11-language test list."""

    @pytest.mark.parametrize(
        "language,text,expected_text,expected_book,expected_chapter,expected_verse",
        [
            (
                "en",
                "As it says in Romans 8:28, all things work for good.",
                "Romans 8:28",
                "Romans",
                8,
                28,
            ),
            (
                "it",
                "Come dice Giovanni 3:16, Dio ha tanto amato il mondo.",
                "Giovanni 3:16",
                "John",
                3,
                16,
            ),
            (
                "de",
                "Wie es in Johannes 3,16 heißt, liebte Gott die Welt.",
                "Johannes 3,16",
                "John",
                3,
                16,
            ),
            ("es", "Recuerda la palabra de Isaías 41:10 hoy.", "Isaías 41:10", "Isaiah", 41, 10),
            (
                "fr",
                "Comme le dit Jean 3,16, Dieu a tant aimé le monde.",
                "Jean 3,16",
                "John",
                3,
                16,
            ),
            ("pt", "Como diz João 3:16, Deus amou o mundo.", "João 3:16", "John", 3, 16),
            ("ar", "كما يقول يوحنا ٣:١٦، أحب الله العالم.", "يوحنا ٣:١٦", "John", 3, 16),
            (
                "ru",
                "Как сказано в Иоанна 3:16, Бог так возлюбил мир.",
                "Иоанна 3:16",
                "John",
                3,
                16,
            ),
            ("zh", "正如约翰福音 3:16所说，神爱世人。", "约翰福音 3:16", "John", 3, 16),
            ("hi", "जैसा कि यूहन्ना ५:२४ में कहा गया है।", "यूहन्ना ५:२४", "John", 5, 24),
            ("ko", "요한복음 3:16에 이렇게 나와 있습니다.", "요한복음 3:16", "John", 3, 16),
        ],
    )
    def test_span_located_and_self_verifying(
        self, language, text, expected_text, expected_book, expected_chapter, expected_verse
    ):
        spans = extract_citation_spans(text)
        assert len(spans) == 1, f"[{language}] expected exactly one span in {text!r}, got {spans}"
        span = spans[0]
        assert span.text == expected_text, f"[{language}] text mismatch: {span.text!r}"
        assert span.book == expected_book, f"[{language}] book mismatch: {span.book!r}"
        assert span.chapter == expected_chapter, f"[{language}] chapter mismatch"
        assert span.verse == expected_verse, f"[{language}] verse mismatch"
        assert span.verse_end is None
        assert span.occurrence == 0
        _assert_self_verifying(text, span)


class TestExtractCitationSpansPunctuation:
    def test_parenthesized_reference_excludes_parens(self):
        text = "God is love (1 John 4:8), full stop."
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        assert spans[0].text == "1 John 4:8"
        assert "(" not in spans[0].text and ")" not in spans[0].text
        _assert_self_verifying(text, spans[0])

    def test_fullwidth_bracketed_reference_excludes_brackets(self):
        text = "（约翰福音 3:16）说"
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        assert spans[0].text == "约翰福音 3:16"
        _assert_self_verifying(text, spans[0])

    def test_guillemet_bracketed_reference_excludes_guillemets(self):
        text = "《约翰福音 3:16》说"
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        assert spans[0].text == "约翰福音 3:16"
        _assert_self_verifying(text, spans[0])


class TestExtractCitationSpansRanges:
    def test_verse_range_carries_verse_end(self):
        text = "Read Romans 8:28-30 today."
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        assert spans[0].verse == 28
        assert spans[0].verse_end == 30
        _assert_self_verifying(text, spans[0])

    def test_single_verse_has_no_verse_end(self):
        text = "Read John 3:16 today."
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        assert spans[0].verse_end is None


class TestExtractCitationSpansOccurrence:
    def test_repeated_identical_citation_increments_occurrence(self):
        text = "John 3:16 is famous. Later, John 3:16 is quoted again."
        spans = extract_citation_spans(text)
        assert len(spans) == 2
        assert spans[0].occurrence == 0
        assert spans[1].occurrence == 1
        for span in spans:
            _assert_self_verifying(text, span)
        # occurrence is scoped to identical `text`, not a global citation index —
        # both spans share the same literal substring, so it distinguishes them.
        assert spans[0].text == spans[1].text == "John 3:16"

    def test_distinct_citations_each_start_at_occurrence_zero(self):
        text = "See John 3:16 and also Romans 8:28."
        spans = extract_citation_spans(text)
        assert len(spans) == 2
        assert spans[0].occurrence == 0
        assert spans[1].occurrence == 0


class TestExtractCitationSpansSurrogatePairs:
    def test_offsets_are_utf16_code_units_not_code_points(self):
        """An emoji (astral, 2 UTF-16 code units / 1 Python code point) before
        the citation must shift the UTF-16 offset by 2, not 1 — the exact
        off-by-N the story's offset-unit AC exists to prevent."""
        text = "🙏 (John 3:16) brings comfort."
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        span = spans[0]
        # Python code-point index of "John" is 3 ("🙏 (J..." -> indices 0,1,2,3);
        # the emoji is 1 code point but 2 UTF-16 code units, so the UTF-16
        # offset is shifted by 1 relative to the code-point index: 4.
        assert span.start == 4
        _assert_self_verifying(text, span)

    def test_multiple_astral_characters_accumulate_correctly(self):
        text = "🙏😀🎉 (Romans 8:28-30) today."
        spans = extract_citation_spans(text)
        assert len(spans) == 1
        _assert_self_verifying(text, spans[0])


class TestExtractCitationSpansNoCitations:
    def test_no_citation_returns_empty_list(self):
        assert extract_citation_spans("Just an encouraging message, no references here.") == []

    def test_empty_string_returns_empty_list(self):
        assert extract_citation_spans("") == []
