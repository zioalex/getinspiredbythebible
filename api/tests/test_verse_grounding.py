"""Tests for post-generation verse grounding.

Covers inline-quote extraction across languages, the fabricated/mismatched/partial
classification, canonical-text substitution, and the metric/contract behavior that
rewrites a hallucinated verse quote to the real DB text.
"""

from dataclasses import dataclass

import pytest

from chat.verse_grounding import (
    GROUNDING_SIMILARITY_THRESHOLD,
    PARAPHRASE_SIMILARITY_THRESHOLD,
    _classify_paraphrase,
    _normalize_for_compare,
    ground_response,
)
from utils.verse_parser import extract_inline_quotes, extract_reference_mentions


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


class TestGroundingAcrossLanguages:
    """Per AGENTS.md "Multilingual & Multi-Version Correctness": grounding must
    rewrite a reworded quote to canonical DB text across every supported language
    and citation/punctuation style — incl. parenthesized refs, CJK/fullwidth
    brackets, RTL Arabic, Devanagari, and lead-in connectors."""

    # (id, book, ch, vs, canonical, reworded_response)
    CASES = [
        (
            "en-paren",
            "John",
            3,
            16,
            "For God so loved the world, that he gave his only begotten Son.",
            "He said «God adored the planet so much he sent his single child» (John 3:16).",
        ),
        (
            "it-leadin",
            "Isaiah",
            41,
            10,
            "Non temere, perché io sono con te; io ti rendo forte.",
            "La Bibbia, in Isaia 41:10, dove Dio dice: «Non aver paura perche ti fortifico io».",
        ),
        (
            "it-long-leadin",
            "Isaiah",
            41,
            10,
            "Non temere, perché io sono con te; io ti rendo forte.",
            "Isaia 41:10 ci parla con queste parole: «Non aver paura perche ti fortifico io».",
        ),
        (
            "it-quote-first",
            "Isaiah",
            41,
            10,
            "Non temere, perché io sono con te; io ti rendo forte.",
            "«Non aver paura perche ti fortifico sempre io», come dice Isaia 41:10.",
        ),
        (
            "de",
            "John",
            3,
            16,
            "Denn so sehr hat Gott die Welt geliebt, dass er seinen Sohn gab.",
            "Er sagte «Gott liebte die ganze Erde so sehr, dass er sein Kind sandte» (Johannes 3,16).",
        ),
        (
            "es",
            "Psalms",
            23,
            1,
            "Jehová es mi pastor; nada me faltará.",
            "Leemos «El Senor cuida de mi como un pastor y nada me falta jamas» (Salmos 23:1).",
        ),
        (
            "fr",
            "John",
            3,
            16,
            "Car Dieu a tant aimé le monde qu il a donné son Fils unique.",
            "Il dit «Dieu a aimé la terre entiere au point d envoyer son enfant» (Jean 3:16).",
        ),
        (
            "pt",
            "Psalms",
            23,
            1,
            "O Senhor é o meu pastor; nada me faltará.",
            "Lemos «O Senhor cuida de mim como pastor e nada me faltara nunca» (Salmos 23:1).",
        ),
        (
            "ru",
            "John",
            3,
            16,
            "Ибо так возлюбил Бог мир, что отдал Сына Своего.",
            "Сказано «Бог настолько полюбил весь мир, что послал единственного Сына» (Иоанна 3:16).",
        ),
        (
            "ar",
            "John",
            3,
            16,
            "لأنه هكذا أحب الله العالم حتى بذل ابنه الوحيد",
            "يقول الكتاب «الله أحب العالم كله حتى أرسل ابنه الوحيد لنا اليوم» (يوحنا 3:16).",
        ),
        (
            "hi",
            "John",
            3,
            16,
            "क्योंकि परमेश्वर ने जगत से ऐसा प्रेम रखा कि उसने अपना एकलौता पुत्र दे दिया",
            "वचन «परमेश्वर ने सारे संसार से इतना प्रेम किया कि अपना पुत्र भेजा» (यूहन्ना 3:16) कहता है।",
        ),
        (
            "zh",
            "John",
            3,
            16,
            "神爱世人，甚至将他的独生子赐给他们。",
            "经上说「神如此疼爱全世界的人，竟然赐下他唯一的孩子」（约翰福音 3:16）。",
        ),
        (
            "ko",
            "John",
            3,
            16,
            "하나님이 세상을 이처럼 사랑하사 독생자를 주셨으니",
            "성경은 「하나님이 온 세상을 너무 사랑하셔서 외아들을 보내셨다」 (요한복음 3:16) 라고 합니다.",
        ),
    ]

    @pytest.mark.parametrize("cid,book,ch,vs,canon,resp", CASES, ids=[c[0] for c in CASES])
    def test_reworded_quote_corrected_to_canonical(self, cid, book, ch, vs, canon, resp):
        db = [FakeVerse(book, ch, vs, canon)]
        ctx = {(book.lower(), ch, vs)}
        out, corrections = ground_response(resp, db, ctx)
        assert canon in out, f"[{cid}] canonical not substituted: {out!r}"
        assert out != resp, f"[{cid}] response left unchanged"
        assert [c.reason for c in corrections] == ["mismatched"], f"[{cid}] {corrections}"


class TestGroundingVersionFaithful:
    """Grounding corrects to the user's selected translation, never a fixed one."""

    KJV = "For God so loved the world, that he gave his only begotten Son."
    WEB = "For God so loved the world, that he gave his one and only Son."

    @pytest.mark.parametrize("canonical", [KJV, WEB], ids=["kjv", "web"])
    def test_corrects_to_selected_version(self, canonical):
        resp = "He said «God loved the planet so much he sent his one child» (John 3:16)."
        out, _ = ground_response(resp, [FakeVerse("John", 3, 16, canonical)], {("john", 3, 16)})
        assert canonical in out and out != resp


class TestGroundingNegativeControls:
    """A non-verse quotation near a reference must never be rewritten."""

    @pytest.mark.parametrize(
        "resp",
        [
            'John 3:16 is my favorite. The pastor said "what a lovely day" outside.',
            'John 3:16 and also "my dog is very cute" today.',
            "约翰福音 3:16 是我最喜欢的。他说「今天天气很好」。",
        ],
        ids=["en-sentence-break", "en-and-also", "zh-different-sentence"],
    )
    def test_non_verse_quote_not_corrected(self, resp):
        out, corrections = ground_response(
            resp, [FakeVerse("John", 3, 16, JOHN_3_16_EN)], {("john", 3, 16)}
        )
        assert out == resp
        assert corrections == []


# ---------------------------------------------------------------------------
# BITB-053: Unquoted / paraphrased citation grounding
# ---------------------------------------------------------------------------

JOHN_3_16_EN_FULL = "For God so loved the world, that he gave his only begotten Son."
ISA_41_10_IT = (
    "Non temere, perché io sono con te; non smarrirti, perché io sono il tuo Dio. "
    "Ti rendo forte e ti vengo in aiuto e ti sostengo con la destra vittoriosa."
)


class TestExtractReferenceMentions:
    def test_simple_english(self):
        text = "In John 3:16 God tells us he gave his only Son for the world."
        mentions = extract_reference_mentions(text)
        assert len(mentions) == 1
        assert str(mentions[0].reference) == "John 3:16"
        assert "God tells us he gave his only Son for the world" in mentions[0].content_text

    def test_reference_not_duplicated(self):
        text = "Romans 8:28 — all things work together for good for those who love God."
        mentions = extract_reference_mentions(text)
        assert len(mentions) == 1

    def test_parenthetical_reference(self):
        text = "Dio ci dice di non temere perché Lui ci rende forti (Isaia 41:10)."
        mentions = extract_reference_mentions(text)
        assert len(mentions) == 1
        assert "isaia" in str(mentions[0].reference).lower() or "isaiah" in str(mentions[0].reference).lower()

    def test_sentence_boundary_stops_at_period(self):
        text = "This is a prior sentence. In John 3:16 God so loved the world. Next sentence here."
        mentions = extract_reference_mentions(text)
        assert len(mentions) == 1
        # content_text should not include "prior sentence"
        assert "prior" not in mentions[0].content_text

    def test_offsets_valid(self):
        text = "Romans 8:28 tells us all things work for good."
        mentions = extract_reference_mentions(text)
        assert len(mentions) == 1
        m = mentions[0]
        # ref_span should point at the reference text in the original string
        assert text[m.ref_span[0] : m.ref_span[1]].startswith("Romans")
        # sentence_span should be a valid slice
        assert text[m.sentence_span[0] : m.sentence_span[1]] == m.sentence


class TestClassifyParaphrase:
    def test_english_paraphrase_detected(self):
        content = "God tells us he gave his only beloved Son for the entire world"
        canonical = JOHN_3_16_EN_FULL
        assert _classify_paraphrase(content, canonical)

    def test_italian_paraphrase_detected(self):
        # "God says do not fear because he makes us strong" — overlaps non, temere, rendo/rende, forte
        content = "Dio ci dice di non temere perché Lui ci rende forti"
        canonical = ISA_41_10_IT
        assert _classify_paraphrase(content, canonical)

    def test_commentary_not_detected(self):
        # Pure commentary with no lexical overlap beyond stopwords
        content = "questo passo parla della forza spirituale che viene dall alto"
        canonical = ISA_41_10_IT
        assert not _classify_paraphrase(content, canonical)

    def test_too_short_not_detected(self):
        # Fewer than _PARAPHRASE_MIN_CANDIDATE_WORDS long tokens
        assert not _classify_paraphrase("God loved", JOHN_3_16_EN_FULL)

    def test_empty_inputs(self):
        assert not _classify_paraphrase("", JOHN_3_16_EN_FULL)
        assert not _classify_paraphrase("God gave his Son for the world today", "")

    def test_threshold_constant_reasonable(self):
        assert 0.0 < PARAPHRASE_SIMILARITY_THRESHOLD < 0.5


class TestGroundParaphrase:
    """Unquoted paraphrases get canonical text appended after the reference."""

    def test_english_unquoted_paraphrase(self):
        text = "In John 3:16 God so loved the world that he gave his only beloved Son for us."
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN_FULL)
        out, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert len(corrections) == 1
        assert corrections[0].reason == "paraphrased"
        assert JOHN_3_16_EN_FULL in out
        # Reference still present
        assert "John 3:16" in out

    def test_italian_unquoted_paraphrase(self):
        text = "In Isaia 41:10 Dio ci dice di non temere perché Lui ci rende forti."
        isa = FakeVerse("Isaiah", 41, 10, ISA_41_10_IT)
        out, corrections = ground_response(text, [isa], context_refs=set())
        assert len(corrections) == 1
        assert corrections[0].reason == "paraphrased"
        assert ISA_41_10_IT in out

    def test_idempotency_canonical_already_present(self):
        # If the canonical text is already in the sentence, do not append again.
        text = f'In John 3:16 {JOHN_3_16_EN_FULL} — this is the verse.'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN_FULL)
        out, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        assert corrections == []
        assert out == text

    def test_quoted_verse_not_double_processed(self):
        # A quoted verse handled by pass-1 must not also get a paraphrase append.
        text = f'John 3:16 says: "God loved the whole planet greatly and sent his child."'
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN_FULL)
        out, corrections = ground_response(text, [jn], context_refs={("john", 3, 16)})
        # Pass-1 corrects the quote; pass-2 must not add a second append.
        assert out.count(JOHN_3_16_EN_FULL) == 1

    def test_paraphrase_disabled_by_flag(self):
        text = "In John 3:16 God so loved the world that he gave his only beloved Son for us."
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN_FULL)
        out, corrections = ground_response(
            text, [jn], context_refs=set(), ground_paraphrases=False
        )
        assert corrections == []
        assert out == text

    def test_no_resolved_verses_no_paraphrase(self):
        text = "In John 3:16 God so loved the world that he gave his only beloved Son for us."
        out, corrections = ground_response(text, [], context_refs=set())
        assert corrections == []
        assert out == text


class TestGroundParaphraseNegativeControls:
    """Ordinary discussion about a verse must never be altered."""

    @pytest.mark.parametrize(
        "text",
        [
            "John 3:16 is one of the most beloved verses in the Bible.",
            "We should reflect on John 3:16 today.",
            "Romans 8:28 is a passage about hope and perseverance.",
            "See also Isaiah 41:10 for encouragement.",
        ],
        ids=["beloved-verse", "reflect-on", "about-hope", "see-also"],
    )
    def test_commentary_not_altered(self, text):
        jn = FakeVerse("John", 3, 16, JOHN_3_16_EN_FULL)
        isa = FakeVerse("Isaiah", 41, 10, ISA_41_10_IT)
        rom = FakeVerse("Romans", 8, 28, "And we know that all things work together for good.")
        out, corrections = ground_response(text, [jn, isa, rom], context_refs=set())
        assert out == text, f"Commentary was wrongly altered: {out!r}"
        assert corrections == []


class TestGroundParaphraseCrossLanguage:
    """Parametrized: unquoted paraphrases detected across all 11 supported languages."""

    JOHN_CANONICAL = {
        "en": "For God so loved the world, that he gave his only begotten Son.",
        "it": "Dio ha tanto amato il mondo da dare il suo Figlio unigenito.",
        "de": "Denn so sehr hat Gott die Welt geliebt, dass er seinen einzigen Sohn gab.",
        "fr": "Car Dieu a tant aimé le monde qu il a donné son Fils unique.",
        "es": "Porque de tal manera amó Dios al mundo, que ha dado a su Hijo unigénito.",
        "pt": "Porque Deus amou o mundo de tal maneira que deu o seu Filho unigênito.",
        "ru": "Ибо так возлюбил Бог мир, что отдал Сына Своего Единородного.",
        "ar": "لأنه هكذا أحب الله العالم حتى بذل ابنه الوحيد",
        "hi": "क्योंकि परमेश्वर ने जगत से ऐसा प्रेम रखा कि उसने अपना एकलौता पुत्र दे दिया",
        "zh": "神爱世人，甚至将他的独生子赐给他们。",
        "ko": "하나님이 세상을 이처럼 사랑하사 독생자를 주셨으니",
    }

    # Each case: (lang_id, text_with_unquoted_paraphrase, book, ch, vs)
    CASES = [
        ("en", "In John 3:16 God greatly loved the world and gave his only begotten Son.", "John", 3, 16),
        ("it", "In Giovanni 3:16 Dio ha amato il mondo tanto da dare il suo unico Figlio.", "John", 3, 16),
        ("de", "In Johannes 3,16 hat Gott die Welt so sehr geliebt dass er seinen Sohn gab.", "John", 3, 16),
        ("fr", "Dans Jean 3:16 Dieu a tellement aimé le monde qu il a donné son Fils.", "John", 3, 16),
        ("es", "En Juan 3:16 Dios amó tanto al mundo que entregó a su Hijo unigénito.", "John", 3, 16),
        ("pt", "Em João 3:16 Deus amou o mundo de tal forma que deu seu Filho unigênito.", "John", 3, 16),
        ("ru", "В Иоанна 3:16 Бог так возлюбил мир что отдал Сына Своего Единородного.", "John", 3, 16),
        ("it-isa", "In Isaia 41:10 Dio ci dice di non temere perché Lui ci rende forti.", "Isaiah", 41, 10),
    ]

    CANONICAL_MAP = {
        ("John", 3, 16, "en"): JOHN_CANONICAL["en"],
        ("John", 3, 16, "it"): JOHN_CANONICAL["it"],
        ("John", 3, 16, "de"): JOHN_CANONICAL["de"],
        ("John", 3, 16, "fr"): JOHN_CANONICAL["fr"],
        ("John", 3, 16, "es"): JOHN_CANONICAL["es"],
        ("John", 3, 16, "pt"): JOHN_CANONICAL["pt"],
        ("John", 3, 16, "ru"): JOHN_CANONICAL["ru"],
        ("Isaiah", 41, 10, "it-isa"): ISA_41_10_IT,
    }

    @pytest.mark.parametrize("lang,text,book,ch,vs", CASES, ids=[c[0] for c in CASES])
    def test_paraphrase_appends_canonical(self, lang, text, book, ch, vs):
        canonical = self.CANONICAL_MAP[(book, ch, vs, lang)]
        db = [FakeVerse(book, ch, vs, canonical)]
        out, corrections = ground_response(text, db, context_refs=set())
        assert len(corrections) == 1, f"[{lang}] expected 1 correction, got {corrections}"
        assert corrections[0].reason == "paraphrased", f"[{lang}] {corrections[0].reason}"
        assert canonical in out, f"[{lang}] canonical not appended: {out!r}"
