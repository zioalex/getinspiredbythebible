# BITB-051: Search Retrieval-Evaluation Harness (golden set + scorer)

**Status:** 🚧 In Progress (P0 + P1 landed; P2–P4 todo)
**Priority:** P1 (High) — without it we cannot tell whether the now-enabled query
expansion / hybrid search actually improve retrieval
**Size:** L (3–5 days, delivered in 5 small PRs)
**Created:** 2026-06-16
**Parent:** BITB-043 (Validate & Enable Phase-1 Search)

## User Story

As the maintainer, I want a repeatable way to measure verse-retrieval **ranking
quality** (Precision@5 / Recall@10 / MRR) over a curated, multilingual golden set,
so I can validate that query expansion and hybrid search actually help — and tune
their weights — instead of shipping search changes blind. *"Without a golden set I
cannot evaluate it."*

## Problem

Query expansion was enabled by default (PR #741, released 1.27.0) and hybrid search
is being enabled (the trimmed PR #727), but there is **no scorer** that runs the real
search pipeline and reports ranking metrics. Two adjacent assets do not solve it:

- `golden_set/` scores chat **response** quality (scripture present, tone, source) —
  not retrieval ranking.
- `api/tests/fixtures/query_expansion_test_cases.json` lists themes/refs for 10
  queries but has no runnable scorer.

## Scope & key decisions

- **New package `api/search_eval/`** (named distinctly from `golden_set/` to avoid
  conflation) + a thin `scripts/run_search_eval.py` CLI.
- **Ground truth:** hand-curated by the implementer, **maintainer-reviewed in the
  PR**; ~55+ queries across **all 11 supported languages**
  (en/it/de/es/fr/pt/ar/ru/zh/hi/ko, ≥5 each). All 11 translations (incl. Hindi) are
  loaded in prod, so every language has a real corpus.
- **Embeddings: Azure `text-embedding-3-small` (1536) everywhere** — matching prod
  (`deployment/terraform.tfvars`). **No Ollama in the eval**: query embeddings must
  match prod's stored vectors; mixing models yields meaningless cross-model numbers.
- **CI posture:** per-PR CI runs only `--validate` (no DB / no embeddings / no
  secrets — works on forks). All **live** retrieval (smoke + full corpus) runs on
  Azure in a **manual + nightly** workflow, never gating per-PR.
- **Incident guard absorbed from PR #727:** golden cases may list `irrelevant_refs`
  (verses that must NOT surface, e.g. the Italian frustration query must not return
  Job 21:27), scored by a `false_positives_at_k` metric.
- Scope = query expansion + hybrid. Topic boosting is a selectable config but a no-op
  until **BITB-044** populates `verse_topics`.

## Metric definitions

References (ground truth and retrieved) are normalized to canonical verse-key
**matchers** via `api/search_eval/normalize.py`, reusing
`utils.book_names.normalize_book_name` + `LOCALIZED_TO_ENGLISH` (handles localized
names, "Psalm"↔"Psalms", verse ranges, chapter-only refs). For one query with
relevant matchers `R`, irrelevant matchers `I`, and ranked retrieved keys `r₁..rₙ`
(from `VerseResult.reference`, always English canonical):

- **Precision@k** = |{ i ≤ k : rᵢ matches any R }| / k
- **Recall@k** = (# matchers in R covered by some rᵢ, i ≤ k) / |R|  *(matcher-coverage:
  a range or chapter-only ref counts as one item)*
- **MRR** = 1 / rank of first matching rᵢ (0 if none)
- **false_positives@k** = count of top-k matching any `I` (incident guard; healthy = 0)

## Phased delivery (one PR each)

### P0 — Trim PR #727 to the hybrid-search enablement only ✅ (landed)

PR #727 was an earlier, overlapping attempt that also added a duplicate scorer +
12-case golden set. Reconciliation decision: **keep its hybrid flip only.** Removed its
`search_golden_set.json`, `test_search_golden_eval.py`, reverted its `pytest.ini` and
BITB-043 story edits; kept `hybrid_search_enabled = True` + the flag/mocks test updates.
Its good content (exact-phrase regressions, the Job 21:27 incident guard) is absorbed
into this harness.

- **Done when:** PR #727 contains only the hybrid enablement; full backend tests green.

### P1 — Metric + normalization core (pure, no DB) ✅ (landed — PR #745)

`api/search_eval/`: `normalize.py`, `metrics.py`, `models.py` (`GoldenCase` with
`relevant_refs` + `irrelevant_refs`). Pure-function `precision_at_k` / `recall_at_k` /
`mrr` / `false_positives_at_k`. Tests `api/tests/test_search_eval_metrics.py` run in the
blocking `backend-tests` job.

- **Done when:** `pytest tests/test_search_eval_metrics.py` green; metric values match
  hand-computed expectations. **No DB.**

### P2 — Golden set data + loader + `--validate` + non-blocking CI (todo)

- `api/search_eval/data/retrieval_golden_set.json`: 55+ cases, all 11 languages (≥5
  each), seeded from `query_expansion_test_cases.json` + #727's 12 cases (with
  `irrelevant_refs`), expanded with pastoral judgement. **Maintainer reviews labels.**
- `api/search_eval/loader.py` (+ filters); `scripts/run_search_eval.py --validate` (no
  DB/LLM): loads, checks coverage, prints summary.
- Tests `api/tests/test_search_eval_dataset.py`: unique ids; ≥55 cases; all 11
  languages; every case ≥1 `relevant_refs`; all refs normalize.
- Non-blocking `search-eval-validate` job (`continue-on-error: true`) in
  `test_update.yml` running `--validate`.
- **Done when:** `--validate` exits 0 with ≥55 cases / 11 languages; dataset tests green.

### P3 — Runner (real retrieval) + report + CLI (todo)

- `api/search_eval/runner.py`: bootstrap standalone like
  `scripts/migrations/run_migrations.py`
  (`providers.factory.create_*_provider`, `scripture.database.async_session_factory`);
  per query reuse the real `ScriptureSearchService` paths and, for expansion,
  `ChatService._expand_query` → `embedding.embed` → `search(extra_embeddings=[…])`,
  mirroring `_search_scripture`. Fail-open per query; **read-only**.
- Named `EvalConfig`s: `baseline_semantic`, `expansion_semantic` (default A/B),
  `hybrid`, `hybrid_expansion`, optional `topic_boosted` (warn until BITB-044).
- `report.py`: configs × P@5/R@10/MRR table + per-language breakdown + false-positive
  guard + expansion latency/cost. CLI: `--config`, `--language`, `--json`, `--smoke`.
- `docs/SEARCH_EVAL_HOWTO.md`; update BITB-043 + `BACKLOG.md`.
- **Done when:** manual `DATABASE_URL=<prod-ro>` + Azure env →
  `run_search_eval.py` prints the expansion OFF-vs-ON A/B table + per-language breakdown.

### P4 — Full-corpus eval automated in CI (Routes A + B; manual + nightly) (todo)

New `.github/workflows/search-eval-full.yml` (`workflow_dispatch` + nightly
`schedule`), Azure embeddings, results as job summary + uploaded artifact, non-gating:

- **Route A (`eval-prod`):** `DATABASE_URL` from `PROD_DATABASE_URL` secret (read-only);
  embed queries with Azure; retrieve from prod's vectors. True prod numbers, no rebuild.
- **Route B (`eval-corpus`):** load all 11 translations + Azure-embed into pgvector,
  cached via `actions/cache` (key = translations + model + script versions); full A/B.
- **`eval-smoke`:** load 1 Corinthians + Azure-embed (~440 verses, cents); fast
  end-to-end plumbing proof (replaces the old Ollama smoke).
- Secrets: the read-only `PROD_DATABASE_URL` plus the `AZURE_OPENAI_*` endpoint /
  key / deployment credentials; jobs no-op with a clear notice if absent.
- **Done when:** dispatch produces an artifact + summary with the full-corpus A/B table
  (Routes A + B + smoke); nightly runs unattended; per-PR CI unchanged.

## Acceptance Criteria

- [x] P0: PR #727 trimmed to hybrid-search enablement only.
- [x] P1: `api/search_eval/` core (normalize + metrics + `GoldenCase` incl.
      `irrelevant_refs`) with no-DB tests in the blocking job.
- [ ] P2: 55+ multilingual golden set (all 11 languages) + loader + `--validate` +
      non-blocking CI; maintainer-reviewed labels.
- [ ] P3: runner over real retrieval + report/CLI; manual prod-read-only A/B table.
- [ ] P4: manual + nightly full-corpus eval (Routes A & B + smoke) on Azure.
- [ ] Retrospective once expansion/hybrid validated against the set (feeds BITB-043).

## Files / Config

| Item | Location |
|---|---|
| Harness package | `api/search_eval/` (`normalize.py`, `metrics.py`, `models.py`, `loader.py`*, `runner.py`*, `report.py`*) |
| Golden set | `api/search_eval/data/retrieval_golden_set.json`* |
| CLI | `scripts/run_search_eval.py`* |
| Tests | `api/tests/test_search_eval_metrics.py`, `…_dataset.py`* |
| CI | `.github/workflows/test_update.yml` (validate)*, `search-eval-full.yml`* |
| Reused utils | `utils/book_names.py`, `scripture/search.py`, `providers/factory.py`, `scripture/database.py` |

Note: items marked with `*` above are future phases (P2–P4).

## Related

- **BITB-043** — parent (validate & enable Phase-1 search); this harness is its
  evaluation tooling. Hybrid enabled via the trimmed PR #727; expansion via #741.
- **BITB-044** — populate `verse_topics` so the `topic_boosted` config is meaningful.
- **BITB-018** — original Phase-1 search work.
