# BITB-070: Re-evaluate `hybrid` Content-Safety Mode (Two-Vendor Defense-in-Depth)

**Status:** 🎯 Todo
**Priority:** P3 (Low) — `ml_only` is currently reliable and safe; this is a deliberate
future upgrade, not a gap.
**Size:** M (1-2 days, mostly infra + a small code change)
**Created:** 2026-07-17

## User Story

As a maintainer, I want a documented, ready-to-execute plan for switching content safety to
`hybrid` mode, so that when the team decides two-vendor defense-in-depth is worth the added
infra/cost, it's a scoped task instead of a fresh investigation.

## Context

While testing PR #840 (BITB-061 fail-closed abuse controls) locally, the question came up:
should `content_safety_mode` default to `hybrid` instead of `ml_only`? Investigating surfaced
that this is not a config-only change — there's a real infrastructure gap and a code-level
constraint worth documenting before anyone attempts it.

### What `hybrid` actually adds over `ml_only`

Both modes share Stage 1 (fast keyword filter) and now (post-PR #840 + follow-ups) both
degrade safely to the local keyword filter if their ML stage fails — that part is identical.
The difference is in Stage 2 (and Stage 3), per `api/utils/content_safety.py`:

| | Stage 2 | Stage 3 |
|---|---|---|
| `ml_only` (current default) | Llama Guard — primary model (`meta-llama/llama-guard-4-12b`), falls back to a secondary model (`openai/gpt-oss-safeguard-20b`) if the primary fails, falls back to the keyword filter only if *both* fail (see BITB-061 follow-up commits) | — (explicitly skipped; `ml_only` returns immediately after Llama Guard) |
| `hybrid` | OpenAI Moderation API | **Azure Content Safety**, chained after — both must independently agree content is clean before it's allowed |

`ml_only` gets one vendor's opinion (Llama Guard — now internally resilient via the
primary/secondary retry, but still conceptually one classifier's judgment). `hybrid` chains
two genuinely independent vendors (OpenAI + Microsoft Azure) — different training data,
different blind spots, both must agree. That's real defense-in-depth, not just retry
resilience within one vendor.

Given `ml_only`'s reliability after the BITB-061 follow-up work (a 2026-07-17 100-sample live
benchmark measured 0 total failures — the secondary model recovered every primary failure),
the marginal safety benefit of adding a second, independent vendor is real but not urgent: it
protects against Llama Guard *and* the secondary both having a shared blind spot (e.g. a
category neither model's training data covers well), which is a lower-probability, harder-to-
detect failure mode than the "provider unavailable" class BITB-061 fixed.

### Blockers found (2026-07-17)

1. **No `OPENAI_API_KEY` infrastructure exists anywhere.** Checked
   `deployment/variables.tf`, `deployment/main.tf`, `deployment/terraform.tfvars`, and
   `.github/workflows/azure-deploy.yml` — there is no Terraform variable, no container env var
   wiring, and no GitHub Actions secret reference for a plain OpenAI API key. The only
   OpenAI-related credential that exists is `AZURE_OPENAI_API_KEY`
   (`deployment/main.tf:152`), which is exclusively for the Azure OpenAI **embedding**
   provider — unrelated to content moderation. Flipping `content_safety_mode` to `hybrid`
   today, with no other changes, means `_get_openai_moderation_provider()`
   (`api/utils/content_safety.py`) always returns `None` (no key), so **every message would
   silently fall back to the local keyword filter, permanently** — the opposite of an upgrade.
2. **Azure Content Safety has zero infrastructure either** — no `AZURE_CONTENT_SAFETY_ENDPOINT`
   / `AZURE_CONTENT_SAFETY_KEY` Terraform variables or env wiring. (Distinct from Azure
   *OpenAI*, which is already wired for embeddings.)
3. **Code-level constraint:** Azure Content Safety can currently only run as `hybrid`'s Stage 3
   — it's gated by `if content_safety_mode == "hybrid"` in
   `ContentSafetyService.check()`. There is no existing path to run "Llama Guard (ml_only) +
   Azure" without OpenAI Moderation also being Stage 2. Getting Azure-as-extra-layer without a
   new OpenAI key would require adding a new mode value (e.g. `ml_only_plus_azure`) and a small
   code change, not just infra.

## Options When This Is Picked Up

1. **Full hybrid**: wire up both `OPENAI_API_KEY` (new Terraform variable + `main.tf` env var +
   GitHub secret, mirroring the existing `openrouter_api_key` pattern in
   `deployment/variables.tf:234-239`) and Azure Content Safety credentials, then flip the
   default. Gets genuine two-vendor defense-in-depth.
2. **New mode, no OpenAI key**: add a mode (e.g. `ml_only_plus_azure`) that runs Llama Guard
   (Stage 2, as today) then Azure Content Safety (Stage 3) without OpenAI Moderation in the
   middle — smaller infra lift (just Azure credentials), smaller code change in
   `ContentSafetyService.check()`.
3. **Stay on `ml_only`**: if Llama Guard's post-BITB-061 reliability holds up in production
   telemetry (watch `llama_guard.primary_result_total` / `llama_guard.secondary_model_total` —
   see BITB-061 follow-up observability work), the case for a second vendor may not be worth
   the added latency/cost/infra.

## Acceptance Criteria (once picked up)

- [ ] Decision made and documented: option 1, 2, or 3 above
- [ ] If 1 or 2: new API key(s) provisioned, Terraform variables + `main.tf` env wiring +
      GitHub secret added, following the `openrouter_api_key` pattern
- [ ] If 2: `ContentSafetyService.check()` updated to support the new mode
- [ ] Tests added for the new mode/path
- [ ] `content_safety_mode` default changed only after the above is verified working in a
      real deploy (not just unit tests) — see the local-prod end-to-end testing approach used
      for BITB-061 (`make docker-up-local-prod-build` + real HTTP requests against `/api/v1/chat`)
