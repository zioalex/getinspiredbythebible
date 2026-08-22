"""
Traditional-to-Simplified Chinese character normalization (BITB-025).

A single-character lookup table, applied before verse-reference matching so
that a book name written in Traditional characters (e.g. ``約翰福音``, as an
LLM might produce for John) resolves the same way as the Simplified form
already used throughout ``translation_registry.py`` (``约翰福音``).

Deliberately NOT a general-purpose Traditional->Simplified converter (no
opencc / ICU Transliterator / chinese-conv): those do phrase-level
conversion and are not guaranteed length-preserving, which would break every
caller in ``verse_parser.py`` that returns offsets into the original text
(``extract_reference_mentions``, ``_find_adjacent_reference``). This table is
a strict 1:1 character substitution, so ``len(normalize_traditional_to_simplified(s))
== len(s)`` always holds and offsets stay valid.

The table covers exactly the characters that appear across the 66 CUV book
names and their Catholic (思高本) aliases in ``translation_registry.py`` once
those names are rendered in Traditional script — derived by converting every
current entry with an authoritative Simplified->Traditional converter
(dev-time only, not a runtime dependency) and collecting the resulting
character-level diffs. See ``tests/fixtures/t2s_char_map.json``, which is the
cross-platform source of truth this table (and its frontend/Android
counterparts) must match.
"""

# Traditional character -> Simplified character. Two Traditional variants of
# the same character can map to one Simplified target (e.g. both 啟 and 啓 are
# Traditional forms of 启 — the getbible CUS feed's Revelation entry uses 啟,
# while some OCR/typed sources use the 啓 variant).
TRADITIONAL_TO_SIMPLIFIED: dict[str, str] = {
    "亞": "亚",
    "來": "来",
    "傳": "传",
    "創": "创",
    "啓": "启",
    "啟": "启",
    "師": "师",
    "彌": "弥",
    "後": "后",
    "數": "数",
    "書": "书",
    "歷": "历",
    "爾": "尔",
    "猶": "犹",
    "瑪": "玛",
    "竇": "窦",
    "紀": "纪",
    "約": "约",
    "結": "结",
    "羅": "罗",
    "記": "记",
    "詩": "诗",
    "該": "该",
    "賽": "赛",
    "達": "达",
    "錄": "录",
    "門": "门",
    "馬": "马",
    "鴻": "鸿",
}

_T2S_TABLE = str.maketrans(TRADITIONAL_TO_SIMPLIFIED)


def normalize_traditional_to_simplified(text: str) -> str:
    """Convert Traditional Chinese characters to Simplified, char-by-char.

    Length-preserving by construction (one-to-one substitution, no
    expansion/contraction), so callers that track offsets into the original
    string may translate a copy for matching and still slice the original
    for display. A no-op for any text with no table characters — safe to
    call unconditionally on non-Chinese text.
    """
    return text.translate(_T2S_TABLE)
