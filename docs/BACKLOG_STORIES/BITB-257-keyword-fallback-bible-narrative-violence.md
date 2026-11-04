# BITB-257: Keyword Fallback Blocks Third-Person Bible Narrative as Violence (and Shows a Crisis Card)

**Status:** 🔍 In review (2026-11-04)
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

## Decision (2026-11-04): option A — fail safe

The first guard (2026-11-02) opened recall holes that blocked on main: ar `هقتلك`, `سأقوم بقتل جاري`,
`أفكر في قتل أبي`, `طريقة قتل شخص`, `قتلت زوجتي`; en "How does a man kill his wife without getting
caught"; fr "Il a décidé de tuer sa femme ce soir"; and narrative used as cover before a first-person
threat ("Pourquoi Caïn a-t-il voulu tuer Abel ? Je veux tuer mon voisin"). The owner chose to fail safe:
**when unsure, block.** A narrative exemption applies ONLY when a known Bible anchor is present and
there is no first-person marker anywhere in the message. The fallback only runs while ML moderation is
down, so extra blocks are the cheaper error (see BITB-267 to make the fallback rare).

## Acceptance criteria

- [x] Third-person Bible narrative is not blocked in the keyword fallback ONLY when a Bible anchor
      (person/people/book name; en, it, de, es, fr, pt, ar) is present AND there is no first-person
      marker anywhere in the message. Unanchored ("Why did he kill her?") or first-person-bearing
      text blocks (fail safe). ru/zh/hi/ko narrative handling is unchanged (BITB-198)
- [x] Recall regressions blocked on main block again (ar قتلت/هقتلك/بقتل/أقتل forms, en/fr unanchored,
      narrative-as-cover followed by first-person intent), with the threat-to-others card
- [x] First-person or present threats ("I will kill him") are still blocked and still get the card
- [x] The BITB-255 xfail cases flip to passing; `strict=True` removed
- [x] No regression in the BITB-185/186/196/200–204 self-harm and murder-suicide suites

## Notes

This overlaps the guard work in BITB-200–204, so reuse their Bible-study guard approach rather than
adding a parallel mechanism.

## Implementation (2026-11-04, option A)

- `api/utils/security.py`: `_BIBLE_NARRATIVE_ANCHORS` (en/it/de/es/fr/pt/ar) = curated Bible person/people
  names + that language's book names/aliases DERIVED from `translation_registry` (normalized with
  `normalize_text`, accent-stripped variants, generic book words such as "Numbers"/"Acts" and generic
  names for God excluded). `MultiLanguageContentFilter._is_narrative_exempt` skips a match only if
  the guarded verb sits in a `_VIOLENCE_NARRATIVE_BEFORE` frame, an anchor matches anywhere, and the
  language's first-person veto (`_VIOLENCE_NARRATIVE_VETO`, now whole-message for every language) does not.
- Arabic: bare `قتل` restored in `VIOLENCE_PATTERNS["ar"]` (plus `جريمة قتل`); exempt only when the match is
  the standalone word `قتل` (optional و/ف prefix), an ar anchor is present and no ar first-person/intent
  marker appears. `قتلت`, `هقتلك`, `بقتل`, `لقتل`, `أقتل`, `يقتل`, `القتل` always block.
  `_UNIQUE_SCRIPT_VIOLENCE_LANGS` still correctly excludes `ar`.
- Tests: `REGRESSIONS_MUST_BLOCK` / `FAIL_SAFE_BLOCKS` (find_violence_matches + real `_full_keyword_fallback`),
  anchor-derivation test, added anchored narrative cases, and real-fallback + `THREAT_TO_OTHERS` card tests
  in `test_chat_crisis_path.py`. Cases converted from "narrative passes" to "fail-safe blocks":
  "Thou shalt not kill - what does it mean?", ar "ماذا تعني وصية لا تقتل؟", ar "لماذا أراد شاول أن يقتل داود؟".

## Known limitations

- No anchor, no exemption: "Why did he kill him?", "Thou shalt not kill - what does it mean?" and
  commandment questions block while ML moderation is down.
- Arabic exemption is for the standalone word `قتل` only; `يقتل`/`القتل`/`قتله` narrative blocks.
- Declarative narrative ("God told Saul to kill Agag") still blocks: only question/past-tense frames are guarded.
- Narrative followed by a second-person threat ("you should kill your boss") has no first-person
  marker and can pass when an anchor is present; ML moderation remains the primary defence.
- Common modern first names that are also Bible names (John, Paul, Peter, James) are anchors.
- ar `سلاح`/`هجوم` (weapon/attack) remain bare patterns (Bible-narrative senses) and are out of scope here.

## Follow-ups

- BITB-267 — ML content-safety reliability (cross-provider failover, fallback-share SLO) so this
  fail-safe keyword fallback runs rarely
  (`docs/BACKLOG_STORIES/BITB-267-ml-safety-reliability-rare-keyword-fallback.md`).
