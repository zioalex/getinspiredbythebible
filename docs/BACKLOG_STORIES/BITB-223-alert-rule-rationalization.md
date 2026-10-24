# BITB-223: Alert-Rule Rationalization — Actionability Over Inventory

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (one PR: classification matrix + Terraform changes + threshold retunes)
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 follow-up — accepted lever, Part A)
**Evidence base:** `cost-evidence-20261023-121757` (30-day firing history + 3-month meter data)

## User Story

**As** the person paying ~1 CHF per log-alert rule per month for rules that mostly
never fire — and who receives ~143 alert pages per month from the noisy ones —
**I want** every alert rule classified by *actionability* (what would I actually do
when it fires?) and then kept, slowed, or removed accordingly, **so that** the
20.04 CHF/month scheduled-query-rule line item drops ~40-60% and every page that
reaches Telegram is one I would act on.

## Why now — the evidence

- Scheduled query rules are the **#2 cost driver of the entire bill**: 60.11 CHF
  over 3 months = **20.04 CHF/mo, 21.6% of spend** (`01-cost-by-resource-type.json`).
- In 30 days, **9 of 32 rules fired**; **23 never fired** (`07-alert-firing-history.json`).
- The two noisiest rules are in alert-fatigue territory:
  - `content_safety_fallback_rate` (Sev2, PT5M): **99 firings/30d**
  - `backend_5xx_rate` (Sev1, PT5M): **42 firings/30d**
  A page nobody acts on 99 times is noise; noise trains the owner to ignore
  Telegram, which defeats the entire alerting stack (the BITB-064 lesson).
- The repo runs **two parallel alerting stacks into the same Telegram channel**:
  these 32 Azure rules *and* `prod-monitor.yml` (7 GitHub probes every 5 minutes:
  health, synthetic-chat, content-safety, cross-origin, verse-search, frontend,
  log-scan). A rule that duplicates a probe's coverage is a second pager for the
  same event.

## The actionability criterion (owner-set, 2026-10-23)

> "Some alerts can be removed or run daily if they are not really actionable."

For each rule, answer: **if this fired at 3am, what would I do?**

- A concrete action exists (investigate, roll back, restart) → keep at a frequency
  matching the urgency of that action.
- The action is "look at it next week" (quality drift) → **PT1H or daily**, not PT5M.
- No action exists, or another rule/probe pages the same event → **remove**.
- Safety/fail-closed controls → **insurance: keep**, even never-fired.

## Classification matrix (from evidence; the PR finalizes it)

### Fired in 30d — recalibrate, don't remove

| Rule | Sev | Fires/30d | Verdict | Rationale |
|------|-----|-----------|---------|-----------|
| `content_safety_fallback_rate` | 2 | **99** | **Recalibrate** | Fires on blips; needs sustained-window threshold (e.g. 15-30 min above rate) so it pages on real degradation, not hiccups. Falling back occasionally is the *designed* behavior (BITB-061). |
| `backend_5xx_rate` | 1 | **42** | **Recalibrate + deploy-window suppression** | Deploy-time app replacement causes brief 5xx blips (BITB-067 gap #5 documented this class). Longer aggregation window; suppress during the azure-deploy window or gate on sustained 5xx. |
| `backend_asgi_exceptions` | 1 | 10 | Keep PT5M | The proven catch-all signal (2026-07-05 `_IncludedRouter` outage, BITB-064/065). |
| `scripture_search_latency_p95` | 2 | 9 | Keep PT5M | Protects the BITB-062 search-latency work; real 3am action (DB investigation). |
| `backend_probe_failures` | 2 | 3 | **Decide with BITB-224** | Its input is the availability web tests — which the evidence shows are **disabled**. If tests stay off, this rule is dead; re-enable tests or retire the rule. |
| `scripture_fetch_latency_p95` | 3 | 3 | PT15M | Latency quality trend, not an emergency. |
| `backend_errors` | 2 | 2 | Keep PT5M | Actionable error-log signal. |
| `scripture_pipeline_errors` | 2 | 2 | Keep PT5M | Actionable; subsumes `scripture_fetch_errors` (which never fired). |
| `scripture_grounding_errors` | 2 | 2 | Keep PT5M | Actionable grounding-path signal. |

### Never fired in 30d — remove or demote

| Rule | Sev | Verdict | Rationale |
|------|-----|---------|-----------|
| `backend_unhandled_exceptions` | 2 | **Remove** | Redundant: `backend_asgi_exceptions` + `backend_errors` + `backend_5xx_rate` all fired on the same real incidents; the App-Insights-table variant adds a 4th pager for the same event. |
| `llama_guard_primary_failure_rate` | 3 | **Remove** | Redundant: `content_safety_fallback_rate` is the aggregate fallback signal, and the GH content-safety probe asserts both directions end-to-end every 5 min. |
| `backend_error_rate_other` | 3 | **Remove** | "Other" 4xx are client faults; `backend_errors` covers actionable server-side error lines; client-rejection abuse is covered by the next rule. |
| `scripture_fetch_errors` | 2 | **Remove** | Redundant with `scripture_pipeline_errors` (same pipeline, 2 firings there vs 0 here). |
| `chat_ttft_p95` | 3 | **PT1H** | Quality metric, no 3am action; gross latency/outage is caught by the synthetic-chat probe (30 s timeouts). |
| `chat_verseless_responses` | 2 | **PT1H** | Quality drift, next-week action. |
| `verse_grounding_paraphrase_brackets` | 3 | **Daily** | Niche quality regression counter (BITB-053); trend data, not a page. |
| `embedding_fallback_rate` | 2 | **PT15M** | Real signal but symptom-covered by the verse-search probe; demote, keep for diagnosis. |
| `backend_client_rejection_spike` | 3 | **PT15M** | Abuse-pattern insurance (security-adjacent) — demote, don't remove. |
| `frontend_client_errors` | 2 | **PT1H** | Actionable (debugging JS errors) but never an emergency; BITB-066 reporter also feeds `client.errors_total`. |
| `rate_limiter_fail_closed` | 1 | **Keep PT5M — insurance** | Security fail-closed control (BITB-061). Never firing is exactly what we want; removal is on no one's authority. |

### Metric alerts (12 rules, 0.85 CHF/mo total) — out of this story's scope

Pennies; not worth the review churn. Exception: `db_storage` at 85% provably
cannot catch the storage ratchet — that is BITB-232.

## Estimated savings

20 log rules → **~6 removed, ~6 demoted** (PT1H/daily tiers bill a fraction of
PT5M). Derived from the meter baseline (20.04 CHF/mo / 20 rules ≈ 1.00 CHF per
PT5M rule): expected **~8-12 CHF/mo (~40-60% of the line)**. Verify post-change
against the same Cost Management query (acceptance criterion).

## Acceptance Criteria

- [ ] The classification matrix above is finalized per-rule with a one-line
      "what would I do at 3am" answer for every one of the 32 rules — committed
      in the story file
- [ ] Removed rules: each has a written redundancy/insurance justification
      (safety controls are never removed — `rate_limiter_fail_closed` stays)
- [ ] Demoted rules: `evaluation_frequency` updated in `deployment/monitoring.tf`;
      no PT5M rule remains that lacks a 3am action
- [ ] `content_safety_fallback_rate` + `backend_5xx_rate` recalibrated so
      sustained-window logic (or suppression) reduces their 30-day fire counts
      by ≥80% without losing real incidents
- [ ] A 30-day post-merge firing-history pull shows the reduction; the
      scheduled-query meter line shows the expected drop
- [ ] Telegram test: one forced alert per kept rule path still pages (action
      group wiring untouched)

## Out of Scope

- Metric-alert rules (pennies; only `db_storage` needs work — BITB-232)
- The disabled availability web tests (BITB-224)
- `daily_quota_gb`, sampling (BITB-225/215)

## Related

- BITB-150 — parent analysis; meter baseline 20.04 CHF/mo
- BITB-064/065/067 — why `backend_asgi_exceptions` and the catch-alls stay
- BITB-061 — why `rate_limiter_fail_closed` is untouchable insurance
- BITB-053 — origin of `verse_grounding_paraphrase_brackets`
- BITB-224 — decides `backend_probe_failures`' fate
