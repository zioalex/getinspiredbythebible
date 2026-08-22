# BITB-107: `eval-smoke` Cannot Pass — the Plumbing Check Has Broken Plumbing

**Status:** 🎯 Todo
**Priority:** P1 — the only route that was safe to run before letting the nightly touch production
is the one that fails; it currently blocks the recommended pre-flight entirely
**Size:** S–M (config fixes; one root cause still to be pinned down)
**Created:** 2026-08-22
**Prompted by:** run
[32565015468](https://github.com/zioalex/getinspiredbythebible/actions/runs/32565015468), the first
real `eval-smoke` execution after `AZURE_OPENAI_ENDPOINT` was configured

## User Story

**As** the operator, **I want** `route=smoke` to actually pass, **so that** I have a way to prove the
search-eval harness works end to end without pointing it at the production database — which is the
entire reason the smoke route exists.

## What Happened

With Azure credentials finally in place, `eval-smoke` got much further than before and still failed.
Steps 1–10 all succeeded: 1 Corinthians loaded, **437 verses embedded via Azure**, the eval ran. The
job failed only at step 11, the exit-code gate, because `run_search_eval.py` returned 1:

```
search-eval query failed, scoring as zero (fail-open)   (×6)
ERROR: every query failed — DB/provider likely unreachable.
```

All six query results (3 cases × 2 configs) errored. Five carry `"error": "Connection error."`; the
sixth `"embedding circuit breaker open"` — the `ResilientEmbeddingProvider` breaker tripping after
the preceding failures, which is correct behaviour reacting to a real fault.

`"Connection error."` is `openai.APIConnectionError`'s default message, so the embedding HTTP call
never completed.

## Findings

### 1. The failure is on the embedding path, not the LLM path

Worth stating because it is the intuitive wrong answer: `baseline_semantic` sets `use_expansion=False`
and needs no LLM at all, and it failed on all three cases with the same `"Connection error."`. Every
result also carries `"expansion_used": false`. So a missing OpenRouter/LLM credential is **not** the
cause.

### 2. Ruled out by inspection

- **Client construction.** `api/providers/azure_openai.py` builds
  `AsyncAzureOpenAI(azure_endpoint=..., api_key=..., api_version="2024-02-01")` — character-for-character
  the same call `scripts/create_azure_embeddings.py` makes, and that script embedded 437 verses
  against the same endpoint seconds earlier in the same job.
- **Missing endpoint or key.** `providers/factory.py` raises `ProviderError` when either is empty. It
  did not raise, so both were populated.

So a direct client reaches Azure from this runner while the app's provider does not. The remaining
difference is inside the settings/resilience layer, and pinning it down needs a run with debug
logging — it is not determinable from static reading.

### 3. A second, independent defect that will bite immediately after

`config.py` defaults `embedding_dimensions: int = 1024`, and `validate_embedding_dimensions()`
**deliberately skips** the azure_openai provider:

```python
if self.embedding_provider == "azure_openai":
    # dimension validation is skipped
    return self
```

The smoke workflow never sets `EMBEDDING_DIMENSIONS`, so the provider is constructed with
`dimensions=1024` — while the corpus was loaded with `load_bible.py --ci --dimensions 1536` and the
column is `vector(1536)`. `text-embedding-3-small` honours a 1024 request, so Azure returns 200 and
the mismatch surfaces later as a pgvector error rather than anything obvious.

This is currently masked by finding 2: no embedding call succeeds, so nothing reaches the dimension
check. Fixing the connection without fixing this trades one failure for a more confusing one.

### 4. The smoke route has no `--config` guard, unlike `eval-prod`

`eval-smoke` runs `--run --smoke --json` with no `--config`, so it uses
`DEFAULT_AB = ("baseline_semantic", "expansion_semantic")`. The expansion leg needs an LLM provider;
with no `LLM_PROVIDER` set it falls back to `config.py`'s default `"ollama"`, and no Ollama server
runs on the runner. `eval-prod` handles exactly this:

```bash
elif [ "$HAS_LLM" != "true" ]; then
  config_flag=(--config baseline_semantic)
fi
```

`eval-smoke` has no equivalent. Not the current failure — but it guarantees half the smoke run stays
broken even once findings 2 and 3 are fixed. The route billed as credential-light demands a
credential nobody gave it.

## Proposed Fix

1. **Set `EMBEDDING_DIMENSIONS: "1536"`** in the `eval-smoke` job env so the provider matches the
   column the job itself creates.
2. **Give `eval-smoke` the same config guard as `eval-prod`** — default it to `--config
   baseline_semantic` unless an LLM credential is present.
3. **Root-cause the `APIConnectionError`** with one debug run (log the resolved endpoint, deployment
   and timeout at provider construction). Fix, then confirm a green smoke run.
4. **Consider whether the dimension validator should stop skipping azure_openai.** Skipping it is
   why a 1024/1536 mismatch is expressible at all. A check that `embedding_dimensions` matches the
   configured deployment's native size would have caught finding 3 at startup rather than at query
   time — and would protect production, not just this workflow.

## Acceptance Criteria

- [ ] `eval-smoke` completes green on a manual `workflow_dispatch` with `route=smoke`
- [ ] `EMBEDDING_DIMENSIONS` is set for the smoke job and matches the seeded column width
- [ ] `eval-smoke` does not attempt the expansion leg without an LLM credential
- [ ] The `APIConnectionError` root cause is identified and recorded — not merely worked around
- [ ] A decision recorded on whether `validate_embedding_dimensions()` should cover azure_openai
- [ ] The runbook's "run smoke first" advice is true again

## Verification

A green run is the criterion, but green is not sufficient on its own: confirm the summary shows the
smoke job **ran** rather than skipped (preflight skips are reported as success), and confirm at least
one query returned actual verses. A run where all six cases still score 0.00 with `n_errors: 3` is
the current failure wearing a passing exit code.

## Related

- **BITB-051 P4a / PR #968** — introduced this workflow
- **BITB-101** — the `eval-prod` credential story; same workflow, different defect
- `.github/workflows/search-eval-full.yml`, `api/providers/azure_openai.py`,
  `api/providers/embedding_resilience.py`, `api/providers/factory.py`, `api/config.py`
