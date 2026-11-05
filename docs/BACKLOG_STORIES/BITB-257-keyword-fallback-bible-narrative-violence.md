# BITB-257: Keyword Fallback Blocks Third-Person Bible Narrative as Violence (and Shows a Crisis Card)

**Status:** 🔍 In review (2026-11-02)
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

## Implementation (2026-11-02)

- `api/utils/security.py`: ar bare `قتل` replaced by intent-only patterns (first person/future/
  imperative, intent verb + verbal noun, how-to naming the asker; `جريمة قتل` kept). en/fr/it/es/pt/de
  bare kill-verbs are skipped by `find_violence_matches` when the text before the match is a
  third-person narrative frame (`_VIOLENCE_NARRATIVE_VERBS` / `_VIOLENCE_NARRATIVE_BEFORE`): en
  do-support with a non-I/we/you subject and commandment frames; fr/it/es/pt/de past-tense
  "wanted/tried/decided to" frames that exclude first-person pronouns. Nouns (bomb/weapon/gun) are never guarded.
- Tests: the BITB-255 xfails flipped to plain passes; a parametrized 11-language first-person threat
  test goes through the real fallback (block reason + `THREAT_TO_OTHERS` card); mixed en/ar case;
  `THREATS_STILL_BLOCK` and noun-guard tests in `test_violence_keyword_fallback_languages.py`.
- BITB-194 (Latin/ar narrative false positives): the fr/de/it xfail cases now pass, so BITB-194's
  remaining false positives are fixed for the covered phrasings.

## Known limitations

- Declarative narrative ("God told Saul to kill Agag") still blocks: only question/past-tense frames are guarded.
- Narrative-framed evasions ("Why did Cain kill Abel and how can I do the same") can pass, but only
  while ML moderation is down; the ML stages remain the primary defence.
- ar `سلاح`/`هجوم` (weapon/attack) remain bare patterns (Bible-narrative senses) and are out of scope here.
