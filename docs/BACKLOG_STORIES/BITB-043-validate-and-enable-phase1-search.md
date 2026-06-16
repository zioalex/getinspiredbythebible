# BITB-043: Validate & Enable Phase-1 Search Improvements

**Status:** 🎯 Todo
**Priority:** P1 (High) — high-ROI relevance fix; code already merged, just gated off
**Size:** M (1-2 days)
**Created:** 2026-06-07

## User Story

As a user seeking spiritual guidance, I want search to use the query-expansion and
hybrid (semantic + keyword) retrieval that was already built, so that I get
thematically relevant verses instead of literal keyword matches — without the team
having to write new retrieval code first.

## Problem

The Phase-1 search improvements from **BITB-018** (query expansion, hybrid search,
topic boosting) were implemented and merged in Feb 2026
(`docs/DONE/2026-02-24-query-understanding-context-quality.md`) but ship **disabled**:
the feature flags default `False` and no deployment/env file enables them
(`api/config.py:76–85`). Production search is therefore still **pure semantic** — the
incident that motivated the work (frustrated Italian user → irrelevant Job 21:27) would
still reproduce today. The code has been dark and unvalidated for ~3.5 months.

This story is **validation + rollout only** — no new retrieval features. It carves the
"flip the already-built flags safely" work out of BITB-018. (Topic boosting is excluded
here because it is additionally blocked on empty data — see **BITB-044**.)

## Scope

In scope:

- **Query expansion** (`query_expansion_enabled`) — `api/chat/service.py:_expand_query`
- **Hybrid search** (`hybrid_search_enabled`) — `api/scripture/repository.py:search_verses_hybrid`,
  migration `003_add_fulltext_index.sql`, weights `hybrid_search_semantic_weight` / `_keyword_weight`

Out of scope:

- **Topic boosting** rollout — blocked on `verse_topics` population (**BITB-044**)
- Phase 2–4 (enriched/multi-vector embeddings, reranking, fine-tuning)

## Approach

1. **Build the golden eval set** — `tests/fixtures/query_understanding_golden_set.json`,
   50+ queries across languages with relevant/irrelevant verse annotations
   (see `docs/GOLDEN_SET_GUIDE.md` and the seed examples in the BITB-018 story).
2. **Measure baseline** Precision@5 / Recall@10 / MRR with all flags off.
3. **Enable hybrid search** first (strict-improvement, low risk, no LLM cost): confirm
   exact-phrase queries (e.g. "peace be still" → Mark 4:39) land in top-3 and metrics
   don't regress; verify the GIN full-text indexes from migration `003` exist in prod.
4. **Enable + A/B query expansion**: watch added latency (must keep total < 2s) and the
   ~$0.001/query LLM cost; gate by the same golden-set metrics + thumbs-up rate.
5. **Tune weights** (`hybrid_search_semantic_weight` / `_keyword_weight`) against the
   golden set; document chosen values.
6. **Retrospective** in `docs/DONE/`.

## Acceptance Criteria

- [ ] Golden eval set committed (50+ queries, multilingual) with a runnable scorer
      reporting Precision@5 / Recall@10 / MRR.
- [ ] Baseline (all flags off) measured and recorded.
- [ ] Hybrid search enabled in prod; exact-phrase regression cases pass; no metric regression.
- [ ] Query expansion enabled (A/B or staged); total search latency stays < 2s; LLM cost
      measured and within expectation.
- [ ] Chosen hybrid weights documented; final metrics show improvement over baseline.
- [ ] Full backend test suite passes.
- [ ] Retrospective written in `docs/DONE/`.

## Files / Config

| Item | Location |
|---|---|
| Feature flags | `api/config.py:76–85` (`query_expansion_enabled`, `hybrid_search_enabled`, weights) |
| Query expansion | `api/chat/service.py` (`_expand_query`) |
| Hybrid search | `api/scripture/repository.py` (`search_verses_hybrid`) |
| Full-text index | `scripts/migrations/003_add_fulltext_index.sql` |
| Golden set guide | `docs/GOLDEN_SET_GUIDE.md` |

## Related

- **BITB-018** — parent story (now "code complete, pending validation & rollout")
- **BITB-044** — populate `verse_topics` so topic boosting can also be enabled
- `docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md` — Phase 1 context
