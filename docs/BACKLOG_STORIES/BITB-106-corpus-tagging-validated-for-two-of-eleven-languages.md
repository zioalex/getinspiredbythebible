# BITB-106: Corpus Tagging Is Validated for Two Languages and Impossible for Four

**Status:** 🎯 Todo
**Priority:** P2 — a quality and scope-honesty gap, not a correctness bug; topic boosting works where
it is validated and silently does nothing where it is not
**Size:** M (corpus runs and vocabulary work; the ru/zh/hi/ko decision is the maintainer's)
**Created:** 2026-08-21
**Prompted by:** PR #970 (BITB-044), which validated its tagging against real corpora for `en` and
`de` only

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

- [ ] `it`, `es`, `fr`, `pt`, `ar` each run against a real corpus with per-topic coverage recorded
- [ ] `CORPUS_KEYWORD_DENYLIST` extended for any topic breaching the 25% guideline, or explicitly
      confirmed empty per language on the strength of a real run
- [ ] Arabic substring matching specifically reviewed for over-firing
- [ ] A recorded decision on `ru`/`zh`/`hi`/`ko`: vocabulary authored, or scope documented
- [ ] Untaggable languages are visible in eval reports and the runbook, not only in a skip log
- [ ] A guard prevents a future keyword from silently pushing a topic past the coverage guideline

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
- `api/chat/topic_tagging.py`, `api/chat/topics.py`, `scripts/populate_verse_topics.py`,
  `docs/HOW-TO-POPULATE-VERSE-TOPICS.md`
