# BITB-257: Keyword Fallback Blocks Third-Person Bible Narrative as Violence (and Shows a Crisis Card)

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** M
**Created:** 2026-10-29
**Prompted by:** BITB-255 verification (2026-10-29)

## Problem (verified in code)

When the ML safety stages (Llama Guard, OpenAI moderation, Azure) are unavailable,
`ContentSafetyService._full_keyword_fallback` (`api/utils/content_safety.py`) blocks third-person
Bible narrative questions as violence:

- en: "Why did Cain kill Abel in the book of Genesis?" → `keyword_violation:violence (fallback)`
- ar: "لماذا قتل قايين هابيل في سفر التكوين؟" → same

The block existed before BITB-255. Since BITB-255, the blocked outcome is also classified as
`threat_to_others`, so the user gets an emergency-services crisis card on a Bible-study question.
BITB-255 records this with `xfail(strict=True)` cases, en and ar, in its real-fallback narrative test.

## Acceptance criteria

- [x] Third-person, past-tense Bible narrative ("Why did X kill Y", "David killed Goliath") is not
      blocked in the keyword fallback, in all 11 languages
- [x] First-person or present threats ("I will kill him") are still blocked and still get the card
- [x] The BITB-255 xfail cases flip to passing; `strict=True` removed
- [x] No regression in the BITB-185/186/196/200–204 self-harm and murder-suicide suites

## Notes

This overlaps the guard work in BITB-200–204, so reuse their Bible-study guard approach rather than
adding a parallel mechanism.

## Approach

`MultiLanguageContentFilter.find_violence_matches` (`api/utils/security.py`) now skips a match
when `_is_narrative_violence` says it sits inside a third-person past/modal narrative frame:

- `NARRATIVE_FRAME_PATTERNS` (en/it/de/es/fr/pt/ar; no de `sollte`, no pt `ia/iam`, en `did` frame
  without the `didn't` variant) cover kill/attack verbs only ("did X kill",
  "voleva uccidere", "wollte ... töten", bare Arabic past "قتل", "أن يقتل", ...). Never
  bomb/gun/weapon/terror.
- The clause around the match (cut at `. ! ? ; \n ؟ 。 ！ ？`) must contain a frame from any
  language that fully covers the match, and ONE shared veto (the union of every language's
  `NARRATIVE_VETO_PATTERNS`: first-person, object pronouns, indefinites, intent, future-time words,
  Arabic obligation/intent and first-person ي-suffix words) must not match anywhere in the clause.
- Arabic bare past "قتل" is additionally exempt only in a question ("لماذا/كيف/متى/من/هل/ما" at
  clause start) or next to a known Bible name (`NARRATIVE_REQUIRE_PATTERNS`).
- ru/zh/hi/ko needed no change (BITB-198 tables already ignore third-person narrative).
- `content_safety.py` logic is unchanged (docstring/comment only); ar stays out of
  `_UNIQUE_SCRIPT_VIOLENCE_LANGS`.

Tests: `test_violence_keyword_fallback_languages.py` (NARRATIVE_FRAMED, FRAMED_FIRST_PERSON_BLOCKS,
ambiguity guard) and `test_chat_crisis_path.py` (xfails removed; THREAT_PHRASES keep the threat card).

## Known limitations

- Arabic first-person past "قتلت" / "قتلنا" and colloquial phrasing are not exempted (stay blocked).
- Present-tense third person ("Why does God kill ...") stays blocked.
- Arabic with harakat (diacritics) is not covered by the frame patterns.
- A first-person marker anywhere in the same clause still blocks, even with a narrative frame
  ("Why did I think David wanted to kill Goliath?").
- Future-time third-party attack reports ("They planned to attack the school tomorrow",
  "Il voulait tuer le président demain") are blocked by design (future-time veto), at the cost of
  rare narrative questions containing words like "now" / "today" / "next".
- Third-party incitement/obligation ("Man sollte ... töten", "يجب قتل ...") stays blocked.
