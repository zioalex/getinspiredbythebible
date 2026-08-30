# BITB-103: The Golden Set Cannot Validate Topic Boosting

**Status:** ✅ Done
**Priority:** P1 — blocks BITB-044's three remaining acceptance criteria; without it, "did topic
boosting help?" is not a question the harness can answer
**Size:** M (golden-set authoring, not code)
**Created:** 2026-08-21
**Prompted by:** PR #970 (BITB-044), whose remaining ACs all say "validate against the BITB-043
golden set" — the golden set cannot currently carry that weight

## User Story

**As** the maintainer about to decide whether to enable `topic_boosting_enabled` in production,
**I want** a golden set that actually exercises all 13 topics and includes a neutral control group,
**so that** "topic-laden queries improve, neutral queries do not regress" is a measurement rather
than a hope.

## Why This Exists

BITB-044 (PR #970) makes topic boosting *possible* to validate by finally populating `verse_topics`.
Its three open acceptance criteria then hand the question to the golden set:

> - [ ] With `topic_boosting_enabled=True`, topic-laden golden queries improve (or hold) Precision@5/MRR; neutral queries do not regress.
> - [ ] `topic_boost_factor` chosen against the golden set and documented.
> - [ ] Topic boosting enabled in prod.

The golden set cannot answer any of them today. Measured against
`api/search_eval/data/retrieval_golden_set.json` (58 cases) and the 13 canonical topics in
`api/chat/topics.py`:

### 1. Three canonical topics have zero cases

`joy`, `patience` and `trust` appear nowhere as a golden-set category. Whatever boosting does for
those topics is unmeasurable, in either direction.

### 2. Two golden-set categories are not topics at all

| category | cases | canonical topic? |
|---|---|---|
| `strength` | 7 | **no** |
| `provision` | 1 | **no** |

Eight cases — 14% of the set — are labelled with vocabulary that `detect_topics()` will never
produce, so they cannot exercise the boost path regardless of what the boost does.

### 3. Four topics are represented by a single case

`grief`, `hope`, `guidance` (and `provision`) have exactly one case each. A one-case topic cannot
show a Precision@5 or MRR delta that means anything — one ranking change moves the metric from 0.0
to 1.0 and reads as a dramatic result.

Full distribution: loneliness 11, forgiveness 9, love 7, strength 7, anxiety 6, fear 6, anger 5,
peace 3, grief 1, hope 1, guidance 1, provision 1.

### 4. There is no neutral control group

Every one of the 58 cases carries a topic-ish `category`. The AC's second half — "neutral queries do
not regress" — has no population to measure against. A boost that quietly degrades non-thematic
lookups (a plain reference lookup, a factual question) would pass this suite unnoticed, which is
precisely the regression most worth catching before flipping the flag in production.

### 5. The languages do not line up with what the tagger supports

| group | languages | cases | can topic boosting apply? |
|---|---|---|---|
| corpus-validated | en, de | 13 | yes |
| tagged, denylist unvalidated | it, es, fr, pt, ar | 25 | yes, on unverified tagging (BITB-106) |
| unsupported by the tagger | ru, zh, hi, ko | 20 | **no** |

Only **13 of 58 cases (22%)** sit in languages where tagging is both supported *and* validated
against a real corpus. 20 cases (34%) are in languages `scripts/populate_verse_topics.py` skips
outright, so they will show a flat zero-delta that must not be misread as "boosting doesn't help".

### 6. Nothing links a case to a topic

Cases carry `category` and `tags` (free text). Neither is constrained to the canonical topic
vocabulary, and nothing checks that they stay aligned as either side changes. The overlap that does
exist today is coincidental, not enforced.

## Proposed Fix

1. **Add an explicit `topics` field** to the golden-set case schema, holding zero or more *canonical*
   topic ids. Keep `category`/`tags` as the human-facing labels they already are; `topics` becomes
   the machine-checked link. An empty `topics` list is the explicit marker for a neutral case.
2. **Fill the three empty topics** (`joy`, `patience`, `trust`) and **raise the single-case topics**
   (`grief`, `hope`, `guidance`) to at least 3 cases each.
3. **Reconcile `strength` and `provision`** — either map those 8 cases onto canonical topics, or add
   the two as canonical topics in `api/chat/topics.py` (with keyword vocabulary, which then also
   needs corpus validation per BITB-106). Deciding is part of this story; the current state, where
   they are neither, is the only outcome to rule out.
4. **Add a neutral control subset** — reference lookups, factual questions, and thematically flat
   queries, labelled `topics: []` — large enough to detect a regression. These are what make the
   "does not regress" half of BITB-044's AC real.
5. **Add a CI assertion** alongside the existing `--validate` job: every canonical topic has ≥3
   cases, every value in a case's `topics` is a canonical topic id, and the neutral subset is
   non-empty. The failure mode here is silent drift between two files nobody diffs together, and a
   test is what keeps it loud.

## Decisions

**Derivation rule for the existing 58 cases' `topics` field:** for each case, take the union of
{its `category`, if it's a canonical topic name} ∪ {any of its `tags` that are canonical topic
names}. This is mechanical and reviewable — see the exact per-case output baked into
`api/search_eval/data/retrieval_golden_set.json`.

**`strength` → `["patience"]`.** All 7 `category: "strength"` cases carry the tag `perseverance`,
which is a literal `patience` keyword in every one of its 6 Latin-script languages
(`TOPIC_KEYWORDS_BY_LANGUAGE["patience"]`), and every one of them cites `Isaiah 40:31` ("they that
**wait** upon the LORD shall renew their strength"). Considered and rejected: promoting `strength`
to a new canonical topic — `TOPIC_KEYWORDS_BY_LANGUAGE` also drives production tagging
(`scripts/populate_verse_topics.py`), so a new canonical topic means authoring keyword vocabulary
in 7 languages and a corpus-validation pass (BITB-106), which is a different, larger story.

**`provision` (en-003) → `["anxiety", "trust"]`, not `trust` alone.** The query ("I'm worried about
money and finances") is one `detect_topics()` actually classifies as `anxiety` (via "worried");
labelling it `trust` only would make the one thing the tagger agrees on invisible. `trust` stays
because the real theme — trusting God for provision — is genuine even though this exact phrasing
doesn't trigger it.

**Label coverage vs. boost-exercising ("taggable") coverage are different metrics, and both are
enforced.** Deriving `topics` from `category`/`tags` satisfies "every topic has ≥3 cases" on paper,
but leaves `trust` (16 labelled cases, almost all via the `trust` tag on anxiety/fear queries) and
`patience` (12 labelled, mostly via the `strength` mapping) at **zero** cases the keyword tagger
actually detects from the query text alone — exactly as unmeasurable as `joy` was at zero cases.
16 new cases (`en-009`..`en-019`, `de-006`..`de-010`) were authored specifically so every canonical
topic clears **both** a ≥3 labelled-case bar and a ≥2 real-detection ("taggable") bar — see
`api/search_eval/loader.py`'s `topic_coverage()` / `topic_tagger_coverage()` and
`docs/SEARCH_EVAL_HOWTO.md`'s "Golden-set schema and the `topics` field" section.

**Neutral control subset:** 10 cases (`en-020`..`en-027`, `de-011`, `de-012`), all confirmed to
return `[]` from `detect_topics()`, against a CI floor of 6 (so removing one case doesn't instantly
redden the pipeline).

**New-case language policy:** English (19 new cases) and German (7 new cases) only — the two
tagger-supported languages the story's own audit calls "corpus-validated" (as opposed to
`it/es/fr/pt/ar`, tagged but pending BITB-106's corpus validation, or `ru/zh/hi/ko`, which the
tagger skips outright). Every new German case reuses vocabulary verbatim from
`TOPIC_KEYWORDS_BY_LANGUAGE`, substituted into the sentence frame of an existing, already-reviewed
German case, to keep translation risk near zero.

**Verification method:** every proposed query was run through a byte-for-byte reimplementation of
`detect_topics()`'s flatten+substring logic (there is no shortcut around actually running it — the
existing 58 cases hid two silent substring artifacts, "fe" ["faith", ES] matching inside English
"feel"/"suffering" and "futur" ["future", FR] matching inside English/Italian/Portuguese "future"/
"futuro", that a plain read of the query text would not catch). Every proposed Bible reference was
checked against `data/bible/kjv.json`.

## Acceptance Criteria

- [x] Golden-set cases carry a `topics` field validated against the canonical vocabulary in
      `api/chat/topics.py`
- [x] All 13 canonical topics have ≥3 cases; `joy`, `patience`, `trust` no longer at zero
- [x] `strength` and `provision` are either mapped to canonical topics or promoted to canonical
      topics, with the decision recorded
- [x] A labelled neutral subset (`topics: []`) exists and is large enough to detect a regression
- [x] `--validate` fails if any canonical topic falls below the case threshold, if a case names a
      non-canonical topic, or if the neutral subset is empty
- [x] The per-language caveat is documented in the report output, so a flat delta on ru/zh/hi/ko
      reads as "not taggable" rather than "boosting doesn't work"

## Verification

The coverage assertions are structural and belong in `--validate`, which already runs per-PR with no
database — that is where they will actually be enforced.

What `--validate` cannot check is whether the *added* cases are good: whether the `relevant_refs` for
a new `patience` query are genuinely the passages a person would want. That needs the same
hand-authoring care the original 58 got, and is the real cost of this story.

## Related

- **BITB-044 / PR #970** — populates `verse_topics`; its three open ACs depend on this story
- **BITB-104** — un-stubs the `topic_boosted` eval config and consumes this data
- **BITB-106** — corpus-tagging validation for the languages this story's cases span
- **BITB-051** — the harness and golden set this extends
- `api/search_eval/data/retrieval_golden_set.json`, `api/chat/topics.py`
