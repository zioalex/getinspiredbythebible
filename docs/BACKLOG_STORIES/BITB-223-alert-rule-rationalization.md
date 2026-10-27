# BITB-223: Alert-Rule Rationalization — Actionability Over Inventory

**Status:** 🚧 In Progress
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

## Classification matrix (FINALIZED — every one of the 32 rules)

Each rule gets a one-line "what would I do at 3am" answer, then the verdict.
Verdict legend: **keep** (unchanged), **demote** (slower cadence),
**recalibrate** (same cadence, breach gating added), **remove**,
**defer** (owned by another story).

### Scheduled-query rules (20 → 16 after this PR)

| Rule | Sev | Fires/30d | Verdict | 3am answer |
|------|-----|-----------|---------|-----------|
| `content_safety_fallback_rate` | 2 | **99** | **Recalibrate** (PT5M eval kept) | "Check which safety provider is down and why — but only if it's been degrading for half an hour, not on every blip." Falling back occasionally is designed behavior (BITB-061); implemented: `window_duration` PT5M + `failing_periods` **6 of 6** (30-minute sustained fallback) — a blip no longer pages, a persistently degraded ML safety net still does. |
| `backend_5xx_rate` | 1 | **42** | **Recalibrate** (PT5M eval kept) | "Is the backend really down for users, or is this the deploy swapping revisions?" Deploy blips (BITB-067 gap #5) had no action and caused most of the 42 pages. Implemented: query `ago(5m)`/`bin(timestamp, 5m)` at `>=3` 5xx per bin + `failing_periods` **3 of 3** (15-minute sustained 5xx rate) — a real continuous outage (e.g. the 2026-07-05 `_IncludedRouter` class) still pages within ~15 min; a seconds-long deploy blip does not. Sustained-window gating preferred over time-of-day suppression because deploy windows vary. |
| `backend_asgi_exceptions` | 1 | 10 | **Keep PT5M** | "A crash above the app — restart/roll back now." The proven catch-all (2026-07-05 `_IncludedRouter` outage, BITB-064/065). |
| `scripture_search_latency_p95` | 2 | 9 | **Keep PT5M** | "Investigate DB load/saturation now (check db-cpu-high)." Protects the BITB-062 search-latency work. |
| `backend_probe_failures` | 2 | 3 | **Defer to BITB-224** | "Undecidable — its input (availability web tests) is disabled." Left unchanged; BITB-224 decides re-enable-tests vs retire-rule. |
| `scripture_fetch_latency_p95` | 3 | 3 | **Demote PT15M** | "Look at the slow queries tomorrow — it's a trend, not an outage." Window widened to PT15M, single p95 bin over `ago(15m)`. |
| `backend_errors` | 2 | 2 | **Keep PT5M** | "Read the category/sample/RequestIds and fix the handler now." |
| `scripture_pipeline_errors` | 2 | 2 | **Keep PT5M** | "A fail-open path is silently degrading answers — find it now." |
| `scripture_grounding_errors` | 2 | 2 | **Keep PT5M** | "Same as above for the grounding/resolution path." |
| `chat_ttft_p95` | 3 | 0 | **Demote PT1H** (was PT15M) | "Nothing at 3am — gross latency/outage is caught by the synthetic-chat probe (30s timeouts); this is provider-quality drift for next week." Window PT1H kept; `evaluation_frequency` PT1H; 2-of-3 sustained gate kept. |
| `chat_verseless_responses` | 2 | 0 | **Demote PT1H** | "Check the retrieval path tomorrow — quality drift, and the search path has dedicated PT5M rules." Window PT1H, 15-min bins, `total > 10`/bin, `failing_periods` **2 of 4** (≥30 min of verseless serving). |
| `verse_grounding_paraphrase_brackets` | 3 | 0 | **Demote P1D** (daily) | "Nothing — cosmetic nested-parens trend data (BITB-053), dormant until paraphrase mode is 'append'." Window P1D (24h; `PT24H` is not in the provider's allowed-value list for `window_duration` — `P1D` is the closest valid granularity), 1h bins, `total > 20`/bin (same 5-per-15-min rate); clustering gate is "≥2 hot bins per day" (`threshold = 1`) with 1-of-1 `failing_periods` — the original 2-of-3 gate made the look-back 72h and Azure rejects >48h (see *Post-merge apply fix*). |
| `embedding_fallback_rate` | 2 | 0 | **Demote PT15M** | "Diagnose the embedding breaker tomorrow — its user-facing symptom is covered by the GH verse-search probe." Window PT15M, 5-min bins. |
| `backend_client_rejection_spike` | 3 | 0 | **Demote PT15M** | "If it's a real bot attack I'd act — but on a 15-minute cadence; routine Turnstile/auth noise never needs a page." Insurance for abuse patterns (security-adjacent): demoted, not removed; `>=30` rejections per 15 min. |
| `frontend_client_errors` | 2 | 0 | **Demote PT1H** | "Debug the JS errors in the morning — never an emergency; the BITB-066 reporter retains the data for diagnosis." Window PT1H, 15-min bins, `total > 20`/bin, `failing_periods` **2 of 4**. |
| `rate_limiter_fail_closed` | 1 | 0 | **Keep PT5M — insurance** | "Chat is being actively rejected — restore Postgres connectivity now." Security fail-closed control (BITB-061); never-firing is the goal. Untouchable. |
| `backend_unhandled_exceptions` | 2 | 0 | **Remove** | Redundancy justification: a 4th pager for the same event — `backend_asgi_exceptions` + `backend_errors` + `backend_5xx_rate` all fired on the same real incidents; the App-Insights-table variant added no distinct signal (and the ASGI-middleware crash class never even reaches the exceptions table). Resource block deleted; destruction on next apply intended. |
| `llama_guard_primary_failure_rate` | 3 | 0 | **Remove** | Redundancy justification: `content_safety_fallback_rate` is the aggregate fallback signal (recalibrated to 30-min sustained), and the GH content-safety probe asserts both classification directions end-to-end every 5 minutes; the primary-stuck-secondary-recovers state had no distinct 3am action. |
| `backend_error_rate_other` | 3 | 0 | **Remove** | Redundancy justification: "other" 4xx are client faults with no server-side action; actionable server-side ERRORs are the categories `backend_errors` already pages on; client-rejection abuse stays covered by `backend_client_rejection_spike`. |
| `scripture_fetch_errors` | 2 | 0 | **Remove** | Redundancy justification: same chat scripture pipeline as `scripture_pipeline_errors` (kept PT5M) — 2 firings there vs 0 here in the 30-day evidence window; the metric rule added a second pager for the same failures. |

### Metric alerts (12 rules, 0.85 CHF/mo total) — classified, out of scope for changes

Pennies; not worth the review churn. Exception: `db_storage` at 85% provably
cannot catch the storage ratchet — that is BITB-232.

| Rule | Sev | 3am answer / classification |
|------|-----|------------------------------|
| `backend_availability` | 1 | "Region can't reach /health/ready — check the app now." Web-test availability signal; keep. Out of scope. |
| `backend_preflight_availability` | 1 | "Browser-only preflight failing — the _IncludedRouter class; act now." Keep. Out of scope. |
| `backend_restarts` | 2 | "Check OOM/crash-loop vs deploy." Keep. Out of scope. |
| `db_cpu` | 2 | "DB at the saturation knee — investigate/tier up." Keep. Out of scope. |
| `db_memory` | 3 | "Cache-thrash/OOM risk — watch it." Keep. Out of scope. |
| `db_storage` | 2 | "Storage climbing — but the 85% threshold provably can't catch the ratchet; retune is BITB-232." Keep (as-is) here; BITB-232 owns it. |
| `db_connections_failed` | 2 | "DB rejecting connections — hard breach; act now." Keep. Out of scope. |
| `backend_cpu_high` | 2 | "Backend compute saturated — scale up." Keep. Out of scope. |
| `backend_memory_high` | 2 | "OOM risk — raise memory or find the leak." Keep. Out of scope. |
| `backend_replicas_at_max` | 2 | "At capacity ceiling — raise max replicas." Keep. Out of scope. |
| `frontend_cpu_high` | 3 | "Informational; stateless SSR rarely the constraint." Keep. Out of scope. |
| `frontend_memory_high` | 3 | "Informational symmetry." Keep. Out of scope. |

### Decisions rolled up

- **4 removals:** `backend_unhandled_exceptions`, `llama_guard_primary_failure_rate`,
  `backend_error_rate_other`, `scripture_fetch_errors` — each redundant with a kept
  rule or probe covering the same event (justifications in the matrix above and in
  the `deployment/monitoring.tf` header/removal comments).
- **7 demotions:** `chat_ttft_p95` → PT1H, `chat_verseless_responses` → PT1H,
  `verse_grounding_paraphrase_brackets` → P1D, `embedding_fallback_rate` → PT15M,
  `backend_client_rejection_spike` → PT15M, `frontend_client_errors` → PT1H,
  `scripture_fetch_latency_p95` → PT15M. For each, the query window was widened /
  re-binned to match the new cadence with thresholds kept sensible for the wider
  window (documented per-rule above).
- **2 recalibrations** (PT5M cadence kept, sustained-window gating added):
  `content_safety_fallback_rate` → 6-of-6 × PT5M (30-min sustained);
  `backend_5xx_rate` → 3-of-3 × PT5M at ≥3/bin (15-min sustained). Both use the
  `failing_periods` block of `azurerm_monitor_scheduled_query_rules_alert_v2` —
  no time-of-day suppression (deploy windows vary).
- **Exact PT5M survivors** (evaluation every 5 minutes, unchanged): `rate_limiter_fail_closed`,
  `backend_asgi_exceptions`, `backend_errors`, `scripture_pipeline_errors`,
  `scripture_grounding_errors`, `scripture_search_latency_p95` — plus the two
  recalibrated rules (`content_safety_fallback_rate`, `backend_5xx_rate`), which keep
  their PT5M evaluation but now require sustained breaches, and `backend_probe_failures`,
  left untouched pending BITB-224. Every PT5M rule has a concrete 3am action.
- **`backend_probe_failures`: deferred to BITB-224** — its input (the availability web
  tests) is disabled per the evidence; re-enable the tests or retire the rule, decided
  there, not here.

## Post-merge apply fix (2026-10-27)

The first `terraform apply` after #1218 merged failed on
`verse_grounding_paraphrase_brackets` with `400 InvalidRequestContent: Query look back
cannot exceed 48 hours`. Azure computes look-back as `window_duration ×
number_of_evaluation_periods`; the P1D window with the kept 2-of-3 gate is 72h.
`terraform validate`/`plan` don't check this, so CI was green. Fix: 1-of-1
`failing_periods`, with the clustering moved into the threshold (alert only when at
least 2 hourly bins in the day exceed 20). `api/tests/test_monitoring_alert_lookback.py`
now asserts every scheduled-query rule in `deployment/monitoring.tf` stays within 48h.

## Estimated savings

20 log rules → **4 removed, 7 demoted** (PT1H/daily/PT15M tiers bill a fraction
of PT5M) plus 2 recalibrated in place. Derived from the meter baseline
(20.04 CHF/mo / 20 rules ≈ 1.00 CHF per PT5M rule): expected **~8-12 CHF/mo
(~40-60% of the line)**. Verify post-change against the same Cost Management
query (acceptance criterion).

## Acceptance Criteria

- [x] The classification matrix above is finalized per-rule with a one-line
      "what would I do at 3am" answer for every one of the 32 rules (20
      scheduled-query + 12 metric-alert) — committed in the story file
- [x] Removed rules: each has a written redundancy/insurance justification
      (safety controls are never removed — `rate_limiter_fail_closed` stays)
- [x] Demoted rules: `evaluation_frequency` updated in `deployment/monitoring.tf`;
      no PT5M rule remains that lacks a 3am action
- [x] `content_safety_fallback_rate` + `backend_5xx_rate` recalibrated with
      sustained-window logic (`failing_periods` 6-of-6 and 3-of-3 over PT5M
      windows respectively — see matrix) so blips don't page; real incidents
      still do. **Owner-run verification below.**
- [ ] A 30-day post-merge firing-history pull shows the reduction; the
      scheduled-query meter line shows the expected drop — **owner-run step**
      (requires 30 days of post-merge production data + the Cost Management
      query; cannot be ticked from the repo)
- [ ] Telegram test: one forced alert per kept rule path still pages (action
      group wiring untouched) — **owner-run step** (requires production access
      to force and observe an alert)

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
