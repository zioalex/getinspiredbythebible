"""Tests for post-generation verse grounding.

Covers inline-quote extraction across languages, the fabricated/mismatched/partial
classification, canonical-text substitution, and the metric/contract behavior that
rewrites a hallucinated verse quote to the real DB text.
"""

from dataclasses import dataclass

from chat.verse_grounding import (
    GROUNDING_SIMILARITY_THRESHOLD,
    _normalize_for_compare,
    ground_response,
)
from utils.verse_parser import extract_inline_quotes


@dataclass
class FakeVerse:
    """Stand-in for scripture.search.VerseResult (only the fields grounding uses)."""

    book: str
    chapter: int
    verse: int
    text: str


# Canonical reference texts used across the tests.
ISAIAH_41_10_IT = (
    "Non temere, perché io sono con te; non smarrirti, perché io sono il tuo Dio. "
    "Ti rendo forte e ti vengo in aiuto e ti sostengo con la destra vittoriosa "
    "della mia giustizia."
)
JOHN_3_16_EN = "For God so loved the world, that he gave his only begotten Son."


class TestExtractInlineQuotes:
    def test_quote_then_parenthetical_reference(self):
        text = 'He wrote "For God so loved the world." (John 3:16) today.'
        quotes = extract_inline_quotes(text)
        assert len(quotes) == 1
        assert str(quotes[0].reference) == "John 3:16"
        assert quotes[0].quoted_text == "For God so loved the world."

    def test_reference_then_quote_with_connector(self):
        text = 'As John 3:16 says: "For God so loved the world."'
        quotes = extract_inline_quotes(text)
        assert len(quotes) == 1
        assert str(quotes[0].reference) == "John 3:16"

    def test_italian_guillemets(self):
        text = "La verità «Dio è amore eterno e infinito» (1 Giovanni 4:8) consola."
        quotes = extract_inline_quotes(text)
        assert len(quotes) == 1
        assert str(quotes[0].reference) == "1 John 4:8"

    def test_german_low_high_quotes(self):
        text = "Er sagte „Selig sind die Barmherzigen“ (Matthäus 5:7) heute."
        quotes = extract_inline_quotes(text)
        assert len(quotes) == 1
        assert str(quotes[0].reference) == "Matthew 5:7"

    def test_quote_without_reference_is_ignored(self):
        text = 'She said "what a lovely day" while walking.'
        assert extract_inline_quotes(text) == []

    def test_reference_without_quote_is_ignored(self):
        text = "Romans 8:28 is a comforting passage to remember."
        assert extract_inline_quotes(text) == []

    def test_narrative_gap_not_misattributed(self):
        # A nearby quote that is not introduced by the reference must not bind.
        text = 'John 3:16 and also "my dog is very cute" today.'
        assert extract_inline_quotes(text) == []

    def test_offsets_point_at_quoted_text(self):
        text = '"For God so loved the world." (John 3:16)'
        q = extract_inline_quotes(text)[0]
        assert text[q.span[0] : q.span[1]] == q.quoted_text


class TestNormalize:
    def test_strips_punctuation_and_case(self):
        assert _normalize_for_compare('  "Hello, WORLD!" ') == "hello world"

    def test_collapses_newlines(self):
        assert _normalize_for_compare("line one\nline two") == "line one line two"

    def test_drops_ellipsis(self):
        assert _normalize_for_compare("the world... and more") == "the world and more"


class TestGroundResponse:
    def test_italian_fabrication_is_corrected(self):
        # The reported bug: a reconstructed-from-memory Isaiah 41:10.
        text = (
            'Un altro passaggio utile è: "Non temere, perché io sono con te; non '
            "smarrirti, perché io sono il tuo Dio; io ti fortirò, io ti aiuterò, io ti "
            'sosterrò con la mia destra fedele" (Isaia 41:10). Spero ti aiuti.'
        )
        isa = FakeVerse("Isaiah", 41, 10, ISAIAH_41_10_IT)
        corrected, corrections = ground_response(text, [isa], context_refs=set())
        assert len(corrections) == 1
        assert corrections[0].reason == "fabricated"  # was not in Scripture Context
        assert ISAIAH_41_10_IT in corrected
        assert "io ti fortirò" not in corrected
        # Reference and surrounding prose are preserved.
        assert "(Isaia 41:10)" in corrected
        assert corrected.startswith("Un altro passaggio utile è:")

    def test_mismatch_when_verse_was_in_context(self):
        text = 'John 3:16 says: "God really loved the entire planet a whole lot."'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN)
        corrected, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert len(corrections) == 1
        assert corrections[0].reason == "mismatched"
        assert JOHN_3_16_EN in corrected

    def test_faithful_quote_unchanged(self):
        text = f'As John 3:16 says: "{JOHN_3_16_EN}"'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN)
        corrected, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert corrections == []
        assert corrected == text

    def test_partial_quote_not_flagged(self):
        text = 'John 3:16 reminds us: "For God so loved the world".'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN)
        corrected, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert corrections == []
        assert corrected == text

    def test_very_short_quote_skipped(self):
        text = 'John 3:16 says: "He gave."'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN)
        _, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert corrections == []

    def test_range_concatenation_partial_accepted(self):
        # An LLM quoting only verse 23 of a 5:22-23 range must not be flagged.
        v22 = FakeVerse("Galatians", 5, 22, "But the fruit of the Spirit is love, joy, peace,")
        v23 = FakeVerse(
            "Galatians", 5, 23, "gentleness, self-control: against such there is no law."
        )
        text = 'Galatians 5:22-23 lists "gentleness, self-control: against such there is no law."'
        _, corrections = ground_response(
            text, [v22, v23], context_refs={("galatians", 5, 22), ("galatians", 5, 23)}
        )
        assert corrections == []

    def test_unresolved_detected_but_text_unchanged_by_default(self):
        text = 'Consider also: "a fabricated line never written here" (Obadiah 1:5).'
        corrected, corrections = ground_response(text, [], context_refs=set())
        assert len(corrections) == 1
        assert corrections[0].reason == "unresolved"
        assert corrections[0].corrected_quote is None
        assert corrected == text  # detect-and-log only

    def test_unresolved_stripped_when_enabled(self):
        text = 'Consider also: "a fabricated line never written here" (Obadiah 1:5).'
        corrected, corrections = ground_response(
            text, [], context_refs=set(), strip_unresolved=True
        )
        assert corrections[0].reason == "unresolved"
        assert "a fabricated line never written here" not in corrected
        assert "(Obadiah 1:5)" in corrected

    def test_no_quotes_returns_input_unchanged(self):
        text = "Take heart and be encouraged today."
        corrected, corrections = ground_response(text, [], context_refs=set())
        assert corrected == text
        assert corrections == []

    def test_threshold_constant_is_reasonable(self):
        assert 0.8 <= GROUNDING_SIMILARITY_THRESHOLD < 1.0
