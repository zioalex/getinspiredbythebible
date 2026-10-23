# BITB-211: Read Aloud Reads the Hidden Verse List at the End of an Answer (Web + Android)

**Status:** ✅ Done — PR #1190, merged 2026-10-22
**Priority:** P1
**Size:** S
**Created:** 2026-10-22
**Prompted by:** product-owner feedback 2026-10-22 — "The reading should exclude the verse list at the end
of the message in both platforms."

Follow-up to BITB-119 / BITB-205.

## Bug and root cause

The system prompt (`api/chat/prompts.py`) has every answer end with a hidden citation marker,
`<!-- VERSES: Matthew 6:34; Philippians 4:6-7 -->`, using English book names. It stays in the message
content (`api/golden_set/follow_up_evaluators.py`: "the VERSES comment legitimately stays"), and the screen
never shows it. Neither speakable-text normalizer (`frontend/src/lib/speakableText.ts`,
`android/.../tts/SpeakableText.kt`) stripped HTML comments. Every reading therefore ended with the verse list,
e.g. "Matthew capitolo 6, versetto 34; Philippians capitolo 4, versetti da 6 a 7" in the middle of an
Italian answer.

## Fix

A new rule in both normalizers, specified once in `tests/fixtures/speakable_text.json`: drop every HTML
comment (`<!--…-->`, multi-line, or unterminated to the end of the text) before any other normalization.

## Acceptance criteria

- [x] Fixture cases `verses_comment_{en,it,de,es,fr,pt,ar,ru,zh,hi,ko}` plus inline, multi-line and
      unterminated comment cases; the web cross-platform test fails without the rule and passes with it
- [x] Android `SpeakableTextParityTest` green in CI on the same fixture
- [ ] Owner check: a reading on web and Android ends with the answer's last sentence

## Out of scope

- A visible "Verses cited:" list the model might write in prose (the prompt asks for flowing prose and
  the hidden marker; none observed). Revisit if one shows up.

## Follow-ups

- BITB-216 — watch for a visible "Verses cited" list being read aloud
