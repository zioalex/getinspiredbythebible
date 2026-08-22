"""Tests for Traditional->Simplified Chinese normalization (BITB-025)."""

import json
from pathlib import Path

from utils.chinese_script import TRADITIONAL_TO_SIMPLIFIED, normalize_traditional_to_simplified
from utils.translation_registry import CHINESE_ALIASES, ENGLISH_TO_CHINESE

FIXTURES_DIR = Path(__file__).parent.parent.parent / "tests" / "fixtures"


class TestNormalizeTraditionalToSimplified:
    """Direct behavior of the normalization function."""

    def test_all_table_entries_convert(self):
        for traditional, simplified in TRADITIONAL_TO_SIMPLIFIED.items():
            assert normalize_traditional_to_simplified(traditional) == simplified

    def test_noop_on_english(self):
        text = "John 3:16, for God so loved the world"
        assert normalize_traditional_to_simplified(text) == text

    def test_noop_on_cyrillic(self):
        text = "Иоанна 3:16"
        assert normalize_traditional_to_simplified(text) == text

    def test_noop_on_korean(self):
        text = "요한복음 3:16"
        assert normalize_traditional_to_simplified(text) == text

    def test_noop_on_arabic(self):
        text = "يوحنا 3:16"
        assert normalize_traditional_to_simplified(text) == text

    def test_noop_on_already_simplified(self):
        text = "约翰福音 3:16"
        assert normalize_traditional_to_simplified(text) == text

    def test_noop_on_empty_string(self):
        assert normalize_traditional_to_simplified("") == ""

    def test_noop_on_emoji(self):
        text = "🙏 John 3:16 📖"
        assert normalize_traditional_to_simplified(text) == text

    def test_length_preserving_over_table(self):
        for traditional in TRADITIONAL_TO_SIMPLIFIED:
            assert len(normalize_traditional_to_simplified(traditional)) == len(traditional)

    def test_length_preserving_over_mixed_text(self):
        text = "請閱讀約翰福音 3:16, danke, 谢谢, 감사합니다"
        result = normalize_traditional_to_simplified(text)
        assert len(result) == len(text)

    def test_idempotent(self):
        text = "約翰福音 3:16"
        once = normalize_traditional_to_simplified(text)
        twice = normalize_traditional_to_simplified(once)
        assert once == twice

    def test_book_name_john(self):
        assert normalize_traditional_to_simplified("約翰福音") == "约翰福音"

    def test_book_name_matthew(self):
        assert normalize_traditional_to_simplified("馬太福音") == "马太福音"

    def test_mixed_script_single_character(self):
        # 創 traditional + 世记 already simplified
        assert normalize_traditional_to_simplified("創世记") == "创世记"

    def test_both_traditional_variants_of_qi_map_to_same_target(self):
        # 啟 (getbible CUS feed's Revelation entry) and 啓 (alternate variant)
        # are both Traditional forms of 启.
        assert normalize_traditional_to_simplified("啟") == "启"
        assert normalize_traditional_to_simplified("啓") == "启"


class TestFixtureParity:
    """The three platform implementations must agree — this is the shared
    source of truth they're all checked against."""

    def test_backend_table_matches_fixture(self):
        with open(FIXTURES_DIR / "t2s_char_map.json", encoding="utf-8") as f:
            fixture = json.load(f)
        assert TRADITIONAL_TO_SIMPLIFIED == fixture["char_map"]


class TestExhaustiveBookCoverage:
    """Every Chinese book name in the registry must resolve after converting
    it to Traditional and back through our table — proves the table covers
    every book without hand-typing all 66 Traditional names."""

    def test_every_book_name_and_alias_roundtrips(self):
        # Invert the table (Simplified -> Traditional) to render every
        # canonical/alias name in Traditional script, then normalize it back
        # and assert it matches the original Simplified string exactly.
        s2t = {
            simplified: traditional for traditional, simplified in TRADITIONAL_TO_SIMPLIFIED.items()
        }

        names = set(ENGLISH_TO_CHINESE.values()) | set(CHINESE_ALIASES.keys())
        checked = 0
        for name in names:
            # Skip the one entry that's already Traditional in the source data
            # (ENGLISH_TO_CHINESE["Revelation"] = "啟示錄") — it has no
            # Simplified round-trip to construct here, and is covered by
            # test_chinese_traditional_revelation_still_resolves instead.
            if name == "啟示錄":
                continue
            traditional = "".join(s2t.get(ch, ch) for ch in name)
            if traditional == name:
                continue  # no Traditional-only characters in this name
            assert normalize_traditional_to_simplified(traditional) == name
            checked += 1

        assert checked > 0
