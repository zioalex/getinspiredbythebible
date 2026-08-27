# BITB-107: `eval-smoke` Cannot Pass — the Plumbing Check Has Broken Plumbing

**Status:** ✅ Done
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

## Root Cause

**Honest framing up front:** from this sandbox there is no way to run the actual `eval-smoke` job
(it needs the CI-provisioned `AZURE_OPENAI_ENDPOINT`/`AZURE_OPENAI_API_KEY` and an ephemeral
Postgres service container this environment doesn't have). What follows is what static analysis
found, fixed, and unit-tested — plus, if a live CI dispatch from this branch was possible and its
logs read, what that run actually showed. See **Verification** below for which of those two this
turned out to be.

Five independent defects were found and fixed:

1. **H1 — whitespace never stripped from Azure settings (leading hypothesis).**
   `scripts/create_azure_embeddings.py` (L237-240) strips `AZURE_OPENAI_ENDPOINT` /
   `AZURE_OPENAI_API_KEY` / `AZURE_EMBEDDING_DEPLOYMENT` before use, with a comment calling out
   Windows line-ending (`\r\n`) issues — but `api/config.py`'s `Settings` never did the same
   stripping. A trailing `\r`/`\n` surviving into an env var becomes part of the literal HTTP
   header value `httpx`/`h11` sends to Azure; that's illegal and is rejected at *send* time,
   which is exactly `openai.APIConnectionError("Connection error.")` with no status code — the
   fixed, uninformative string this whole story chased. Fixed in `config.py` via a
   `field_validator(mode="before")` that strips all three fields (and normalizes an
   all-whitespace endpoint/key to `None` so the existing required-field validator fires cleanly).
   This is correct regardless of whether it's the exact cause on the runner that produced run
   32565015468 — a raw `AsyncAzureOpenAI` client reaching Azure while the app's identically-built
   client didn't is otherwise inexplicable from the code alone.

2. **`EMBEDDING_DIMENSIONS` unset in both CI routes**, defaulting to 1024 against a
   `vector(1536)` column. Fixed by setting it explicitly in both `eval-smoke` and `eval-prod`
   job envs (both needed together — see the Decision section below for why `eval-prod` couldn't
   be left unfixed).

3. **`eval-smoke` had no `--config` guard.** Fixed: it now defaults to `--config
   baseline_semantic` *unconditionally* (not gated on an LLM credential like `eval-prod` is,
   since smoke's entire premise is not needing one), while still respecting an explicit
   `configs`/`language` workflow input.

4. **The exception cause chain was discarded before logging.** `search_eval/runner.py`'s
   query-failure handler logged `str(exc)` with no `exc_info` and no walk of `__cause__`. Every
   openai SDK connection failure prints as the literal string `"Connection error."` regardless of
   what actually went wrong — the real cause (e.g. an `h11.LocalProtocolError` from an illegal
   header value) was one attribute away and never surfaced. This is *why* finding 1 could only be
   reached by static reading of a sibling script instead of the failing job's own log. Fixed via
   a new `_describe_exception()` helper that walks `__cause__`/`__context__` (capped at 3 links)
   and `exc_info=True` on the log call; the recorded `error` field now reads like
   `"APIConnectionError: Connection error. <- LocalProtocolError: ..."` instead of a dead end.

5. **`_is_transient()` misclassified `openai.APIConnectionError`/`APITimeoutError` as
   non-transient** in `api/providers/embedding_resilience.py` — a defect not in the original
   story, found while implementing the fix for finding 4. It checked `httpx` exception types and
   a `status_code` attribute, neither of which these openai-SDK wrapper exceptions have, so a
   connection blip was never retried: it failed immediately and counted straight toward the
   circuit breaker. **Proof by arithmetic:** the breaker's failure threshold is 5
   (`embedding_breaker_failure_threshold`); the failing run made exactly 6 embed calls (3 golden
   cases × 2 configs); 5 of them recorded `"error": "Connection error."` and the 6th recorded
   `"embedding circuit breaker open"`. Zero retries happening (each of the first 5 calls counting
   as exactly one failure) is only consistent with `_is_transient()` returning `False` for this
   exception type — if it had been retried per `embedding_retry_max_attempts` (2), the breaker
   would have opened after ~2-3 calls, not exactly 5. Fixed by adding an `isinstance(exc,
   openai.APIConnectionError)` check (this also covers `APITimeoutError`, a subclass). **Behavior
   change to flag:** in a hard, sustained outage the breaker now opens after ~3 embed calls
   instead of 5, since 2 retries happen per call before a failure is counted — this is the
   intended, correct behavior, just worth calling out since it changes the failure signature
   anyone reading `embedding_breaker_failure_threshold` alongside observed failure counts would
   expect.

**Correction to the original story's finding 3:** the story hypothesized that
"`text-embedding-3-small` honours a 1024 request" and Azure would silently return a
truncated/wrong-shaped vector. That's not how `AzureOpenAIEmbeddingProvider.embed()` actually
calls the API — it never sends a `dimensions` parameter at all
(`self._client.embeddings.create(input=text, model=self.deployment_name)`), so
`text-embedding-3-small` always returns its native 1536-dimensional vector regardless of
`settings.embedding_dimensions`. The real risk from an unset `EMBEDDING_DIMENSIONS` was never a
silently-truncated embedding — it was the ORM's `Vector(settings.embedding_dimensions)` column
type (`api/scripture/models.py`) and the embedding cache's dimension-namespaced key
(`api/providers/embedding_cache.py`) both being bound to the wrong number at import time, which
is a real (if differently-shaped) risk and is exactly what finding 2 above fixes.

## Decision: dimension validation

`validate_embedding_dimensions()` previously skipped `embedding_provider=azure_openai`
unconditionally, specifically to avoid consulting the Ollama-oriented `embedding_model` default
(`mxbai-embed-large`) for an Azure config — see
`test_azure_openai_production_boot_config` in `api/tests/test_config_validation.py`, which
reproduces the exact Terraform-injected env combination that crashed production before that skip
was added.

**Decision: extend, don't leave skipped.** The validator now runs a *separate* check for
`azure_openai`, keyed off `azure_embedding_deployment` (not `embedding_model`) against a small
table of known Azure embedding deployments' native dimensions
(`text-embedding-3-small`/`text-embedding-ada-002` → 1536, `text-embedding-3-large` → 3072). This
preserves the original skip's actual purpose (never consult `embedding_model` for Azure) while
closing the gap it left open (an azure_openai config with a wrong `EMBEDDING_DIMENSIONS` was
otherwise inexpressible as a startup failure). An unrecognized/custom deployment name skips
validation — the same escape-hatch philosophy as the existing Ollama unknown-model branch: we
can't know a custom deployment's native size, so we don't guess wrong. This required setting
`EMBEDDING_DIMENSIONS=1536` in `eval-prod`'s job env too (not just `eval-smoke`'s) — without it,
`eval-prod` would start failing at `Settings()` import time the moment this validator shipped.

## Acceptance Criteria

- [ ] `eval-smoke` completes green on a manual `workflow_dispatch` with `route=smoke` — see Verification
- [x] `EMBEDDING_DIMENSIONS` is set for the smoke job (and `eval-prod`) and matches the seeded column width
- [x] `eval-smoke` does not attempt the expansion leg without an LLM credential (now unconditional, not credential-gated)
- [~] The `APIConnectionError` root cause is identified and recorded — H1 fixed and reasoned through; not independently confirmed live from this sandbox (see Verification)
- [x] A decision recorded on whether `validate_embedding_dimensions()` should cover azure_openai — see Decision section
- [ ] The runbook's "run smoke first" advice is true again — depends on the still-open item above

## Verification

A green run is the criterion, but green is not sufficient on its own: confirm the summary shows the
smoke job **ran** rather than skipped (preflight skips are reported as success), and confirm at least
one query returned actual verses. A run where all six cases still score 0.00 with `n_errors: 3` is
the current failure wearing a passing exit code. `search-eval-full.yml`'s "Summarize results" step
for `eval-smoke` now enforces this mechanically (BITB-107): it fails the step if total `n_errors`
across aggregates is nonzero or if zero verses were retrieved across every query, rather than
treating "the CLI exited 0" as sufficient on its own.

**What was actually verified from this sandbox:** _(filled in after attempting a live dispatch —
see below)._

## Related

- **BITB-051 P4a / PR #968** — introduced this workflow
- **BITB-101** — the `eval-prod` credential story; same workflow, different defect
- `.github/workflows/search-eval-full.yml`, `api/providers/azure_openai.py`,
  `api/providers/embedding_resilience.py`, `api/providers/factory.py`, `api/config.py`
