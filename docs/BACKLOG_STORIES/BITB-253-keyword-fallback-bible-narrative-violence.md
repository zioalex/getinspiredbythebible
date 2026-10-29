# BITB-253: Keyword Fallback Blocks Third-Person Bible Narrative as Violence (and Shows a Crisis Card)

**Status:** 🎯 Todo
**Priority:** P1
**Size:** M
**Created:** 2026-10-29
**Prompted by:** BITB-251 verification (2026-10-29)

## Problem (verified in code)

When the ML safety stages (Llama Guard, OpenAI moderation, Azure) are unavailable,
`ContentSafetyService._full_keyword_fallback` (`api/utils/content_safety.py`) blocks third-person
Bible narrative questions as violence:

- en: "Why did Cain kill Abel in the book of Genesis?" → `keyword_violation:violence (fallback)`
- ar: "لماذا قتل قايين هابيل في سفر التكوين؟" → same

The block existed before BITB-251. Since BITB-251, the blocked outcome is also classified as
`threat_to_others`, so the user gets an emergency-services crisis card on a Bible-study question.
BITB-251 records this with `xfail(strict=True)` cases, en and ar, in its real-fallback narrative test.

## Acceptance criteria

- [ ] Third-person, past-tense Bible narrative ("Why did X kill Y", "David killed Goliath") is not
      blocked in the keyword fallback, in all 11 languages
- [ ] First-person or present threats ("I will kill him") are still blocked and still get the card
- [ ] The BITB-251 xfail cases flip to passing; `strict=True` removed
- [ ] No regression in the BITB-185/186/196/200–204 self-harm and murder-suicide suites

## Notes

This overlaps the guard work in BITB-200–204, so reuse their Bible-study guard approach rather than
adding a parallel mechanism.
