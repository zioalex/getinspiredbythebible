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
```

Available config names (`search_eval.runner.EVAL_CONFIGS`):

| Config | Search method | Expansion |
|---|---|---|
| `baseline_semantic` | `search()` (semantic only) | no |
| `expansion_semantic` | `search()` | yes |
| `hybrid` | `search_hybrid()` | no |
| `hybrid_expansion` | `search_hybrid()` | yes |
| `topic_boosted` | `search_hybrid()` (boosting is a **no-op**, see below) | no |

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

**`topic_boosted` is a documented no-op** until **BITB-044** populates
`verse_topics` — the runner logs a warning and falls back to plain hybrid
search, so its numbers are expected to equal `hybrid`'s. Don't read anything
into `topic_boosted` results until BITB-044 ships.

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

- **`eval-prod`** — read-only against the production database (DB connection
  built the same way `azure-deploy.yml` does for migrations/seeding — no new
  DB secret), Azure-embeds the golden set's queries, and retrieves from prod's
  real vectors. True prod numbers, no rebuild, no writes.
- **`eval-smoke`** — loads 1 Corinthians into an ephemeral CI Postgres,
  Azure-embeds it, and runs `--run --smoke`. Proves the CLI/Azure plumbing
  end-to-end without touching prod. Its P@5/R@10/MRR are expected to be
  **~0** — the golden set's first 3 cases live in Matthew/Philippians/Proverbs,
  not 1 Corinthians — so a non-zero *exit code* is the failure signal here,
  not the metric values.

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

**Not yet built:** a third route (`eval-corpus`, tracked as **P4b**) that
rebuilds all 11 translations from scratch into a cached pgvector instance, for
a reproducible-corpus A/B that doesn't drift with prod's live data. Deferred
deliberately — see the "P4b" section of
`docs/BACKLOG_STORIES/BITB-051-search-retrieval-eval-harness.md` for why.
Until it lands, `eval-prod` is the only source of real A/B numbers, and its
per-language scores still carry the versification caveat above.
