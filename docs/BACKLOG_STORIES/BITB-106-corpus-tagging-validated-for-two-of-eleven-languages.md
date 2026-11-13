# BITB-106: Corpus Tagging Is Validated for Two Languages and Impossible for Four

**Status:** ✅ Done (2026-09-18)
**Priority:** P2 — a quality and scope-honesty gap, not a correctness bug; topic boosting works where
it is validated and silently does nothing where it is not
**Size:** M (corpus runs and vocabulary work; the ru/zh/hi/ko decision is the maintainer's)
**Created:** 2026-08-21
**Prompted by:** PR #970 (BITB-044), which validated its tagging against real corpora for `en` and
`de` only

## What Shipped (2026-09-18)

All five previously-unvalidated languages (`it`, `es`, `fr`, `pt`, `ar`) were run against real
corpora, and Arabic's substring-matching over-firing was found and denylisted. The `ru`/`zh`/`hi`/
`ko` question was decided as scope, not left open, with a technical rationale rather than a shrug
— see "The ru/zh/hi/ko decision" below. **This decision is the maintainer's to override**; it is
recorded, not final, and easy to revisit if the reasoning doesn't hold up.

### Validation results (measured against real corpora, not estimated)

Via `scripts/measure_topic_coverage.py` (new — see "Why not the DB-backed dry run" below for why
this substitutes for `populate_verse_topics.py --dry-run --verbose` here). Calibration: `en`
against the committed KJV reproduces this story's own original `en`/`de` numbers exactly
(`guidance` 3.23% / `anger` 1.56%), which is the proof this tool's output is admissible in place of
a DB-backed run.

| lang | corpus scanned | verses | tagged | highest topic |
|---|---|---|---|---|
| en | KJV (in-repo, exact production edition) | 31,100 | 18.3% | guidance 3.23% |
| de | Luther 1912 (in-repo, exact production edition) | 31,102 | 12.3% | love 1.89% |
| it | Riveduta (OSIS) — stand-in for production's `ita1927` | 31,102 | 10.2% | anger 1.26% |
| es | Reina-Valera — matches production's `valera` exactly | 31,102 | 12.2% | guidance 3.27% |
| fr | fr_apee — stand-in for production's `ls1910` | 30,975 | 14.9% | guidance 2.62% |
| pt | Almeida Atualizada — matches production's `almeida` | 31,104 | 11.3% | guidance 3.33% |
| ar | Smith & Van Dyke — matches production's `arabicsv` | 31,102 | 7.7%\* | love 0.72%\* |

\* After denylisting; 12.0% / love 3.78% before. No topic on any of the seven breaches the 25%
guideline (`COVERAGE_GUIDELINE_PCT`) — the Arabic denylist below is for a different, keyword-level
reason.

**it/fr caveat:** the corpora above are public-domain stand-ins, not the exact `ita1927`/`ls1910`
editions production loads (those are only reachable via `api.getbible.net`, which this sandbox
could not reach). Close enough for the coverage question this story asks; a maintainer with
`api.getbible.net` access can re-run against the exact editions per
`docs/HOW-TO-POPULATE-VERSE-TOPICS.md`'s Docker recipe for the stronger confirmation.

### Arabic substring over-firing (the review this story's AC requires)

`SUBSTRING_MATCH_LANGUAGES` matches Arabic by bare substring (clitics attach with no space, so a
word-boundary pattern would miss most real occurrences) — and a short root fires inside unrelated
words even while its topic stays under 25%. Four keywords denylisted for this reason (full worked
examples with real match counts in `api/chat/topic_tagging.py`'s `CORPUS_KEYWORD_DENYLIST`
comment): `حب` (love, 1,071 verses — mostly `صاحبه` "companion", the names `رحبعام`/`حبرون`,
`فحبلت` "conceived"), `أمل` and `يأس` (hope, 397 and 74 verses — mostly unrelated roots meaning
"complete"/"bearer"/"worker"/"widows" and "measure"/"rulership"), `عفو` (forgiveness, 15 verses),
`قلق` (anxiety, 26 verses). Follow-up filed as **BITB-161** to fix the mechanism itself and recover
this recall.

### The ru/zh/hi/ko decision

**Recorded: topic boosting is a seven-language feature**, not an eleven-language one with four
gaps — no new vocabulary authored for `ru`/`zh`/`hi`/`ko`. Reason: the matching mechanism
(word-boundary regex with a bounded suffix allowance) doesn't fit those languages' morphology —
`zh` has no whitespace word boundaries at all, `ko` is agglutinative with particles fused to the
stem, and `hi`/`ru` are inflected enough that a hand-authored list would need to be either huge or
a real morphological analyzer, i.e. a different mechanism, not more keywords. Recorded in
`api/chat/topics.py` (comment above `SUPPORTED_TOPIC_LANGUAGES`) and
`docs/HOW-TO-POPULATE-VERSE-TOPICS.md` ("Scope"). Revisit under LLM-assisted tagging (BITB-044's
deferred item), which is language-agnostic and would cover all eleven in one move.

### Why not the DB-backed dry run

`populate_verse_topics.py --dry-run --verbose` needs `DATABASE_URL` pointed at a translation
already loaded, plus `pydantic`/`pydantic-settings` installed. Neither was available in the
sandbox this validation ran in (no Docker daemon; `api.getbible.net` blocked by egress policy).
`scripts/measure_topic_coverage.py` (new) answers the identical question using the *same* matching
code, loaded directly by file path so it can never silently drift from what the population script
does, against a corpus fetched fresh over HTTPS — see its docstring for the calibration proof.
Use it going forward for any new-language validation that doesn't need a live database.

### Coverage guard

`api/tests/test_topic_coverage_guard.py` (new): structural checks (every denylist entry
references a real keyword; every non-denylisted substring-matched keyword is long enough to be
safe) plus a negative rehearsal that injects a doctored over-firing keyword via
`build_topic_matchers(..., keyword_map=...)` (new parameter) and confirms the same measurement
path reports the breach — for both a word-boundary language and Arabic's substring matching.
Runs on synthetic, non-scripture sample text (license-safe, CI-fast); the real per-language
evidence above is not re-fetched on every CI run.

## User Story

**As** the maintainer, **I want** to know that corpus tagging behaves sanely in every language it
claims to support — and to be explicit about the languages it does not — **so that** topic boosting
is not quietly a two-language feature in an eleven-language product.

## Why This Exists

`scripts/populate_verse_topics.py` tags verses per language from
`TOPIC_KEYWORDS_BY_LANGUAGE`. Three tiers exist today, and only the first is verified:

| tier | languages | status |
|---|---|---|
| validated against real corpus | `en`, `de` | 18.3% of KJV, 12.3% of Luther 1912 tagged; no topic above ~3.2% |
| vocabulary exists, never run on a real corpus | `it`, `es`, `fr`, `pt`, `ar` | `CORPUS_KEYWORD_DENYLIST` ships **empty and unverified** |
| no vocabulary at all | `ru`, `zh`, `hi`, `ko` | skipped outright by the script |

PR #970 is explicit about the middle tier:

> `it`/`es`/`fr`/`pt`/`ar` were not validated against real corpus data (none available in this
> environment) — the runbook calls this out explicitly as a pre-flight step before relying on the
> empty denylist for those languages.

### Why the empty denylist matters

`CORPUS_KEYWORD_DENYLIST` exists because a keyword that is rare in query text can be extremely common
in scripture prose, tagging a large fraction of the corpus and flattening the boost into noise.
BITB-044 adopted a 25% guideline and found `en`/`de` comfortably under it, so the denylist ships
empty — a conclusion that is only established for those two languages.

The failure mode in an unvalidated language is quiet: an over-firing keyword produces a topic that
matches a third of the corpus, the boost stops discriminating, and search gets slightly worse in that
language with no error anywhere. The Arabic path carries extra risk, since it uses substring matching
for attached clitics rather than the word-boundary matching used elsewhere — deliberately, but
substring matching is exactly the mechanism most likely to over-fire.

### Why the missing four matter

`ru`, `zh`, `hi` and `ko` have no topic vocabulary, so the script skips them. Two consequences worth
stating plainly:

- Topic boosting is permanently inert in those languages, and nothing in the product says so.
- They account for **20 of the 58 golden-set cases (34%)**, so any topic-boost evaluation that
  averages across all languages is diluted by a third of cases that cannot move (see BITB-103).

## Proposed Fix

1. **Run the pre-flight for the middle tier.** `--dry-run --verbose` against real `it`/`es`/`fr`/`pt`/
   `ar` corpora; record per-topic coverage the way BITB-044 did for `en`/`de`; extend
   `CORPUS_KEYWORD_DENYLIST` for any topic breaching the 25% guideline. Give Arabic a closer look
   given its substring matching.
2. **Decide the bottom tier explicitly.** Either author keyword vocabulary for `ru`/`zh`/`hi`/`ko`, or
   record that topic boosting is a seven-language feature. Leaving it undecided is the option to rule
   out — that is how a gap becomes permanent by default.
3. **Make the scope legible wherever it matters.** If a language cannot be tagged, that should be
   visible in eval reports (so a flat delta is not misread as "boosting doesn't help") and in the
   runbook, not only in the script's skip log.
4. **Add a coverage guard.** A test or script assertion that no topic exceeds the guideline in any
   validated language, so a future keyword addition cannot silently push one over. The denylist is
   currently empty on the strength of a one-time manual observation; a guard is what makes that
   durable.

## Deferred: LLM-assisted tagging

BITB-044's remaining list also proposes an LLM-assisted tagging pass to catch thematic matches with
no literal keyword overlap ("he restoreth my soul" is about peace without containing a peace
keyword). It composes cleanly with keyword seeding via `ON CONFLICT DO NOTHING`.

Deliberately **not** part of this story. Keyword seeding already tags 18.3% of KJV, which is enough
to measure whether boosting helps at all (BITB-104). Improving tag *recall* before establishing that
the boost is worth having would be optimising an unvalidated feature. Revisit once BITB-104 has
numbers — if the boost helps, better recall is the obvious next lever; if it does not, this work is
moot.

## Acceptance Criteria

- [x] `it`, `es`, `fr`, `pt`, `ar` each run against a real corpus with per-topic coverage recorded
      (offline scan, not the DB-backed dry run — see "Why not the DB-backed dry run" above)
- [x] `CORPUS_KEYWORD_DENYLIST` extended for any topic breaching the 25% guideline, or explicitly
      confirmed empty per language on the strength of a real run (confirmed empty for the 25%
      guideline everywhere; four Arabic keywords denylisted for a keyword-level reason instead)
- [x] Arabic substring matching specifically reviewed for over-firing
- [x] A recorded decision on `ru`/`zh`/`hi`/`ko`: vocabulary authored, or scope documented (scope
      documented; maintainer's to override)
- [x] Untaggable languages are visible in eval reports and the runbook, not only in a skip log
      (already partly shipped by BITB-103 in `api/search_eval/report.py`; the coverage-check job
      summary was the remaining gap, closed here via `check_verse_topic_coverage.py`'s new
      `out_of_scope` status)
- [x] A guard prevents a future keyword from silently pushing a topic past the coverage guideline

## Verification

Coverage percentages are the evidence, and they come only from real corpus runs — this story cannot
be discharged by inspection of the keyword lists, which is precisely why BITB-044 left it open rather
than guessing.

The guard needs a negative test: add a deliberately over-firing keyword in a scratch branch and
confirm it trips.

## Related

- **BITB-044 / PR #970** — established the tagger, the 25% guideline, and the `en`/`de` baseline
- **BITB-103** — the golden set's language distribution, and why untaggable languages must be
  reported separately
- **BITB-104** — the measurement this feeds; also the gate on whether LLM-assisted tagging is worth
  doing at all
- **BITB-116** — the topic-boosting A/B decision; also gates whether BITB-161's recall fix is worth
  doing
- **BITB-161** (new) — Arabic morphology-aware matching, filed to recover the recall this story's
  denylist traded away
- `api/chat/topic_tagging.py`, `api/chat/topics.py`, `scripts/populate_verse_topics.py`,
  `scripts/measure_topic_coverage.py` (new), `scripts/check_verse_topic_coverage.py`,
  `api/tests/test_topic_coverage_guard.py` (new), `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`
