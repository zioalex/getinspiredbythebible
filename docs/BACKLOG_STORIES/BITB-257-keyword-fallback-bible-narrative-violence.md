# BITB-257: Keyword Fallback Blocks Third-Person Bible Narrative as Violence (and Shows a Crisis Card)

**Status:** 🔍 In review (2026-11-08)
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

- [x] Third-person Bible narrative is not blocked in the keyword fallback ONLY when the WHOLE message
      (<= 200 chars, one sentence) fully matches a closed frame with a named Bible subject (en, it,
      de, es, fr, pt, ar). Anything else, narrative phrasings outside the frames included, blocks
      exactly as on main (fail safe). ru/zh/hi/ko narrative handling is unchanged (BITB-198)
- [x] Recall regressions blocked on main block again (ar قتلت/هقتلك/بقتل/أقتل forms, en/fr unanchored,
      narrative-as-cover followed by first-person intent), with the threat-to-others card
- [x] First-person or present threats ("I will kill him") are still blocked and still get the card
- [x] The BITB-255 xfail cases flip to passing; `strict=True` removed
- [x] No regression in the BITB-185/186/196/200–204 self-harm and murder-suicide suites

## Notes

This overlaps the guard work in BITB-200–204, so reuse their Bible-study guard approach rather than
adding a parallel mechanism.

## Round 3: strict whole-message allowlist (owner decision 2026-11-08)

Rounds 1-2 exempted a match when a frame, an anchor and the absence of first-person/time words
held (a per-match denylist veto, then an in-frame anchor, a time/intent veto and a cross-language
rescan). Independent verification of round 2 found **73 threat regressions against main**
(unicode tricks, first person in another language, Romance verbs without pronouns, time synonyms,
Arabic dialect, real-world violence by people named after Bible figures, padded long messages):
a denylist can never be complete. Round 3 replaces all of it with a closed allowlist, mirroring
BITB-238's directed-harm exemption (`_dh_whole_message_exempt`, PR #1249). The two helpers
(`_violence_narrative_whole_message_exempt` here) can be unified once both PRs merge; names are
distinct (`_VN_*`) so they merge cleanly.

**Rule** (`api/utils/security.py`, `_violence_narrative_whole_message_exempt(lang, normalized)`).
A violence-table match is skipped only if this returns True. It is computed once per message and
only when the table matched (linear cost; 50k chars stay well under 200 ms):

1. Length: the whitespace-collapsed message is <= 200 chars and has no newline.
2. Normalization for the check: Arabic harakat/tatweel and Latin accents stripped; a word mixing
   Latin with Cyrillic/Greek (homoglyph) fails.
3. First-person veto: the union of every language's first-person words (a belt-and-braces check,
   the frames have no pronoun slot).
4. Single sentence: optional wrappers `( [ « " "` and one terminal `?`/`.`/`؟`.
5. The body must `fullmatch` one closed frame of the language. Subject/object are
   named Bible people (curated list); at least one must be DISTINCTIVE (Cain, Abel, Goliath, Saul,
   Herod, Pharaoh ...): common modern first names (`_BIBLE_COMMON_NAMES`: John, David, Moses, Jesus,
   Elijah, Titus ...) only qualify next to a distinctive anchor, never two common names together.
   Egyptians and God/Dieu/Gott/Dio/Dios/Deus/الله are not anchors. Book names are derived from
   `translation_registry` and only appear in the book slot (`in <book> [chapter[:verse]]`, and
   the `In <book>,` prefix in English); digits arrive letter-mapped by `normalize_text`
   ("17" -> "it") so the number slot accepts those letters.

**Closed frames**
- en: (why|how|when) did <A> [want|try|decide|plan to] (kill|murder|slay|slaughter|stab|shoot)
  [<A> | his brother | him | them | the prophets/priests/firstborn/babies/children/philistines/
  egyptians/amalekites] [in [the book of] <book>]; `did <A> kill|murder <A>`;
  `why didn't <A> kill <A>`; commandment ("thou shalt not / you shall not kill|murder", optional
  lead "what does ... / why does the bible say ..." and " mean" / "- what does it mean").
- it/de/es/fr/pt: question word + subject + wanted/tried/decided-to + infinitive (+ object, book), or
  the simple/compound past (it uccise, es mató, fr a-t-il tué, de hat ... getötet, pt matou),
  also VSO for it/es/pt. Inflected past forms are accepted only inside the frame.
- ar: (لماذا|كيف|متى|هل)? قتل <A> <A>? [في سفر <book>]; <A> قتل <A>; (لماذا|كيف) أراد <A> أن يقتل <A>;
  commandment (ماذا تعني|ما معنى) [وصية] لا تقتل.
- ru/zh/hi/ko: never exempt (unchanged vs main).

**Trade-off (fail safe, by design).** Every narrative phrasing outside the closed frames blocks
exactly as on main, e.g. "How did David kill Goliath with a sling in 1 Samuel 17?", "Why did Cain
kill Abel and what does it teach us?", "Why did David kill him?", "Why did Moses kill the
Egyptian?", "Why did Phinehas kill Zimri?" (not in the name list). Add frames or names when
the owner wants more recall; widening always means adding to the allowlist, never to a veto.

**Tests** (`test_violence_keyword_fallback_languages.py`, `test_chat_crisis_path.py`):
`REGRESSIONS_MUST_BLOCK`, `ANCHOR_BYPASS_MUST_BLOCK` and the 110-row `ALLOWLIST_BYPASS_MUST_BLOCK`
(every round-2 verifier threat/real-world row) via `find_violence_matches` and the real fallback,
plus the threat-card subset; fail-safe-blocks cases; allowed narrative in every language;
5,000/50,000-char timing tests (< 200 ms) for `_full_keyword_fallback` and `_has_crisis_wording`.

## Known limitations

- Pre-existing on main, unchanged: English `killed` is not a violence pattern ("I wonder why Cain
  killed Abel" passes); Arabic with diacritics (`قَتَلَ`) is not matched by the table; ru "Я убью
  своего соседа" is not caught.
- "Why did God kill Uzzah?" blocks (God is not an anchor); likewise any narrative question outside
  the frames (see the trade-off above).
- Arabic: `يقتل`/`القتل`/`قتله` narrative outside the Arabic frames blocks.
- ar `سلاح`/`هجوم` (weapon/attack) remain bare patterns (Bible-narrative senses) and are out of scope.

## Follow-ups

- BITB-267 — ML content-safety reliability (cross-provider failover, fallback-share SLO) so this
  fail-safe keyword fallback runs rarely
  (`docs/BACKLOG_STORIES/BITB-267-ml-safety-reliability-rare-keyword-fallback.md`).
