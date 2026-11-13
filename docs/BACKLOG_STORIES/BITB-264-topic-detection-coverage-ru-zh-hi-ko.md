---
id: BITB-264
status: todo
priority: P2
size: M
rank: 230
created: 2026-11-03
---

# BITB-264: Topic Detection Coverage for ru, zh, hi and ko

**Found by:** BITB-256 verification

## Problem (verified in code, 2026-11-03)

`api/chat/topics.py` `detect_topics()` is a keyword scan over `TOPIC_KEYWORDS_BY_LANGUAGE`,
which only has keyword lists for `SUPPORTED_TOPIC_LANGUAGES = (en, it, de, es, fr, pt, ar)`.
For Russian, Chinese, Hindi and Korean it returns `[]` (unless an English substring happens to
match). Consequences:

- Topic boosting (`topic_boosting_enabled`) never applies for those four languages.
- BITB-256 retrieval-miss rows for ru/zh/hi/ko always have `topics = []`, so the
  topic x language x reason report lumps every miss under `(none)`.
- BITB-256 `expansion_terms` is also empty for ru/zh/hi/ko, nearly empty for ar (the vocabulary
  lacks article/inflected forms such as `القلق`) and keeps only ~30-50% of terms for Latin scripts,
  because the privacy sanitizer is allow-list only. Widening the vocabulary widens that signal too.
- The search-eval report already footnotes these languages as "untaggable" (BITB-103/106).

BITB-259 is an intent-routing spike, not a coverage story, and does not close this gap.

## Requirements

1. Add keyword lists (or an alternative language-agnostic mechanism such as embedding-based
   tagging) so that all 13 canonical topics are detected in ru, zh, hi and ko.
2. Handle unspaced scripts (zh, ko particles) with substring matching that avoids false positives.
3. Parametrized detection tests for all 11 languages; update `SUPPORTED_TOPIC_LANGUAGES`
   consumers (search-eval footnote, `populate_verse_topics.py`).
4. Re-verify BITB-256 aggregate output shows non-`(none)` topics for these languages.

## Acceptance criteria

- [ ] `detect_topics` returns the expected canonical topics for a native sentence per topic in ru/zh/hi/ko.
- [ ] No regression in the existing seven languages; false-positive tests for common words.
- [ ] Search-eval untaggable footnote and BITB-256 HOW-TO limitation note updated.
