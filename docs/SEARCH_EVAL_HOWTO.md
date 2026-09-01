# Search-Eval Harness — How To (BITB-051)

A repeatable scorer that measures **verse-retrieval ranking quality**
(Precision@5 / Recall@10 / MRR) over a curated, multilingual golden set — so
query expansion and hybrid search can be validated and tuned against real
numbers instead of shipped blind.

This is **not** the same tool as `golden_set/`, which scores chat *response*
quality (scripture present, tone, source). This harness only measures
*retrieval ranking* — does the right verse come back, and how high.

## Prerequisites for `--run`

`--validate` needs nothing but the repo. `--run` executes the **real**
search pipeline and needs:

- `DATABASE_URL` — a Postgres instance with the scripture corpus loaded
  (ideally read-only access to prod's data, since retrieval quality depends
  on the actual stored embeddings).
- An embedding provider configured to match how the target database's
  vectors were generated. **Prod uses Azure `text-embedding-3-small`
  (1536-dim)** — set `EMBEDDING_PROVIDER=azure_openai`,
  `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`,
  `AZURE_EMBEDDING_DEPLOYMENT`. **Do not use Ollama embeddings against Azure
  vectors** — query embeddings must come from the same model family as the
  stored vectors, or similarity scores are meaningless.
- An LLM provider (for `*_expansion` configs only) — whatever
  `LLM_PROVIDER`/related env vars the app normally uses.

## Commands

```bash
# No DB required — validates the golden-set file structure (also runs in CI)
python scripts/run_search_eval.py --validate

# Fast plumbing check: 3 cases only, default A/B configs
python scripts/run_search_eval.py --run --smoke

# Full run, default A/B (baseline_semantic vs expansion_semantic)
DATABASE_URL=... EMBEDDING_PROVIDER=azure_openai ... \
  python scripts/run_search_eval.py --run

# Specific configs, one language
python scripts/run_search_eval.py --run --config hybrid,hybrid_expansion --language it

# Machine-readable output
python scripts/run_search_eval.py --run --json

# A/B: unboosted vs boosted (needs a populated verse_topics — see below)
python scripts/run_search_eval.py --run --config hybrid,topic_boosted

# Factor sweep — one report row per point on the curve
python scripts/run_search_eval.py --run --config topic_boosted --topic-boost-factor 0.0,0.1,0.2,0.4,0.8
```

Available config names (`search_eval.runner.EVAL_CONFIGS`):

| Config | Search method | Expansion |
|---|---|---|
| `baseline_semantic` | `search()` (semantic only) | no |
| `expansion_semantic` | `search()` | yes |
| `hybrid` | `search_hybrid()` | no |
| `hybrid_expansion` | `search_hybrid()` | yes |
| `topic_boosted` | `search_hybrid_boosted()` (`verse_topics` LEFT JOIN, factor from the config/`--topic-boost-factor`) | no |

Default `--config` is the A/B pair `baseline_semantic,expansion_semantic`.

## Reading the results

The report prints a configs × P@5/R@10/MRR/FP@5 table, a per-language
breakdown, mean expansion latency (for `*_expansion` configs), and the
false-positive guard status (should read `healthy (0)` — any non-zero count
means a query surfaced a verse explicitly flagged as irrelevant, e.g. the
Italian frustration query returning Job 21:27; investigate immediately).

**Versification caveat:** `relevant_refs` in the golden set are
English-canonical, and retrieved references are also always English-canonical
— so a *correct* hit in a non-English translation can still score as a miss
if that translation numbers the verse differently (Psalm superscriptions,
Joel/Malachi chapter splits, etc.). Read per-language scores with this in
mind; closing the underlying reference-normalization gaps is tracked in
**BITB-052**.

**Topic-tagging caveat (BITB-103):** the keyword-based topic tagger
(`api/chat/topics.py`) only supports `en, it, de, es, fr, pt, ar`.
`ru, zh, hi, ko` golden-set cases are tagged with a trailing `*` in the
per-language breakdown and a footnote — a flat (zero-delta) result for those
languages means **"not taggable"**, not "topic boosting doesn't help". The
same caveat applies to `--validate`'s printed coverage summary.

**Topic boosting (BITB-104):** `topic_boosted` applies the real boost —
`search_hybrid_boosted()`'s `verse_topics` LEFT JOIN, weighted by
`topic_boost_factor` (per-config, sweepable with `--topic-boost-factor`).
Boost topics for each query come from `detect_topics(query)`, the same
keyword tagger production uses — a query the tagger doesn't tag is
unboosted *by design*, matching production behavior exactly. This means the
BITB-103 untaggable-language caveat above still governs how to read a flat
`ru/zh/hi/ko` delta: "not taggable", not "boosting doesn't help".

**Prerequisite:** `verse_topics` must be populated for the corpus under eval
(`scripts/populate_verse_topics.py`) or the run **hard-errors** instead of
reporting unboosted numbers under a boosted config name — the failure this
story exists to close. `eval-smoke`'s ephemeral corpus does not run
`populate_verse_topics.py`, so passing `configs: topic_boosted` to the smoke
route is expected to hard-error; that is the guard working, not a break.

`topic_boost_factor` sweep results — pending the first `eval-prod` run with
`configs: hybrid,topic_boosted` (see the P4a section below). No numbers are
recorded here yet; a maintainer with prod-read-only DB access runs the sweep
and records the curve and the `topic_boosting_enabled` decision once
available — see BITB-115.

| `topic_boost_factor` | P@5 | R@10 | MRR | FP@5 |
|---|---|---|---|---|
| *pending first `eval-prod` run* | | | | |

## Golden-set schema and the `topics` field (BITB-103)

Every case in `api/search_eval/data/retrieval_golden_set.json` must carry a
`topics` field: a list of zero or more canonical topic ids (the top-level
keys of `TOPIC_KEYWORDS_BY_LANGUAGE` in `api/chat/topics.py` — anger,
anxiety, fear, forgiveness, grief, guidance, hope, joy, loneliness, love,
patience, peace, trust). An **empty list is the explicit marker for a
neutral, non-thematic case** (a plain reference lookup, a factual/narrative
question) — it is not an oversight to leave it empty, it's the control group
that lets an eval detect a boosting-induced regression on ordinary queries.

`category`/`tags` stay free-text, human-facing labels (unchanged by this
story) — `topics` is the machine-checked link `--validate` and the dataset
test suite (`api/tests/test_search_eval_dataset.py::TestTopicCoverage`)
actually enforce: every canonical topic needs **≥3 labelled cases**
(`topics` names it) **and ≥2 taggable cases** (a case in a tagger-supported
language where `detect_topics(query)` actually returns that topic too) — a
topic with plenty of labelled cases the tagger never produces is exactly as
unmeasurable as one with zero cases. The neutral subset needs **≥6 cases**.

**When adding a new case:** before committing it, run its query through
`detect_topics()` and record the result in the case's `notes` field —
substring artifacts are common and easy to miss by eye (e.g. Spanish `"fe"`
["faith"] fires inside English *"I **fe**el alone"* and *"suffering"*;
German `"weg"` ["way"] fires inside *"weg**en**"* ["because of"]). A tagger
hit that isn't the query's real theme doesn't need to be added to `topics`
(ground truth), but it's worth a one-line note so the next reader isn't
surprised by the reported coverage counts.

**Deciding where a non-canonical category maps** (the `strength`/`provision`
precedent): `strength` (7 cases, all tagged `perseverance`/`faith`) maps to
`patience` — `perseverance` is a literal `patience` keyword in every one of
its 6 Latin-script languages, and `Isaiah 40:31` ("they that **wait** upon
the LORD shall renew their strength") is used by every one of those cases.
`provision` (1 case, "worried about money and finances") maps to
`["anxiety", "trust"]` — `anxiety` because `detect_topics()` genuinely fires
it (the word "worried"), `trust` because the theme (trusting God to provide)
is real even though the tagger doesn't catch it from this phrasing. Adding
`strength`/`provision` as new *canonical* topics instead was considered and
rejected: `TOPIC_KEYWORDS_BY_LANGUAGE` is also the source for
`scripts/populate_verse_topics.py`'s production tagging, so a new canonical
topic means authoring keyword vocabulary in 7 languages and re-validating it
against the corpus (BITB-106) — a different, larger story than "the golden
set can't measure the topics that already exist".

## Satisfying the story's "Done when" bullet

BITB-051 P3's acceptance criterion is: a maintainer with prod-read-only DB
access and Azure credentials runs

```bash
DATABASE_URL=<prod-read-only-url> EMBEDDING_PROVIDER=azure_openai \
  AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... AZURE_EMBEDDING_DEPLOYMENT=... \
  python scripts/run_search_eval.py --run
```

and gets the expansion OFF-vs-ON A/B table with a per-language breakdown.
This cannot be exercised inside a sandboxed dev environment with no prod DB
or Azure credentials — the harness's *code* is tested against injected fakes
(see `api/tests/test_search_eval_runner.py`); the *live* A/B numbers are
produced automatically by the CI workflow below (**P4a**).

## Running it in CI (P4a)

`.github/workflows/search-eval-full.yml` runs this harness for real, on a
schedule and on demand — no maintainer machine required:

- **`eval-prod`** — read-only against the production database (host discovered
  the same way `azure-deploy.yml` does; authenticated as the dedicated
  read-only `search_eval_ro` role, not the deploy pipeline's admin credential
  — BITB-101), Azure-embeds the golden set's queries, and retrieves from
  prod's real vectors. True prod numbers, no rebuild, no writes.
- **`eval-smoke`** — loads 1 Corinthians into an ephemeral CI Postgres,
  Azure-embeds it, and runs `--run --smoke`. Proves the CLI/Azure plumbing
  end-to-end without touching prod. Its P@5/R@10/MRR are expected to be
  **~0** — the golden set's first 3 cases live in Matthew/Philippians/Proverbs,
  not 1 Corinthians — so a non-zero *exit code* is the failure signal here,
  not the metric values. **Zero verses retrieved is a warning, not a failure**
  (BITB-107, live-verified): a fully healthy run against this narrow,
  single-book corpus can legitimately clear zero rows above the default
  0.35 similarity threshold for topically unrelated queries. A nonzero query
  error count is the real, unambiguous failure signal.

**Running the topic-boost A/B and sweep (BITB-104):** trigger
**Actions → Search Eval — Full → Run workflow** with `configs:
hybrid,topic_boosted` against `eval-prod` (the only route with a populated
`verse_topics`) to get real numbers. `eval-smoke`'s ephemeral corpus never
runs `scripts/populate_verse_topics.py`, so passing `configs: topic_boosted`
to it hard-errors by design (see above) — don't add `topic_boosted` there.

`eval-smoke` always runs `--config baseline_semantic` only (BITB-107) — unlike
`eval-prod`, which falls back to `baseline_semantic` only when no OpenRouter
key is configured. Smoke's whole purpose is credential-light plumbing
verification, so it never attempts the `expansion_semantic` leg (which needs
an LLM provider) regardless of whether an LLM credential happens to be
present; pass the workflow's `configs` input to override this deliberately
for a manual run. `EMBEDDING_DIMENSIONS` must match the target corpus — `1536`
for `azure_openai` (`text-embedding-3-small`), `1024` for Ollama's
`mxbai-embed-large` — and is now enforced by `config.py`'s
`validate_embedding_dimensions()` at startup for both providers (previously
azure_openai was silently skipped, letting a mismatch reach query time
instead of failing fast).

`eval-smoke` also pins `--translation kjv` explicitly (BITB-107, live-verified),
matching the translation code its "Load 1 Corinthians" step actually loads.
Without it, every query silently resolves to `resolve_translation()`'s
language-based default (`"web"` for English) instead of what the corpus
actually contains — `resolve_translation()`'s readiness-aware behavior only
works inside the running FastAPI app (`api/main.py`'s background refresh
populates the cache it consults), which this standalone CLI never runs, so it
always falls back to the static per-language default regardless of what a
given ephemeral CI database actually has loaded. That produces a valid,
error-free, permanently-empty result — not an exception, so it doesn't show
up as a query error, just as zero verses retrieved for every case.

**Troubleshooting `"Connection error."`** — this is `openai.APIConnectionError`'s
fixed, uninformative default message; it tells you nothing about the actual
cause. `eval-smoke` runs a dedicated `--probe-embedding` step (BITB-107)
*before* the eval step specifically so a real failure prints its full
exception chain into the console log instead of being buried in the JSON
artifact as this one opaque string. To reproduce locally:

```bash
EMBEDDING_PROVIDER=azure_openai AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... \
  AZURE_EMBEDDING_DEPLOYMENT=... EMBEDDING_DIMENSIONS=1536 \
  python scripts/run_search_eval.py --probe-embedding
```

It prints the resolved provider config (endpoint scheme+host only, never the
full URL or key), makes one real `embed()` call through the app's actual
cache+resilience-wrapped provider stack, and on failure prints
`traceback.print_exception`'s full chain to stderr — including a cause like
`httpx`/`h11`'s `LocalProtocolError` from an illegal header value, which is
exactly what a trailing `\r`/`\n` surviving into `AZURE_OPENAI_API_KEY` (a
Windows line-ending artifact) produces. `config.py` now strips whitespace
from the Azure endpoint/key/deployment fields for this reason.

Both routes run nightly (04:23 UTC) and via **Actions → Search Eval — Full →
Run workflow** (`route: both | prod | smoke`, optional `configs` / `language`
inputs). Results land as a `$GITHUB_STEP_SUMMARY` table and as a downloadable
JSON+log artifact (30-day retention). Missing secrets/vars make the affected
job skip with a `::notice::` rather than fail — this workflow never runs on
`pull_request` and never gates a merge.

### When `eval-prod` shows up as *skipped*

Its credential, `SEARCH_EVAL_DB_PASSWORD`, is scoped to the `search-eval`
GitHub environment, and an environment-scoped secret is readable only from a
job that declares that environment. The check therefore lives in its own
`prod-secret-check` job ("Check search-eval environment") — read that job, not
`preflight`, to find out why Route A did not run:

| what you see | what it means |
| --- | --- |
| `prod-secret-check` **skipped** | a repo-level precondition failed — the `preflight` summary table names which (ARM login, `TF_VAR_DB_NAME`, Azure OpenAI), or the run was dispatched with `route: smoke` |
| `prod-secret-check` **success**, `eval-prod` **skipped** | the environment exists but `SEARCH_EVAL_DB_PASSWORD` is unset in it — set it under Settings → Environments → search-eval → Environment secrets |
| both **success** | Route A ran; its numbers are in the summary and the artifact |

Checking that secret from `preflight` instead looks correct and is not: it
reads as empty there whether or not the operator ever set it, which pins
`eval-prod` to *always* skipped. `preflight` also gates `eval-smoke`, which
needs no prod credential, so it deliberately stays outside the environment.

**Not yet built:** a third route (`eval-corpus`, tracked as **P4b**) that
rebuilds all 11 translations from scratch into a cached pgvector instance, for
a reproducible-corpus A/B that doesn't drift with prod's live data. Deferred
deliberately — see the "P4b" section of
`docs/BACKLOG_STORIES/BITB-051-search-retrieval-eval-harness.md` for why.
Until it lands, `eval-prod` is the only source of real A/B numbers, and its
per-language scores still carry the versification caveat above.
