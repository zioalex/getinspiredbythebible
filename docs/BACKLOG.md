# Product Backlog

Prioritized list of user stories and features for Vox Quieta.

**Last Updated:** 2026-08-21

**Verification Note (2026-04-20):** PR status reconciliation pass completed against GitHub.
Confirmed merged PRs: #68, #171, #182, #191, #193, #194, #195, #196, #197, #208, #225, #226,
\#227. Confirmed closed-unmerged: #309.

---

## Legend

- **Priority:** P0 (Critical/Blocker), P1 (High), P2 (Medium), P3 (Low)
- **Status:** 🎯 Todo, 🚧 In Progress, ✅ Done, ❌ Cancelled
- **Size:** S (< 4 hrs), M (1-2 days), L (3-5 days), XL (1-2 weeks)

---

## P0 - Critical (Ship Now)

### ✅ BITB-022: Fix Remaining Empty Panels in Performance Dashboard

**Status:** ✅ Done (PR #243 merged 2026-03-06)
**Size:** M (4-6 hours)
**Created:** 2026-03-06
**Completed:** 2026-03-06

**As a** site reliability engineer using the Performance Dashboard,
**I want** all dashboard panels to display real data (not "No data"),
**so that** I can monitor application health, detect performance issues, and troubleshoot errors effectively.

**Why P0:** Dashboard is partially broken in production. After BITB-021 (metrics instrumentation) and
source_id fix were deployed, most panels still show "No data". Only 3 panels work (Request Rate Over
Time, Tokens per Second Trend, Container CPU & Memory). This indicates a KQL query syntax issue,
metric name mismatch, or data availability problem that needs immediate investigation and fix.

**Acceptance Criteria:**

- [x] Root cause identified: 3 KQL issues — empty-row tile crash, invalid `countif` compound
  predicate, restricted `any()` aggregation
- [x] Fix implemented: workbook queries updated (PR #243)
- [x] All Overview panels fixed (Request Volume, Error Rate, Response Time, Availability)
- [x] All LLM Performance panels fixed (tiles use union/summarize pattern to guarantee rows)
- [x] All Database Performance panels fixed (Search Duration, Query Duration, Slow Queries)
- [x] All Error Analysis panels fixed (Exception Summary uses `min()` instead of `any()`)
- [x] All Infrastructure panels show data (CPU/Memory, Container Restarts)

**Also fixed (migration pipeline, PR #244, #245, #247):**

- [x] `002_add_hnsw_indexes.sql` — added `IF NOT EXISTS` to `CREATE INDEX` statements
- [x] `003_tune_postgresql_config.sql` — commented out reference-only verification queries
- [x] `run_migrations.py` — handles reference-only SQL files with no executable statements

**Full Story:** `docs/BACKLOG_STORIES/BITB-022-fix-dashboard-empty-panels.md`

---

### ✅ BITB-023: Session Lifetime Limit with Friendly "Take a Break" Message

**Status:** ✅ Done (PR #250 merged 2026-03-06)
**Size:** M (4-6 hours)
**Created:** 2026-03-06
**Completed:** 2026-03-06

**As a** user who has been chatting for a while,
**I want** to be gently reminded to take a break after 10 messages,
**so that** I don't spend too much time on the app and can go enjoy God's creation outside.

**Why P0:** Current rate limiting (10 requests/minute) silently blocks users with a generic
"connection error". Users don't understand why they're blocked and there's no encouragement
to take a break. This creates a poor user experience and frustration.

**Acceptance Criteria:**

- [x] Session lifetime limit set to 10 messages (not per-minute, lifetime per session)
- [x] When limit is hit, user sees friendly message: "You've had 10 messages in this session!
  Why not take a break and enjoy God's creation outside? 🌳"
- [x] "Start New Session" button appears when limit is reached
- [x] Backend returns HTTP 429 with distinguishable error type (`session_lifetime_limit`)
- [x] Frontend handles 429 specifically and shows the friendly message
- [x] Rate limit is per-session (browser tab), not per-user
- [x] New session resets the counter (user can continue chatting)

**Implementation Notes:**

- Backend: Changed `rate_limit_session_max_requests` default from 100 to 10 in `api/config.py`
- Backend: Added friendly error message in `api/utils/security.py` for session lifetime limit
- Terraform: Added `rate_limit_session_max_requests` variable in `deployment/variables.tf`
- Frontend: Added `SessionLimitError` class in `frontend/src/lib/api.ts`
- Frontend: Added "Start New Session" button in `frontend/src/app/[locale]/page.tsx`
- i18n: Added `startNewSession` translation to all 7 locales (en, es, de, fr, it, pt, ar)

---

### ✅ BITB-020: Replace Keyword Filter with OpenAI Free Moderation API

**Status:** ✅ Done (PR #229, #233, #236, #237 merged 2026-03-06)
**Size:** M (5-6 hours)
**Created:** 2026-03-04
**Completed:** 2026-03-06

**As a** user asking about Bible stories involving violence,
**I want** the content safety filter to understand biblical context vs. harmful intent,
**so that** "David killed Goliath" is never blocked, but "I want to bomb the school" always is.

**Why P0:** Content safety (BITB-017) is deployed but cannot be enabled due to false
positives on Bible queries. This unblocks it.

**Acceptance Criteria (summary — full story in `docs/BACKLOG_STORIES/BITB-020-openai-moderation-content-safety.md`):**

- [x] ~~OpenAI Moderation API (`omni-moderation-latest`, free) replaces broad violence keywords~~
  → Replaced with Llama Guard 3 via OpenRouter (PR #233)
- [x] Stage 1 retains only directed-harm + hate-speech patterns (unambiguous, never biblical)
- [x] False positive tests all pass: "David killed Goliath" → HTTP 200
- [x] True positive tests all pass: "I want to build a bomb" → HTTP 400
- [x] Fallback to existing keyword filter if API unavailable
- [x] `CONTENT_SAFETY_ENABLED=true` safely enabled in production after merge

**Implementation Notes:**

- PR #229: Initial OpenAI Moderation implementation (superseded)
- PR #233: Replaced with Llama Guard 3 via OpenRouter (BITB-021)
- PR #236: Fixed OpenRouter fallback to use native `models` array + throughput-based routing
- PR #237: Fixed `keyword_only` mode to truly skip ML, `ml_only` is now default
- PR #238: Added `CONTENT_SAFETY_ENABLED` and `CONTENT_SAFETY_MODE` to Terraform config

**Tech Constraints:**

- Uses existing `openai_api_key` or `openrouter_api_key` (no new key needed)
- New provider: `api/providers/openai_moderation.py`
- Fits existing `keyword_only / hybrid / ml_only` mode config
- Must not break existing 1,033 tests

**Dependencies:** BITB-017 (PR #208 merged ✅)

**Full Story:** `docs/BACKLOG_STORIES/BITB-020-openai-moderation-content-safety.md`

---

### ✅ BITB-001: Fix Turnstile 403 Errors on Example Sentences

**Status:** ✅ Done (PR #171 merged, deployed to production 2026-02-23 12:26 UTC)
**Size:** S
**Completed:** 2026-02-23

**As a** new user visiting the app for the first time,
**I want** to click example sentences and get immediate responses,
**so that** I can quickly understand what the app does without frustration.

**Acceptance Criteria:**

- [x] Example sentence buttons are disabled until Turnstile is ready
- [x] Users see "Preparing secure connection..." message while waiting
- [x] No 403 errors when clicking examples after page load
- [x] Unit tests verify buttons are disabled when `turnstileEnabled && !turnstileReady`
- [x] E2E tests verify suggested prompts are present and clickable

**Tech Constraints:**

- Must work with existing Cloudflare Turnstile integration
- Frontend-only fix (no backend changes needed)

**Out of Scope:**

- Changing Turnstile provider or configuration
- Adding retry logic for failed Turnstile challenges

**PR:** #171 (`fix/turnstile-ready-check`) - Merged
**Tracking Doc:** `docs/DONE/PR171-turnstile-ready-fix.md`

---

## P1 - High Priority (Next Sprint)

> **Search-relevance epic (BITB-018 → 043/044):** Phase-1 retrieval improvements
> (query expansion, hybrid search, topic boosting) are **built but dark** — merged in
> Feb 2026 yet shipped behind feature flags that default OFF, so production search is
> still pure semantic. The highest-ROI next step is validation + rollout (BITB-043), not
> new code. See `docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md` and
> `docs/TURBOVEC_EVALUATION.md` (turbovec evaluated and rejected — relevance, not infra,
> is the lever).

### ✅ BITB-071: Verse Link Click Sends NaN Chapter for Non-ASCII (Devanagari/Eastern Arabic) Digits

**Status:** ✅ Done (PR #893 merged 2026-07-17)
**Size:** S (< 4 hrs)
**Created:** 2026-07-17
**Completed:** 2026-07-17

**As** a Hindi (or Arabic) user, **I want** clicking a cited verse reference to open the
correct chapter, **so that** I can read the scripture the assistant quoted instead of
hitting a 422 (`GET /scripture/chapter/यूहन्ना/NaN`).

**Root cause:** frontend `linkifyVerses.ts` / `ChatMessage.tsx` parsed non-ASCII
(Devanagari, Eastern Arabic) chapter/verse digits with plain `parseInt` instead of
normalizing them first, unlike `verseExtraction.ts` which already had this handled.
Investigation also found the same missing-non-ASCII-digit-support gap in Android's
verse regex (`ChatMessageItem.kt`, plain `\d` = ASCII-only in Java), a distinct failure
mode (no link at all) from the same root cause — the "three parsers diverge subtly"
trap `AGENTS.md` calls out. Backend unaffected (Python's `re`/`int()` are Unicode-digit
aware natively) and already had test coverage for this exact scenario.

Full story: `docs/DONE/BITB-071-verse-link-non-ascii-digit-parsing.md`

---

### ✅ BITB-064: Catch Browser-Only Outages — CORS-Preflight Smoke Test + Instrumented-Request Alerting

**Status:** ✅ Done — scripted cross-origin probe, Azure preflight web test, runbook, and full browser smoke test all delivered
**Size:** M (one new synthetic probe + Telegram wiring; optional Azure availability test)
**Created:** 2026-07-05

**As** the operator, **I want** a synthetic monitor that hits the API the way a browser does (a
cross-origin CORS preflight) and the production request path exercised with OpenTelemetry
instrumentation on, **so that** a browser-only outage pages me on Telegram in minutes instead of
waiting for a user report.

**Why P1:** A total browser-facing chat outage shipped to production (FastAPI 0.137's `_IncludedRouter`
crashed the pinned OpenTelemetry instrumentation, returning HTTP 500 on every `OPTIONS /api/v1/*`
preflight) and **no monitor, Azure alert, or Telegram notification fired**. The break was browser-only:
`OPTIONS` preflight → 500, but direct `GET`/`POST` → 200. Every safety net (Azure `/health/ready` test,
the `synthetic-chat` and `verse-search` probes) sends non-browser requests, so all stayed green — the
same reason native Android kept working.

**Acceptance Criteria (summary — full story has detail):**

- [x] New CORS-preflight synthetic probe (`OPTIONS /api/v1/chat/stream` with `Origin` +
      `Access-Control-Request-*` headers) asserts 2xx/204 and the `Access-Control-Allow-*` response headers,
      plus a cross-origin POST asserting a streamed answer (`scripts/monitor/synthetic_preflight.py`)
- [x] Wired into `prod-monitor.yml` as the `cross-origin-smoke` job on the 5-min schedule via `notify-telegram`
- [x] Azure `backend_preflight` availability web test (OPTIONS + CORS headers) + alert → always-on channel
- [x] Troubleshooting runbook note: "browser 500 but curl/app fine" ⇒ CORS-preflight / OTel path
- [x] Full production **browser** smoke test (`prod-chat-smoke.spec.ts` + hourly `prod-browser-smoke.yml`),
      Turnstile passed via a separate injected-at-test-time `smoke_probe_secret` (never in the bundle)

**Full Story:** `docs/BACKLOG_STORIES/BITB-064-browser-preflight-smoke-and-alerting.md`

---

### ✅ BITB-065: Backend Catch-All Error Alerting — HTTP 5xx, Unhandled & ASGI-Layer Exceptions

**Status:** ✅ Done (delivered on the PR #824 branch)
**Size:** S (three Terraform scheduled-query alerts)
**Created:** 2026-07-05

**As** the operator, **I want** an alert whenever the backend returns HTTP 5xx or throws an unhandled /
ASGI-layer exception, **so that** a server-side outage pages me regardless of which subsystem broke.

**Why P1:** Of 17 pre-existing alerts, **none** watched backend 5xx or the App Insights
`requests`/`exceptions` tables — the generic 5xx KQL lived only in a passive workbook. The
`_IncludedRouter` 500 fell through because it is not a DB metric, not a custom counter, and (being a
crash *above* the app in the OTel middleware) produced no `| ERROR |` log line. Nuance: that crash
records no `requests` row either (it dies before the span starts), so the reliable signal is the
`uvicorn` "Exception in ASGI application" console line — hence a log-based rule alongside the table ones.

**Acceptance Criteria:**

- [x] `backend_5xx_rate` (App Insights `requests`, Sev 1), `backend_unhandled_exceptions` (App Insights
      `exceptions`, Sev 2), `backend_asgi_exceptions` (console logs "Exception in ASGI application", Sev 1)
- [x] All reuse the `ops_email` action group + `local.alerts_enabled` gating (email + Telegram)

**Full Story:** `docs/BACKLOG_STORIES/BITB-065-backend-catchall-error-alerting.md`

---

### ✅ BITB-066: Frontend Error Observability

**Status:** ✅ Done (delivered on the PR #824 branch, reuse-endpoint approach)
**Size:** M (frontend reporter + backend metric/alert + middleware tweak)
**Created:** 2026-07-05

**As** the operator, **I want** the web frontend to report client-side errors (JS exceptions, unhandled
rejections, API/network failures) and alert on spikes, **so that** browser-only failures are visible
from the client — the way Android already reports via Firebase Crashlytics.

**Why P1:** The web frontend had **no** general client-side error telemetry — the `ErrorBoundary` only
`console.error`d, API failures were swallowed, and the only sink (`/api/v1/client-errors`) was used
solely by Turnstile. A CORS-blocked preflight surfaces as a bare `TypeError` and was reported nowhere.

**Acceptance Criteria (all delivered):**

- [x] `clientErrorReporter.ts` (fire-and-forget, PII-scrubbed, capped/deduped) + global
      `window.onerror`/`unhandledrejection` handlers + `api.ts` failure hook + `ErrorBoundary` + `global-error.tsx`
- [x] `/api/v1/client-errors` hardened (model, cap, rate-limit, flag) + `client.errors_total` metric + spike alert
- [x] `AccessAuditMiddleware` emits `api.preflight_errors_total` on `OPTIONS` 5xx
- [x] Mechanism decision resolved: reuse the existing endpoint (RUM SDK deferred)

**Full Story:** `docs/BACKLOG_STORIES/BITB-066-frontend-error-observability.md`

---

### 🚧 BITB-067: Deploy & Smoke-Monitor Reliability — Gaps From the 2026-07-07 False-Alarm Incident

**Status:** 🚧 In Progress (gaps #1/#2/#3/#4 shipped — #1 in PR #848, #2/#3/#4 in PR #845; #5/#6 open — Terraform/Azure infra work)
**Size:** M (several small, independent hardening items)
**Created:** 2026-07-07

**As** the operator, **I want** deploys and the production smoke monitor to fail **only when the service
is actually broken**, self-diagnose common failure modes, and not create outages as a side effect of
routine changes, **so that** green means healthy and red means real user impact.

**Why P1:** After BITB-064/065/066 shipped, the hourly browser smoke test alerted "production down" for
hours while chat worked fine (it waited on a selector missing from the **undeployed** frontend bundle —
the merge sat in a `waiting` deploy gate). A follow-up deploy then broke origin TLS
(`525 SSL Handshake Failed`) — the same replace→cert-unbind class that BITB-064's new
`smoke_probe_secret` (hashed into the backend replace-trigger) can now provoke.

**Gaps (each independently shippable):**

- [x] Merged monitoring never deploys (stuck approval gate) → false "down"; add deployed-SHA vs `main` drift alert / auto-deploy — `prod-deploy-drift.yml`, PR #848
- [x] Smoke test can't tell "service down" from "stale bundle" → assert the user bubble first, fast + descriptive
- [x] Playwright test-timeout (30s default) < its 60s assertions → cold-start budget unreachable; set `test.setTimeout`
- [x] Smoke job uploads no trace artifact / `detail.txt` → bare "DOWN" alert with no context
- [ ] Backend app replacement unbinds the origin cert (recurring 525) → auto re-bind, fail loudly before flipping traffic
- [ ] Probe-secret rotation forces a full Container App replacement → evaluate decoupling from replacement

**Full Story:** `docs/BACKLOG_STORIES/BITB-067-deploy-and-smoke-monitor-reliability-gaps.md`

---

### ✅ BITB-063: Typed Provider Error Contract — Make the Unreachable 503 Reachable

**Status:** ✅ Done
**Size:** S (typed exception + two route handlers + the contract test that was always missing)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — E1 (context: A8, D4)

**As** the operator, **I want** a total LLM-provider outage to surface as a 503 with a clear
"upstream unavailable" signal — to monitoring, to clients, and to users — **so that** incident
response starts with "OpenRouter is down" instead of a misleading generic-500 hunt, and clients
back off instead of retry-hammering a dead upstream.

**Why P1:** When all OpenRouter fallback models were exhausted, the provider raised a bare
`RuntimeError`, and the routes special-cased it by matching the substring `"All models rate
limited"` — a string that appeared in **neither** exhaustion message. The intended 503 branch
(non-stream) and the friendly stream-error chunk were unreachable dead code; every real outage
misreported as a generic 500.

**Acceptance Criteria:**

- [x] New `AllModelsExhaustedError` (`api/providers/errors.py`), carrying `reason`
      (`rate_limited`/`unavailable`), `models_tried`, and an optional `retry_after`, raised by both
      `chat()` and `chat_stream()` exhaustion paths in `api/providers/openrouter.py`
- [x] Routes catch the **type** (`api/routes/chat.py`): non-stream → HTTP 503 with `Retry-After`
      and a `code: "upstream_unavailable"` detail body; stream → an SSE error chunk with
      `error_code: "upstream_unavailable"`
- [x] Contract tests added (`api/tests/test_provider_error_contract.py`): provider exhaustion
      raises the typed error in both paths, and each route maps it to 503 / an error chunk — a
      change to either side alone now fails CI
- [x] Error responses carry the machine-readable `code`/`error_code` fields (groundwork for a
      later Android follow-up on the `ChatViewModel.kt` substring matching, audit A8 — the Android
      change itself is out of scope here)
- [x] `prod-monitor`'s `synthetic_chat.py` already extracts `error_code` from stream error chunks
      (pre-existing), so the Telegram alert detail automatically distinguishes an upstream outage
      the moment the backend emits the code — no probe change needed. Branching the alert
      *subject/text* on the code, or adding a non-stream probe asserting the 503 directly, is
      follow-up work, not part of this story.

**Full Story:** `docs/BACKLOG_STORIES/BITB-063-typed-provider-error-contract.md`

---

### 🚧 BITB-062: Route Public Semantic Search Through the Index-Friendly Candidate-Pool Pattern

**Status:** 🚧 In Progress — candidate-pool CTE + topics HNSW index + FTS rewrite shipped; persisted
`tsvector` column and the deployed perf re-run deferred (see full story's Scope Note)
**Size:** M (rewrite three query functions onto the existing CTE pattern + one missing index + FTS column)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — S2 (context: S5, S7)

**Note:** this story existed only as a loose story file (never indexed here) since PR #809 created
it alongside BITB-059/060/061/063 — the gap that let it sit unstarted without showing up in a
backlog scan. Added here for visibility.

**As** the operator of a 2-vCPU/4GB production Postgres serving 12 translations, **I want** every
vector-search path to use the HNSW index, **so that** a handful of unauthenticated search calls
cannot saturate the database and starve chat — the actual product — of connections and CPU.

**Why P1:** `search_verses_semantic` / `search_passages_semantic` backed the **public**
`GET /api/v1/scripture/search` endpoint with a `WHERE (1 - cosine_distance) >= threshold` predicate
— the exact full-scan shape the hybrid search path was already rewritten to avoid — and
`topics.embedding` had no vector index at all.

**Acceptance Criteria:** see `docs/BACKLOG_STORIES/BITB-062-index-friendly-public-semantic-search.md`
for the full checklist and what's shipped vs. deferred.

**Full Story:** `docs/BACKLOG_STORIES/BITB-062-index-friendly-public-semantic-search.md`

---

### ✅ BITB-061: Make the Abuse-Control Stack Fail Closed (Turnstile, Rate Limits, Content Safety)

**Status:** ✅ Done — Turnstile, rate-limiter, and content-safety phases all complete
**Size:** M (three coordinated changes: Turnstile policy, shared rate-limit store, safety defaults/metrics)
**Created:** 2026-07-03
**Audit ref:** `docs/audits/2026-07-adversarial-audit.md` — E2, S3, O2

**As** the operator, **I want** bot verification, rate limiting, and content safety to hold their
line when their dependencies fail — and to alert me when they can't — **so that** an attacker's
cheapest path to free LLM usage (or a user in crisis's path past safety screening) is not "wait for
an upstream hiccup".

**Why P1:** Three independent controls share the same silent-fail-open philosophy, all flagged HIGH
in the 2026-07 adversarial audit. **E2:** Turnstile allowed every request through on any siteverify
timeout/error, with no metric marking the bypass. **S3:** the rate limiter is in-memory and
per-process, so limits are 2x too loose across replicas and reset on every deploy. **O2:** content
safety defaults off, and every stage (OpenAI moderation, Llama Guard, Azure) falls back to allow on
error — unacceptable for a pastoral-care product serving people in crisis.

**Acceptance Criteria (summary — full story has detail):**

- [x] Turnstile: rejections fail closed (403); repeated transient siteverify errors trip a circuit
      breaker to fail-closed; isolated blips still fail open but emit a metric (`turnstile.fail_open_total`)
- [x] Rate limiting: counters live in a shared store surviving restarts and consistent across replicas;
      session lifetime cap survives deploys; dedicated unit tests added
- [x] Content safety: keyword stage always runs regardless of ML-stage availability; empty/malformed
      Llama Guard response treated as an error, not "safe"; every fallback branch emits
      `content_safety.fallback_total` with a scheduled-query alert; `content_safety_enabled` default
      flipped on (matches Terraform prod default)

**Full Story:** `docs/BACKLOG_STORIES/BITB-061-fail-closed-abuse-controls.md`

---

### ✅ BITB-068: Content-Safety Smoke Tests — CI Gate + Functional + Deployed Probe

**Status:** ✅ Done (PR #850)
**Size:** S–M (three test tiers + one prod-monitor job + a docs note)
**Created:** 2026-07-10
**Parent ref:** BITB-061 (verification safety net for the content-safety phase, PR #840)

**As** the operator, **I want** an end-to-end smoke test of the content-safety pipeline that runs at
every deployment stage and verifies **both** directions — harmful blocked **and** legitimate content
answered — **so that** neither a silently-degraded safety net nor over-blocking of genuine
help-seekers can ship undetected.

**Why P1:** The safety net had no working end-to-end smoke test. The existing `TestContentSafetySmoke`
still asserted the old HTTP-400 contract, so — since blocks now return a warm HTTP 200 with
`provider == "content_safety"` — its detector fixture saw a 200 and **skipped the entire class**. The
discriminator between "blocked" and "answered" is the `provider` field, not the status code.

**Acceptance Criteria:**

- [x] CI gate: `api/tests/test_content_safety_smoke.py` drives the real ASGI app in deterministic
      `keyword_only` mode (no external keys); asserts harmful blocked, benign allowed, help-seeking
      allowed, and the stream path — both directions. Runs in the `backend-tests` job.
- [x] Functional: rewrote `TestContentSafetySmoke` (`api/tests/functional/test_production_api.py`) to
      the 200/`provider==content_safety` contract; fixed the skip-bug fixture; added a help-seeking
      case; fixed the stream assertion. Revives a test that had been silently inert.
- [x] Deployed probe: `scripts/monitor/synthetic_content_safety.py` + `content-safety` job in
      `.github/workflows/prod-monitor.yml`; fails loudly on a degraded safety net or over-blocking.
- [x] Docs: `AGENTS.md` clarifies why Plan → Build → Verify keeps verification on the strongest model.

**Full Story:** `docs/BACKLOG_STORIES/BITB-068-content-safety-smoke-tests.md`

---

### 🟡 BITB-018: Query Understanding & Context Quality (Phase 1) — Code Complete, Pending Rollout

**Status:** 🟡 Code Complete — Pending Validation & Rollout (flags OFF in prod)
**Size:** L original (implementation done; remaining work is validation + rollout)
**Created:** 2026-02-24
**Reviewed:** 2026-06-07

**As a** user seeking spiritual guidance,
**I want** search to understand the meaning of my situation (not just keyword overlap),
**so that** I receive relevant, comforting scripture.

**Why P1:** Motivated by a real incident (frustrated Italian user → irrelevant Job 21:27).
Query expansion, hybrid search, and topic boosting were **implemented and merged in Feb 2026**
(`docs/DONE/2026-02-24-query-understanding-context-quality.md`) but ship **disabled**
(`api/config.py:76–85`), so the defect still reproduces in prod. Remaining work is split into
BITB-043 (validate + enable) and BITB-044 (populate `verse_topics`).

**Acceptance Criteria:** see full story; tracked via BITB-043 + BITB-044.

**Full Story:** `docs/BACKLOG_STORIES/BITB-018-query-understanding-context-quality.md`

---

### 🚧 BITB-043: Validate & Enable Phase-1 Search Improvements

**Status:** 🚧 In Progress
**Size:** M (1-2 days)
**Created:** 2026-06-07

**As a** user, **I want** search to use the already-built query expansion and hybrid
(semantic + keyword) retrieval, **so that** I get thematically relevant verses instead of
literal matches — without waiting on new retrieval code.

**Why P1:** Highest-ROI item on the search backlog. Query expansion is now enabled
(#741, released 1.27.0) and hybrid search is being enabled (trimmed PR #727). The
remaining work — a golden eval set + scorer to validate and tune these — is carved out
into **BITB-051**. Topic boosting is excluded here — blocked on data (BITB-044).

**Acceptance Criteria (summary — full story has detail):**

- [x] Query expansion enabled by default (#741)
- [x] Hybrid search enabled (`hybrid_search_enabled = True` in `api/config.py`, PR #727 trimmed per BITB-051 P0)
- [x] Golden eval set + scorer (Precision@5 / Recall@10 / MRR) — see **BITB-051** (P0–P3 landed)
- [ ] Baseline measured; hybrid weights tuned + documented; retrospective in `docs/DONE/`
      (needs a live run against prod data/Azure credentials — see `docs/SEARCH_EVAL_HOWTO.md`)

**Full Story:** `docs/BACKLOG_STORIES/BITB-043-validate-and-enable-phase1-search.md`

---

### 🚧 BITB-051: Search Retrieval-Evaluation Harness (golden set + scorer)

**Status:** 🚧 In Progress (P0–P3 landed; P4 todo)
**Size:** L (3-5 days, 5 small PRs)
**Created:** 2026-06-16

**As the** maintainer, **I want** a repeatable scorer that measures verse-retrieval
ranking (Precision@5 / Recall@10 / MRR) over a curated multilingual golden set, **so
that** I can validate whether query expansion / hybrid search actually help and tune
their weights instead of shipping search changes blind.

**Why P1:** Directly unblocks BITB-043 validation — expansion is live but unmeasured.
Delivered in 5 phases: **P0** trim PR #727 to the hybrid flip ✅; **P1** metric +
normalization core (`api/search_eval/`) ✅; **P2** 55+ case golden set (all 11
languages) + `--validate` + non-blocking CI ✅; **P3** runner over real retrieval + A/B
report/CLI ✅; **P4** full-corpus eval automated in CI (prod read-only + cached rebuild,
Azure embeddings, manual + nightly) — todo. Embeddings are **Azure `text-embedding-3-small`
(1536) everywhere** to match prod; per-PR CI is validate-only.

**Acceptance Criteria (summary — full story has detail):**

- [x] P0: PR #727 trimmed to hybrid-search enablement only
- [x] P1: `api/search_eval/` core (normalize + P@5/R@10/MRR + false-positive guard) with no-DB tests
- [x] P2: 55+ multilingual golden set (11 languages) + loader + `--validate` + non-blocking CI
- [x] P3: runner (`api/search_eval/runner.py`) + report/CLI (`--run`); manual prod-read-only A/B table documented in `docs/SEARCH_EVAL_HOWTO.md`
- [ ] P4: manual + nightly full-corpus eval (Routes A & B + smoke) on Azure

**Full Story:** `docs/BACKLOG_STORIES/BITB-051-search-retrieval-eval-harness.md`

---

### 🚧 BITB-052: Audit & Close Bible Reference-Normalization Gaps

**Status:** 🚧 In Progress (aliases + case/diacritic normalization + coverage audit done; versification offsets deferred)
**Size:** M (1-2 days)
**Created:** 2026-06-16

**As the** maintainer, **I want** book/verse references to canonicalize reliably across
all 11 languages and their common citation variants, **so that** the retrieval-eval
metrics (BITB-051) and the app's shared verse-linking don't silently mishandle references.

**Why P2:** Surfaced during BITB-051 P1 review — `normalize_book_name` coverage is uneven:
localized singular/citation forms (Italian `Salmo`, German `Psalm`, Spanish/French/PT) and
abbreviations are missing for several languages (Arabic/Russian have them), numbered-book
variants and case/diacritic handling are gaps, and per-translation **versification**
offsets can mis-score a correct hit. Low impact for BITB-051 today (its refs are
English-canonical) but affects localized input and the app-wide normalizer.

**Acceptance Criteria (summary — full story has detail):**

- [x] Per-language coverage matrix identifying every gap (`docs/audits/book-name-coverage.md`,
      regenerate via `scripts/audit_book_name_coverage.py`)
- [x] Missing localized singular/abbreviation aliases added (Psalms + common books) — PR #791
- [x] Case/diacritic-insensitive + numbered-book-variant matching, no regressions
- [ ] Versification offsets quantified + documented handling decision (with tests)
- [x] Table-driven tests across all 11 languages green

**Concrete reproductions (added 2026-06-19, from verse-grounding debugging):** abbreviation /
numbered-book references fail to parse *with and without* parentheses —
`extract_all_references("1 Cor 13:4")`, `"Cant 2:1"`, `"Songs 2:1"` all return `[]`, while
`"Ps 23:1"` works; full names (`1 Corinthians`, `Song of Solomon`) work. Also a cross-parser
**versification/divergence** note: the frontend verse parser does not support German comma
separators (`Johannes 3,16`) that the backend does — fold into the "robust matching" + parser-sync
scope here.

**Full Story:** `docs/BACKLOG_STORIES/BITB-052-reference-normalization-gaps.md`

---

### 🎯 BITB-053: Ground Unquoted / Paraphrased Verse Citations

**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-06-19

**As a** user reading a Bible answer in any language, **I want** the scripture presented to match
the real verse **even when it is not in quotation marks**, **so that** paraphrased "citations"
can't drift from the canonical text.

**Why P2:** Grounding (`verse_grounding.py`) only rewrites *quoted* spans adjacent to a reference.
An unquoted paraphrase (`In Isaia 41:10 Dio ci dice di non temere…`) is never corrected — the
largest remaining "citation doesn't match the DB" class once parenthesized-reference parsing is
fixed.

**Acceptance Criteria (summary — full story has detail):**

- [ ] Unquoted reference-adjacent paraphrase corrected/surfaced to canonical text
- [ ] Ordinary discussion *about* a verse never altered (negative tests)
- [ ] Parametrized cross-language tests (all 11) + version-faithfulness + chat/chat_stream integration

**Full Story:** `docs/BACKLOG_STORIES/BITB-053-ground-unquoted-paraphrased-citations.md`

---

### 🎯 BITB-054: Per-Translation Data Observability + Honest Handling of Unresolvable Citations

**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-06-19

**As the** maintainer, **I want** to know — and the app to behave honestly — when a cited verse
can't be resolved in the user's translation, **so that** a missing/incomplete translation never
shows up as silently hallucinated scripture.

**Why P2:** When a translation isn't loaded (or has no embeddings), search returns no context and
grounding silently keeps the model's text (`reason=unresolved`). The only diagnostic today is a
manual SQL snippet, and the unresolved path is invisible.

**Acceptance Criteria (summary — full story has detail):**

- [ ] Per-translation verse + embedding counts via a diagnostic (route or startup log)
- [ ] Startup/CI warning + metric when a supported language has no usable verse data
- [ ] Configurable handling of `unresolved` citations (fallback / strip / notify) with tests

**Full Story:** `docs/BACKLOG_STORIES/BITB-054-translation-data-observability.md`

---

### 🚧 BITB-050: Improve Verse Search Thematic Relevance and Response Depth

**Status:** 🚧 In Progress
**Size:** S (< 4 hours)
**Created:** 2026-06-12

**As a** user seeking spiritual guidance, **I want** the verses surfaced for me to match
the *theme* of what I'm facing and the reply to actually unfold that scripture, **so that**
the answer meets me where I am instead of dropping a one-line quote.

**Why P1:** Two prompt-only quality gaps that affect every answer. (1) The query-expansion
prompt over-expands into off-theme terms that pull in irrelevant verses; it is rewritten to
anchor on the 1–2 core themes. (2) The conversational system prompt is given a
response-depth instruction (acknowledge → verse → unfold → bring home) that guards against
padding. **Scope note:** the query-expansion flag flip + validation are owned by **BITB-043** —
this story only changes prompt *content*, enabling no flags.

**Acceptance Criteria (summary — full story has detail):**

- [x] Expansion prompt is theme-focused and warns against off-theme drift
- [x] `RESPONSE_DEPTH_GUIDANCE` wired into `get_system_prompt()` for all languages
- [x] Depth guidance asks for substance while forbidding padding; allows short replies
- [x] Tests cover both changes
- [ ] Full backend test suite passes in CI

**Full Story:** `docs/BACKLOG_STORIES/BITB-050-search-thematic-relevance-and-response-depth.md`

---

### ✅ BITB-038: Quote Scripture Verbatim — Never Paraphrase a Cited Verse

**Status:** ✅ Done (branch claude/backlog-item-ft0aju, 2026-06-09)
**Size:** S (< 4 hours)
**Created:** 2026-06-04

**As a** user who trusts this app to quote the Bible accurately,
**I want** every verse presented as a direct quotation to match my translation's real wording,
**so that** I'm never shown an altered citation that changes the meaning of scripture.

**Why P1:** Reported bug — an Italian response said *"la frutta dello Spirito"* (Galatians 5:22-23)
when the Italian Bible reads *"il frutto dello Spirito"* (singular). Verse text shown to users is
LLM-generated prose, and the system prompts never forbid paraphrasing/re-translating a quoted
verse. A Bible app that misquotes the Bible undermines its core promise. Small, prompt-level fix.

**Acceptance Criteria:**

- [x] All three system prompts (`get_system_prompt`, `get_verse_lookup_prompt`,
  `get_prayer_lookup_prompt`) instruct the model to quote scripture verbatim from the Scripture
  Context and never paraphrase, re-translate, or alter wording (incl. singular/plural, articles)
- [x] Prompt instructs the model not to fabricate verse wording when the verse text is absent
- [x] Italian "fruit of the Spirit" query returns *"il frutto…"* (not *"la frutta"*) when the verse is in context
- [x] Unit test asserts the verbatim rule is present in all three prompt builders
- [x] Full backend test suite passes

**Full Story:** `docs/BACKLOG_STORIES/BITB-038-verbatim-scripture-citation.md`

---

### ✅ BITB-039: Android — Keep the Current Chat When the Phone Is Rotated

**Status:** ✅ Done (PR #689 — 2026-06-06)
**Size:** S (< 4 hours)
**Created:** 2026-06-04

**As an** Android user mid-conversation,
**I want** rotating my phone to keep me in the same chat with all my messages,
**so that** I don't lose my conversation just because the screen orientation changed.

**Why P1:** Reported bug — rotation resets the user into an empty/new chat. `MainActivity` has no
`android:configChanges`, so rotation recreates the Activity; the recreated Compose tree re-runs
`LaunchedEffect(conversationId)` and, because an in-progress chat keeps the `chat/new` route,
calls `startNewConversation()` which wipes the in-memory conversation. Data-loss UX bug on a
common interaction; one-line manifest fix plus a defensive guard.

**Acceptance Criteria:**

- [x] New chat + send message + rotate → same messages and conversation remain visible
- [x] Existing saved conversation survives rotation
- [x] Rotating during an in-flight response does not start a new chat
- [x] Locale switching from Settings still works (still recreates Activity, applies new language)
- [x] Existing Android unit tests pass; guard logic is covered by a test

**Full Story:** `docs/BACKLOG_STORIES/BITB-039-android-preserve-chat-on-rotation.md`

---

### ✅ BITB-041: Verse Detail Never Loads — Add Timeout, Error/Retry, and Monitoring

**Status:** ✅ Done
**Size:** M (1-2 days)
**Created:** 2026-06-04

**As a** user who taps a Bible verse,
**I want** the verse text to load promptly or fail with a clear, retryable error,
**so that** I never get stuck on a `////` placeholder and a spinner that never stops — and as the operator I want this failure monitored and alerted.

**Why P1:** Reported bug — tapping a verse in Italian (ITA1927) shows `////` and an
infinite spinner (English/German work). Root causes: `ChatViewModel.loadChapter()`
has no timeout (never reaches `Error`), the backend verse/chapter query has no timeout
(hangs while health checks stay green), empty synthetic text is rendered as a verse,
and `deployment/monitoring.tf` has no alert for verse-fetch latency/errors — so a hung
fetch that returns a bad 200/500 is invisible. Shares an Italian root cause with BITB-040.

**Acceptance Criteria:**

- [x] Slow/unreachable chapter fetch shows a clear error + working Retry within a bounded time — never an infinite spinner
- [x] Verse text area never shows `////`/empty quotes (loading → verse or error)
- [x] Backend verse/chapter reads time out to 504 instead of hanging
- [x] Italian (ITA1927) detail loads for the reported references; corrupt data repaired + empty-text integrity check added
- [x] Monitoring alert fires on elevated verse/chapter fetch error-rate or p95 latency/timeouts (existing action group)
- [x] New Android + backend tests cover timeout, error, retry, and empty-text paths

**Test note:** existing tests over-mock and skip integration — `loadChapter` is tested
only for `IOException`, `VerseDetailBottomSheet` has no UI test, and the chapter route
covers only 200/404. These gaps let the bug ship.

**Full Story:** `docs/BACKLOG_STORIES/BITB-041-verse-detail-load-resilience-and-monitoring.md`

---

### ✅ BITB-040: Verse-Detail Header Shows English Book Name Instead of Localized

**Status:** ✅ Done (verified against current main 2026-07-15 — `buildSyntheticVerse()` carries
`localizedBook` through the verse link, `Verse.reference` prefers it, and
`VerseDetailBottomSheetComposeTest.kt` covers the localized/fallback/non-Latin-script cases)
**Size:** S (< 4 hours)
**Created:** 2026-06-04

**As a** non-English user tapping a Bible verse,
**I want** the verse-detail header to use my translation's book name (e.g. *"Esodo 30:22"*, *"2. Mose 30:22"*),
**so that** the reference matches the language I'm reading in.

**Why P1:** Reported bug affecting **all non-English locales** on **every** verse tap —
the header shows the English book name (*"Exodus 30:22"*) even when the verse text loads
correctly. `buildSyntheticVerse()` never sets `localizedBook` (`ChatMessageItem.kt:753-770`),
so the sheet header (`VerseDetailBottomSheet.kt:106`) always falls back to the English
`book`. Independent of BITB-041 (which only made it more visible). Tests mock the real
`get_localized_book_name` and skip the verse-flow UI, so it went uncaught. Small fix:
carry the localized name the LLM already wrote through the verse link.

**Acceptance Criteria:**

- [ ] Tapping a verse shows the localized header before and after load, and even if the fetch fails
- [ ] Verified across several non-English locales (incl. one non-Latin-script); no English regression
- [ ] Real (un-mocked) unit test for `get_localized_book_name` across all translations
- [ ] Compose UI test covers the localized header in the verse-detail sheet
- [ ] All existing Android + backend tests pass

**Full Story:** `docs/BACKLOG_STORIES/BITB-040-verse-detail-localized-book-name.md`

---

### ✅ BITB-021: Instrument LLM and Database Performance Metrics

**Status:** ✅ Done (PR #229, #233, #236, #237, #242 merged 2026-03-06)
**Size:** M (4-6 hours)
**Created:** 2026-03-06
**Completed:** 2026-03-06

**As a** site reliability engineer monitoring the Bible app in production,
**I want** the Performance Dashboard to display real-time LLM and database metrics,
**so that** I can detect performance degradation, identify bottlenecks (slow queries, high TTFT, rate limit
exhaustion), and correlate errors with infrastructure health.

**Why P1:** The Azure Monitor Performance Dashboard was deployed but shows "No data" because the backend doesn't emit
the specific custom metrics (`llm.ttft_ms`, `db.search.duration_ms`, etc.) that the dashboard queries expect. This
story adds the missing instrumentation so the dashboard becomes functional.

**Acceptance Criteria (summary — full story in `docs/BACKLOG_STORIES/BITB-021-instrument-performance-metrics.md`):**

- [x] LLM metrics emitted: `llm.ttft_ms`, `llm.total_duration_ms`, `llm.fallback_count`, `llm.rate_limit_hits`, `llm.tokens_per_second`
- [x] Database metrics emitted: `db.search.duration_ms`, `db.query.duration_ms`, `db.slow_queries`
- [x] Metrics instrumented in `OpenRouterProvider`, `ClaudeProvider`, `OllamaProvider`, and `ScriptureRepository`
- [x] Performance Dashboard shows real data in all LLM and Database panels after deployment
- [x] Full test suite passes (1,033+ tests)

**Implementation Notes:**

- PR #240: Workbook scoped to Application Insights (fixed "No data" panels)
- PR #242: Added `schema_migrations` tracking table and smart migration runner
- PR #243: Fixed broken KQL queries in all tiles panels (zero-row-safe pattern)

**Tech Constraints:**

- Must not break existing OpenTelemetry tracing or logging
- Must use OpenTelemetry metrics API (already configured in `main.py`)
- Must follow OTel semantic conventions (counter for monotonic, histogram for distributions)
- Metrics automatically exported to Application Insights (no additional config needed)

**Dependencies:** PRs B1-B5 merged ✅, Application Insights configured ✅, Dashboard deployed ✅

**Full Story:** `docs/BACKLOG_STORIES/BITB-021-instrument-performance-metrics.md`

---

### 🚧 BITB-002: Sync Conflicted PRs with Main

**Status:** 🚧 In Progress (PR #171 merged, ready to start)
**Size:** M

**As a** developer,
**I want** all open PRs to be conflict-free and up-to-date with main,
**so that** we can review and merge them without manual intervention.

**Acceptance Criteria:**

- [ ] PR #167 (ESLint 9) rebased on latest main, conflicts resolved
- [ ] PR #168 (Secrets scan CI) rebased on latest main, conflicts resolved
- [ ] PR #169 (OWASP dependency check) rebased on latest main, conflicts resolved
- [ ] PR #170 (APK security flags) rebased on latest main, conflicts resolved
- [ ] All rebased PRs pass CI checks
- [ ] Tracking document moved to `docs/DONE/`

**Tech Constraints:**

- Must maintain git history (use rebase, not merge)
- Must preserve existing commit messages and authorship
- Must run `make pre-commit` before pushing

**Dependencies:**

- ✅ PR #171 merged (unblocked)
- PR #170 depends on PR #169

**Tracking Doc:** `docs/WIP/PR-CONFLICTS-AND-SYNC-PLAN.md`

---

### ✅ BITB-003: Enable Turnstile Bot Protection on Android

**Status:** ✅ Done
**Size:** M (~9 hours)

**As a** mobile user,
**I want** the Android app to have the same bot protection as the web app,
**so that** the backend remains secure from abuse.

**Acceptance Criteria:**

Android Implementation:

- [x] Hidden `TurnstileWebView` composable created (loads local HTML with Turnstile widget)
- [x] `TurnstileManager` Hilt singleton manages token state (StateFlow)
- [x] `TurnstileInterceptor` (OkHttp) injects `X-Turnstile-Token` header automatically
- [x] `ChatInputField` disables send button while `!isTurnstileReady` (matches web UX)
- [x] WebView configured: JavaScript enabled, DOM storage enabled, cookies enabled
- [x] `turnstile.html` asset created with Cloudflare widget (invisible mode)
- [x] ProGuard rules added to preserve `@JavascriptInterface` methods

Testing & Documentation:

- [x] Unit tests for `TurnstileManager` token state management (`TurnstileManagerTest.kt` — 16 tests)
- [ ] Manual QA: initialization timing, token expiry, offline behavior
- [x] Graceful fail-open when WebView unavailable or network down — `TurnstileManager.hasError`
  state; `ChatViewModel` sets `isTurnstileReady=true` on widget error so the user isn't
  permanently blocked
- [x] Backend validation works unchanged (reuses `api/utils/turnstile.py`)

**Tech Constraints:**

- ❌ **NO official Cloudflare Android SDK** — must use WebView approach (Cloudflare's official recommendation)
- Min SDK 26 (existing constraint) ✅ Compatible
- Zero backend changes required — `X-Turnstile-Token` header already validated
- Token lifetime: 5 minutes (WebView auto-refreshes on expiry via `expired-callback`)

**Implementation Approach (from research):**

1. Create `assets/turnstile.html` with Cloudflare JS widget (invisible, data-size="invisible")
2. `TurnstileWebView` loads HTML, exposes `Android.onToken()` JavaScript bridge
3. `TurnstileManager` singleton holds token as `StateFlow<String?>`, injected via Hilt
4. `TurnstileInterceptor` reads token from manager, adds to every API request header
5. `ChatViewModel` observes `TurnstileManager.isReady` → UI disables send button until ready

**Out of Scope:**

- Custom CAPTCHA implementation (using official Cloudflare widget)
- Separate Turnstile site key for Android (can use same as web initially)
- Backend changes to Turnstile logic

**Dependencies:**

- Requires: Android app bootstrap (PR #156) already merged ✅

**Research Doc:** Task ses_3753a6f4cffezvpl17chuMVTHC (Turnstile Android research)
**Tracking Doc:** `docs/WIP/android-app.md`

---

### ✅ BITB-004: Add Database Migration Framework (Alembic)

**Status:** ✅ Done (merged pending PR)
**Size:** L
**Completed:** 2026-07-30

**As a** developer,
**I want** a version-controlled database migration system,
**so that** schema changes are tracked, reversible, and safely deployed.

**Acceptance Criteria:**

- [x] Alembic installed and configured (`api/alembic/`, run from `api/`)
- [x] Initial migration created from current schema (`api/alembic/versions/r0001_baseline_schema.py`,
      generated via `--autogenerate` against a live local Postgres+pgvector, then hand-verified)
- [x] Migration runs successfully on fresh database (`alembic upgrade head` creates all 9
      ORM-backed tables + `alembic_version`)
- [x] Rollback tested and working (`alembic downgrade base` removes all 9 tables cleanly,
      re-`upgrade head` recreates them; proven both manually and in
      `api/tests/test_alembic_migrations.py`)
- [x] CI runs migration check before deploying (new `alembic-migrations` job in
      `.github/workflows/test_update.yml`: upgrade → check → downgrade base → upgrade → history,
      read-only `alembic check`, never `--autogenerate`, on its own ephemeral Postgres service)
- [x] Documentation updated with migration workflow (`api/alembic/README.md`,
      `docs/MIGRATION_GUIDELINES.md` "Long-Term Solution: Alembic" section)

**Tech Constraints:**

- Must work with existing SQLAlchemy models — yes, `target_metadata` is
  `[ScriptureBase.metadata, FeedbackBase.metadata]` from `scripture/models.py` / `feedback/models.py`
- Must work with asyncpg connection pool — `env.py` reuses
  `scripture.database.get_async_database_url()` for the same SSL convention as the app
- Must support zero-downtime deployments (future-proofing) — `run_migrations_offline()`
  (`alembic upgrade head --sql`) is kept working for a future DBA-reviewed, zero-downtime path

**Out of Scope (respected):**

- Converting existing production database (manual one-time task) — **not done in this PR**;
  see the "operator runbook note" in `docs/MIGRATION_GUIDELINES.md` (`alembic stamp r0001`,
  executes zero DDL, is a deliberate future manual step)
- Auto-generated migrations from model changes in CI — CI only ever runs `alembic check`
  (read-only), never `--autogenerate`
- Backfilling the 5 legacy non-ORM tables (`sessions`, `verse_topics`, `rate_limit_hits`,
  `rate_limit_sessions`, `schema_migrations`) into Alembic — still owned by
  `scripts/migrations/`/`scripts/init.sql`, invisible to Alembic by design (`include_name`
  allowlist in `env.py`)

**Related:** TASKS.md #1.5

---

### 🎯 BITB-005: Make PostgreSQL Database Private (Azure)

**Status:** 🎯 Todo
**Size:** M

**As a** security-conscious operator,
**I want** the production database to be inaccessible from the public internet,
**so that** we reduce attack surface and comply with security best practices.

**Acceptance Criteria:**

- [ ] Azure Private Endpoint configured for PostgreSQL
- [ ] `public_network_access_enabled = false` in Terraform
- [ ] Backend container can still connect via VNet
- [ ] Local development unaffected (uses localhost or Azure firewall exception)
- [ ] Terraform plan reviewed before apply
- [ ] Deployment tested in staging (if available) before production

**Tech Constraints:**

- Must work with Azure Container Apps networking
- Must not break existing CI/CD pipeline
- Requires Azure VNet integration for Container Apps

**Out of Scope:**

- Setting up staging environment (separate story)
- Database encryption at rest (already enabled)

**Related:** TASKS.md #2.1 (Critical security issue)

---

### 🚧 BITB-013: Performance Monitoring & Dashboard

**Status:** 🚧 In Progress (Quick Wins deployed 2026-02-23, monitoring pending)
**Size:** L (3–5 days, can be split into 4 sub-PRs)
**Priority:** P1 (High) — Observability needed to track performance improvements

**As a** product owner and developer,
**I want** comprehensive performance monitoring with a visual dashboard,
**so that** I can identify bottlenecks, track improvements over time, and be alerted before users are impacted.

**Root Cause Analysis (from research):**

1. **LLM Response Latency** (5–30s per request) — Primary bottleneck
   - Double LLM call: `_detect_intent()` + main `llm.chat()`
   - ✅ **FIXED:** Frontend now uses streaming `/api/v1/chat/stream` (deployed 2026-02-23)
   - OpenRouter free tier has 3–10s queue times
2. **Container Apps Cold Start** (15–45s intermittent)
   - ✅ **FIXED:** `backend_min_replicas = 1` in Terraform (deployed 2026-02-23)
   - First request wakes container, FastAPI startup includes DB init + provider health checks
3. **pgvector Semantic Search** (200ms–2s per search)
   - ✅ **FIXED:** HNSW indexes created (migration ran 2026-02-23)
   - ⚠️ **Issue Found:** `maintenance_work_mem` too low (64MB), index build spilled to disk
   - Two searches per request: `search_verses_semantic()` + `search_passages_semantic()`
   - B1ms PostgreSQL (1 vCore, 2GB RAM) — smallest SKU, can't keep embeddings in memory

**Quick Wins (DEPLOYED TO PRODUCTION 2026-02-23):**

- [x] Switch frontend to streaming endpoint (`/api/v1/chat/stream`) — **HIGHEST IMPACT** ✅
- [x] Add pgvector HNSW indexes (200–2000ms → 10–50ms) — **MASSIVE DB SPEEDUP** ✅
- [x] Set `backend_min_replicas = 1` in Terraform — **ELIMINATE COLD STARTS** ✅
- [ ] Remove or optimize `_detect_intent()` LLM call — **CUT 1–3s LATENCY** (deferred)

**Acceptance Criteria:**

**Backend Instrumentation:**

- [ ] OTel spans added for LLM call duration (intent detect + main chat)
- [ ] OTel spans added for embedding generation duration
- [ ] OTel spans added for pgvector search duration (`search_verses_semantic`, `search_passages_semantic`)
- [ ] Correlation ID middleware added (X-Request-ID header, logged in every entry) — **BITB-008**
- [ ] LLM-specific metrics: `llm.duration_ms`, `llm.time_to_first_token_ms`, `llm.tokens_per_second`
- [ ] LLM metrics: `llm.tokens.total` (counter), `llm.fallback.attempts` (counter), `llm.rate_limit.hits` (counter)
- [ ] DB metrics: `db.search.duration_ms` (histogram), `db.query.duration_ms` (histogram), `db.connections.active` (gauge)

**Database-Specific:**

- [ ] PostgreSQL slow query log enabled (`log_min_duration_statement = 100ms` in Terraform)
- [x] HNSW indexes created on `verses.embedding` and `passages.embedding` ✅ (2026-02-23)
- [ ] PostgreSQL performance tuning (`maintenance_work_mem`, `shared_buffers`, etc.) — **IN PROGRESS**
- [ ] Index usage tracked via `pg_stat_user_indexes` queries in dashboard
- [ ] Query profiler middleware logs EXPLAIN ANALYZE for queries >500ms

**OpenRouter-Specific:**

- [ ] Time to first token (TTFT) tracked in streaming responses
- [ ] Token usage and generation speed tracked (`tokens_per_second`)
- [ ] Model-specific performance comparison (llama-3.3 vs gemma-2)
- [ ] Fallback frequency tracked (how often primary model fails with 429)
- [ ] Rate limit headers parsed (`X-RateLimit-Remaining-Requests`)

**Frontend Instrumentation:**

- [ ] `@microsoft/applicationinsights-web` SDK integrated in Next.js
- [ ] Page load time tracked (Core Web Vitals)
- [ ] Chat message send → first byte timing tracked as custom metric
- [ ] Frontend errors reported to App Insights

**Dashboard:**

- [ ] Azure Monitor Workbook created with panels for: traffic, performance, LLM, DB, infrastructure
- [ ] Dashboard shows p50/p95/p99 response time, error rate, availability
- [ ] LLM panel: TTFT, duration, tokens/sec, model comparison, fallback rate
- [ ] DB panel: search duration, query duration, connection pool, CPU/memory, index usage
- [ ] Workbook definition committed as code (Terraform or JSON) to repo
- [ ] Dashboard link added to README

**Alerting:**

- [ ] Alert: chat response time p95 > 15s sustained 5min
- [ ] Alert: error rate > 5% sustained 5min
- [ ] Alert: backend availability < 95% (1h window)
- [ ] Alert: PostgreSQL CPU > 85% sustained 10min
- [ ] Alert: OpenRouter rate limit <10% remaining
- [ ] All alerts notify via email

**Tech Constraints:**

- Must use existing Azure Application Insights (no new SaaS APM tools)
- Must work with async FastAPI and Next.js App Router
- Dashboard definition must be in source control (Terraform or ARM template)
- Frontend SDK must not significantly increase bundle size

**Out of Scope:**

- Distributed tracing across Cloudflare edge (complex, low value currently)
- Cost attribution per user
- Custom OpenTelemetry collector deployment
- Self-hosted Grafana/Prometheus (Azure Monitor is sufficient)

**Suggested Implementation Split:**

1. **PR A: Quick Wins** (S — 2–4 hours) — ✅ **DEPLOYED 2026-02-23**
   - ✅ Switch UI to streaming endpoint
   - ✅ Add pgvector HNSW indexes (migration ran, index build in progress)
   - ✅ Set `backend_min_replicas = 1`

2. **PR A2: PostgreSQL Tuning** (S — 1-2 hours) — ✅ **READY FOR REVIEW (PR pending)**
   - ✅ Add Terraform configuration for PostgreSQL performance parameters
   - ✅ Increase `maintenance_work_mem` to 256MB (fix index build performance)
   - ✅ Tune `shared_buffers`, `work_mem`, `effective_cache_size`
   - ✅ Enable slow query logging
   - ✅ Reference migration file created: `scripts/migrations/003_tune_postgresql_config.sql`

3. **PR B: Backend OTel Spans + Metrics** (M — 1–2 days)
   - Add spans to LLM calls, DB queries, embeddings
   - Add histogram/counter metrics
   - Enable PostgreSQL slow query log

4. **PR C: Frontend App Insights SDK** (S — 3–5 hours)
   - Integrate `@microsoft/applicationinsights-web`
   - Track Core Web Vitals, custom events

5. **PR D: Azure Monitor Workbook + Alerts** (M — 1–2 days)
   - Build workbook with KQL queries
   - Configure alert rules
   - Commit as Terraform code

**Dependencies:**

- BITB-008 (Correlation IDs) — can be done as part of this story (PR B)
- BITB-004 (Alembic) — optional, HNSW indexes can be added via migration or manual SQL

**Research Docs:**

- Task ses_3753a0314ffeOZnLwB42JZ3AJI (Performance monitoring research)
- `docs/WIP/MONITORING-DB-OPENROUTER-ADDENDUM.md` (DB & OpenRouter deep dive)

**Expected Impact:**

| Metric | Before | After (Actual) | Improvement |
| ------ | ------ | ------------- | ----------- |
| Semantic search | 200-2000ms | **10-50ms** (HNSW deployed) | **40-200x faster** ✅ |
| LLM TTFT | Unknown | **1-3s** (streaming deployed) | **10x UX improvement** ✅ |
| Total response | 10-30s perceived | **1-3s perceived** (streaming) | **Streaming = instant** ✅ |
| DB CPU usage | 60-80% | **<20%** (HNSW deployed) | **4x efficiency** ✅ |
| Cold starts | 15-45s | **0s** (min_replicas=1) | **Eliminated** ✅ |
| Index build time | 10-30 min | **3-5 min** (after tuning) | **5-6x faster** (pending PR A2) |

**Known Issues:**

- ⚠️ HNSW index build encountered `maintenance_work_mem` limit (64MB) during migration 002
  - Index build completed but spilled to disk (slower build, correct result)
  - PostgreSQL notice: "hnsw graph no longer fits into maintenance_work_mem after 14284 tuples"
  - **Fix:** PR A2 will increase `maintenance_work_mem` to 256MB for future rebuilds

---

### 🎯 BITB-027: Android Chat-First Navigation with History Drawer

**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-05-10

**As an** Android user,
**I want** the app to open directly into the chat experience (resuming my last conversation),
**so that** I can start interacting immediately with my chat history one tap away behind a drawer.

**Why P1:** Every launch forces users through a list screen before they can interact — this is the primary funnel and directly affects retention.

**Acceptance Criteria:**

- [ ] After `splash`, app navigates directly to `ChatScreen` with the last-used conversation pre-loaded
- [ ] If no prior conversation exists, a fresh one is created and example prompts are visible
- [ ] Hamburger icon on **top-left** opens a `ModalNavigationDrawer` listing past conversations + "+ New chat" + Settings link
- [ ] **"+ New chat"** icon on **top-right** creates a new conversation (replaces back-stack entry)
- [ ] System Back from resumed chat exits the app (no intermediate conversations list)
- [ ] Swipe-from-left edge opens the drawer
- [ ] Last opened conversation id persists in DataStore across app restarts
- [ ] No regression in deep-links to `chat/{conversationId}`

**Full Story:** `docs/BACKLOG_STORIES/BITB-027-android-chat-first-navigation.md`

---

### 🚧 BITB-057: Android — In-App Update API (Flexible Flow)

**Status:** 🚧 In Progress — [PR #863](https://github.com/zioalex/getinspiredbythebible/pull/863) open, pending CI + review
**Size:** M (1–2 days)
**Created:** 2026-07-01

**As an** Android user, **I want** the app to tell me when a new version is available, **so that**
I can update and get the latest features and fixes without checking the Play Store manually.

**Why P1:** The app has no mechanism to detect or prompt for Play Store updates. Users on outdated
builds receive no signal that improvements exist. Implements the flexible (background-download,
non-disruptive) flow via `com.google.android.play:app-update-ktx`; guarded by `BuildConfig.DEBUG`
at the `MainActivity` call sites so debug and sideloaded builds are unaffected.

**Acceptance Criteria (summary — full story has detail):**

- [x] `app-update-ktx` v2.1.0 added to `libs.versions.toml` + `build.gradle.kts`
- [x] `InAppUpdateManager.kt` wraps `AppUpdateManager` with constructor injection for testability
- [x] Flexible flow triggered on cold start when update available and staleness ≥ 3 days
- [x] Snackbar with "Install update" action shown when download completes; calls `completeUpdate()`
- [x] `onResume` re-checks for a pending install (app backgrounded during download)
- [x] Unit tests with `FakeAppUpdateManager`; graceful no-op in debug and on sideloaded builds

**Full Story:** `docs/BACKLOG_STORIES/BITB-057-android-inapp-update-api.md`

---

### ✅ BITB-058: Android — "What's New" Bottom Sheet on First Launch After Update

**Status:** ✅ Done (2026-07-15)
**Size:** S (< 1 day)
**Created:** 2026-07-01

**As an** Android user, **I want** to see a brief "What's New" summary the first time I open the
app after an update, **so that** I notice new features without digging into Settings manually.

**Why P1:** The app updates silently; users have no post-update signal. BITB-031 added a changelog
screen in Settings > About but requires active navigation. This story surfaces the top changelog
entry automatically — once per update, never on fresh install — using the existing `changelog.json`
asset, `ChangelogEntry` model, and `MarkdownText` dependency (no new library).

**Acceptance Criteria (summary — full story has detail):**

- [x] `last_seen_version_code` persisted in `app_prefs`; helpers added alongside `hasSplashBeenSeen()` pattern
- [x] Modal skipped on fresh install (stored == -1); shown exactly once per update
- [x] `WhatsNewBottomSheet.kt` renders top `ChangelogEntry` via `MarkdownText`; graceful empty state
- [x] "Dismiss" closes sheet and marks version seen; "See All" navigates to `changelog` route and marks seen
- [x] String keys `whats_new_title`, `whats_new_dismiss`, `whats_new_see_all` added in all 11 locales
- [x] Unit tests: stored==-1 → false; stored==current → false; stored==current-1 → true

**Full Story:** `docs/BACKLOG_STORIES/BITB-058-android-whats-new-on-launch.md`

---

> **Product feature batch (maintainer, 2026-07-25) → BITB-075…081.**
> Seven stories from a single product review: raise the message limit, an About page and
> intro modal explaining why Vox Quieta exists, clarify-before-answering, the off-screen
> web bottom bar, follow-up suggestion chips, and the Android example-tap fix.

### 🎯 BITB-075: Raise the Chat Message Limit to 500 Characters (Single Source of Truth)

**Status:** 🎯 Todo
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

**As a** user describing a real, complicated situation, **I want** to write up to 500 characters in
one message, **so that** I can give enough context to get a useful answer instead of amputating my
question to fit a 300-character box.

**Why P1:** Raising the number also fixes a live production defect. The limit is hard-coded in five
places that disagree: the deployed value is **200** (`deployment/terraform.tfvars:91`), the backend
default is **300** (`api/config.py:180`), and both clients cap at **300**
(`frontend/src/lib/api.ts:121`, `ChatViewModel.kt:173`). Today a 250-character message passes the
input box, is rejected with a 422, and the error tells the user the limit is 300. Raising the number
without fixing the drift just moves the bug.

**Acceptance Criteria (summary):**

- [ ] 500 accepted end-to-end (web + Android); 501 blocked client-side and rejected server-side
- [ ] Every layer agrees — code default, Terraform, tfvars, env manifest, deployment README
- [ ] `GET /config` publishes `chat.max_message_length`; clients use it, constant is fallback only
- [ ] "Message too long" error and the character counter show the *effective* limit

**Full Story:** `docs/BACKLOG_STORIES/BITB-075-raise-message-limit-to-500.md`

---

### 🎯 BITB-079: Web — the Bottom Bar Is Permanently Off Screen on the Chat Page

**Status:** 🎯 Todo
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

**As a** web visitor, **I want** the bottom bar (Get the app / Privacy / Terms / Changelog) to be
reachable from the chat page, **so that** I can get to the legal pages and the app link.

**Why P1:** `layout.tsx:107-111` renders `<Footer />` *after* a `flex-1` slot, while
`ChatIsland.tsx:938` gives the chat `h-dvh` — the full dynamic viewport. The footer therefore sits
exactly one footer-height below the fold, and the chat's own `overflow-y-auto` scroller
(`ChatIsland.tsx:1035`) swallows the gestures that would reach it. On mobile `100dvh` tracks the
browser chrome, so it keeps sliding away. Privacy and Terms are legally required disclosures; a nav
surface that never appears on screen is the same as not having one. Chat-page-only — short pages are
unaffected.

**Acceptance Criteria (summary):**

- [ ] Footer links reachable without a document scroll at 360×640, 390×844, 768×1024, 1440×900
- [ ] Composer stays visible with the mobile keyboard open; no horizontal scroll; RTL correct
- [ ] Bottom region decrowded (collapsed contact form, one promo element at a time)
- [ ] Playwright viewport regression test — a unit test cannot catch this

**Full Story:** `docs/BACKLOG_STORIES/BITB-079-web-bottom-bar-always-offscreen.md`

---

### 🎯 BITB-081: Android — Tapping an Example Question Must Send on the First Tap

**Status:** 🎯 Todo
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

**As an** Android user tapping an example question on the welcome screen, **I want** it sent
immediately, **so that** I get an answer from one tap instead of finding the text silently pasted
into the composer.

**Why P1:** This is the app's first interaction. `ChatScreen.kt:370-382` only sends when
`isTurnstileReady` is true — which on a cold start it usually is not while the welcome screen is
showing — so the tap becomes a silent paste with no feedback. The guard is unnecessary:
`TurnstileInterceptor` already waits for a token, proceeds without one, and retries once on 403
(`TurnstileInterceptor.kt:28-79`). Web already sends on tap.

**Acceptance Criteria (summary):**

- [ ] Tapping an example on a cold start (no token yet) sends and starts streaming
- [ ] Tapped text never remains in the input field; no second tap ever needed
- [ ] Failures surface the normal error state — never silence
- [ ] Compose UI test with `isTurnstileReady = false` asserts `sendMessage` is invoked

**Full Story:** `docs/BACKLOG_STORIES/BITB-081-android-example-prompt-sends-on-tap.md`

---

### ✅ BITB-089: Deploy Alembic Migrations from CI — Make the Framework Actually Load-Bearing

**Status:** ✅ Done (2026-08-15)
**Size:** M
**Depends on:** BITB-004 (PR #948) — merged, but **inert** until this shipped
**Unblocks:** BITB-090, BITB-091 — both now unblocked

**As a** maintainer who has just merged the Alembic framework, **I want** a committed revision to
actually reach the production database on deploy, **so that** "we have a migration system" is a
true statement rather than a framework nobody is wired to.

BITB-004 deliberately did not touch production or the deploy pipeline. Two consequences: prod has
no `alembic_version` table (so `upgrade head` would fail there today), and the deploy path filter
watches `scripts/migrations/**` only (`.github/workflows/azure-deploy.yml:167`) — so a revision
under `api/alembic/versions/**` **silently never deploys**. No error, no warning.

**Acceptance Criteria (summary):**

- [x] `alembic check` against a *restored copy* of prod passes — the gate for everything else.
      It initially **failed**, which is what BITB-093 exists for; clean after that reconciliation.
- [x] Prod stamped at `r0001` (zero DDL); `alembic current` reports `r0001`, and `alembic check`
      against production itself reports "No new upgrade operations detected."
- [x] Deploy workflow: path filter includes `api/alembic/versions/**`, job installs
      `api/requirements.txt`, and `alembic upgrade head` runs after the legacy call (PR #974)
- [x] SSL form resolved — `get_async_database_url()` now strips `ssl` as well as `sslmode`;
      covered by `api/tests/test_database_church_coverage.py::TestGetAsyncDatabaseUrl`
- [x] **Proven end-to-end.** The `r0002` probe revision (PR #987) reached production through the
      pipeline on 2026-08-15: the `run-migrations` job ran rather than skipping — the first time
      the `api/alembic/versions/**` filter has ever fired — and its "Run Alembic migrations" step
      succeeded against production. Not inferred from the YAML.
- [x] Rollback path documented for a mid-deploy `upgrade head` failure — see
      `docs/MIGRATION_GUIDELINES.md`

**Remaining tidy-up (not blocking):** `r0003` removes the probe's table comment from `sessions`.

**Full Story:** `docs/BACKLOG_STORIES/BITB-089-deploy-alembic-migrations-from-ci.md`

---

### ✅ BITB-093: Reconcile the Production Schema with the ORM Models

**Status:** ✅ Done (2026-08-15) — production reconciled and verified; `alembic check` against
production reports "No new upgrade operations detected."
**Size:** M
**Blocked:** BITB-089 Stage 2 (stamping production) — now unblocked and done

**As a** maintainer about to make Alembic authoritative, **I want** production's schema and the ORM
models to agree, **so that** `alembic stamp r0001` is a true statement rather than a promise the
next `--autogenerate` will contradict.

BITB-089 Stage 1 did its job: `alembic check` against a restored copy of production returns a
non-empty diff, so `r0001` does not describe production and must not be stamped over. Production's
`verses` was created by `create_all()` from an older model revision (nullable FK columns, a
Postgres-generated unique constraint name, no FK delete action) and later extended by hand-rolled
SQL — BITB-090's "two competing schema authorities" as a measured fact.

**Acceptance Criteria (summary):**

- [ ] Seven columns gain `server_default=` in the models (production is right there); `r0001` matches
- [ ] `scripts/reconcile-prod-schema.sql` brings production to the models: NOT NULL, constraint
      renames (rename, never DROP + ADD), FK delete action, stray comment removal
- [ ] Rehearsed against a restored copy **with data** before production
- [ ] `make db-rehearse-alembic` clean against a fresh copy, then BITB-089 Stage 2 proceeds
- [ ] Follow-up filed for the `compare_type=False` blind spot (type drift is invisible to `check`)

**Full Story:** `docs/BACKLOG_STORIES/BITB-093-reconcile-prod-schema-with-orm-models.md`

---

### 🎯 BITB-100: Make the Migration-Safety Rules Enforceable, Not Aspirational

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S–M

**As** the maintainer, **I want** the outage retrospective's process rules in checked documents
and CI assertions, **so that** the next migration is safe by construction, not by memory.

Covers what BITB-097 (pipeline) does not: a "Locking & scale" section in MIGRATION_GUIDELINES
(lock level + production-scale duration stated per revision; rewriting DDL banned from CI;
new-code-old-schema as default), a conditional migration checklist in the PR template, a CI check
that new revisions set `lock_timeout`, and the benchmark-before-build rule in CONTRIBUTING.

Retrospective: `docs/RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md`

**Full Story:** `docs/BACKLOG_STORIES/BITB-100-adopt-migration-safety-rules-from-retrospective.md`

---

### 🎯 BITB-099: Production Postgres Connections Encrypt but Do Not Authenticate the Server

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S–M

**As** the operator of a Postgres server with `public_network_access_enabled = true`, **I want**
the application and migration connections to verify the server's certificate, **so that** TLS
protects against an active attacker and not only a passive one.

`sslmode=require` resolves to `check_hostname = False` and `verify_mode = CERT_NONE` in both
`get_async_database_url()` and `get_migration_connection_params()` — verified by evaluating both
against the production URL. Traffic is encrypted but the server is unauthenticated: any
certificate, any server, any hostname is accepted, against an internet-reachable endpoint.

This is **deliberate** — it is what `sslmode=require` means in libpq, and BITB-016 chose it
knowingly. What is missing is anyone having decided it is *acceptable*. The story forces that
decision: move to `verify-full` with the Azure CA bundle, or keep `require` and record the threat
model. Not an Alembic issue; filed separately.

**Full Story:** `docs/BACKLOG_STORIES/BITB-099-postgres-tls-does-not-verify-the-server.md`

---

### 🎯 BITB-098: Retire the Two English FTS Indexes Nothing Queries

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the GIN indexes no query reads
to stop being maintained on every write, **so that** seeding and future backfills stop paying to
update structures nothing will ever scan.

`scripts/migrations/003` created four GIN indexes. Grepping the repo for
`to_tsvector('english', …)` returns exactly two hits — the two `CREATE INDEX` statements that
define `idx_verses_fts_english` and `idx_passages_fts_english`. Nothing else builds an `english`
tsvector, so no query can match either index.

**`idx_verses_fts_simple` must not be dropped** — that was BITB-095 Phase 2, cancelled on the
measurement (0.105 ms against 0.144 ms through `verse_tsv`). This story covers only the two
`_english` indexes, and requires `pg_stat_user_indexes.idx_scan` evidence from production before
dropping anything: a grep proves no reader in this repo, not that nothing has ever queried them.
Drop with `DROP INDEX CONCURRENTLY` inside an `autocommit_block()` — a plain `DROP INDEX` takes
`ACCESS EXCLUSIVE` on `verses` and queues every reader behind it.

**Full Story:** `docs/BACKLOG_STORIES/BITB-098-retire-unused-english-fts-indexes.md`

---

### 🚧 BITB-097: The Deploy Pipeline Cannot Be Trusted With Migrations

**Status:** 🚧 In Progress — PR #1005 open, pending CI + review
**Priority:** P1 — five defects, each independently capable of causing or hiding an outage
**Size:** M
**Prompted by:** the 2026-08-17 outage (BITB-096) and the 2026-08-18 deploy that never fired

**As** the operator of a single-maintainer production service, **I want** the deploy pipeline to
run migrations before the code that needs them, to bound them from the database, and to actually
fire when I merge, **so that** a schema change cannot take the site down for 45 minutes and a
merged fix cannot silently never reach production.

BITB-096 fixed the migration, not the pipeline. All five defects below are still live; yesterday's
migration was safe only because it was written defensively.

1. `deploy` runs **before** `run-migrations`, so new code is live before its schema exists.
2. `functional-tests` needs only `deploy`, so it races the migration — all 33 failures it
   reported on 2026-08-17 were unavoidable.
3. A CI `timeout-minutes` kills the client, not the server-side DDL, which held its lock a
   further 15 minutes with no possible commit. Only the database can bound the database.
4. `azure-deploy.yml` has **no `push` trigger**; it fires on `workflow_run` after
   "CI/CD - Test Application", whose paths exclude `deployment/**`. #1002 merged and never
   deployed.
5. The `production` gate had **16 runs queued, oldest from 11 August**, and there is no
   `concurrency` group. On 2026-08-17 `deploy` was approved and `run-migrations` was not — the
   gate's partial application *caused* the outage rather than preventing it.

**Acceptance Criteria (summary):**

- [x] `deploy` depends on `run-migrations`, plus the expand/contract rule that ordering requires
      documented in `docs/MIGRATION_GUIDELINES.md` (PR #1005)
- [x] `functional-tests` depends on both; `lock_timeout`/`statement_timeout` set at job or role
      level, below `timeout-minutes` (PR #1005 — via code, not a `PGOPTIONS` env var: asyncpg
      doesn't read it, see PR description)
- [x] `deployment/**` and `azure-deploy.yml` itself added to `test_update.yml`'s trigger paths
      (PR #1005); the end-to-end proof (a Terraform-only change actually deploying) is only
      verifiable post-merge, not attempted in the PR
- [x] `concurrency` group with `cancel-in-progress: false` (true would cancel a live migration)
      (PR #1005)
- [ ] Stranded `waiting` runs cleared and a decision recorded on the approval gate — deliberately
      left to the operator; PR #1005 does not touch the approval gate or any pending approval

**Full Story:** `docs/BACKLOG_STORIES/BITB-097-deploy-pipeline-cannot-be-trusted-with-migrations.md`

---

### ✅ BITB-096: Persist the Verse Tsvector in a `verse_tsv` Side Table

**Status:** ✅ Done (2026-08-18)
**Size:** M
**Supersedes:** the generated-column form of `r0004` (BITB-062 / PR #955)

**As** the operator of a 2-vCPU/4GB production Postgres, **I want** the persisted verse tsvector to
land without rewriting the `verses` table, **so that** BITB-095 can stop recomputing
`to_tsvector('simple', text)` per row without a repeat of the 2026-08-17 outage.

`r0004` as merged added `verses.text_tsv` as a `STORED` generated column, which forces a full table
rewrite under `ACCESS EXCLUSIVE`. On ~400k production rows it was still running at 33 minutes; the
`run-migrations` job then hit its 30-minute timeout, which killed the client but left the DDL
holding its lock for another 15 minutes. Production was down ~45 minutes and recovered only by
cancelling the orphaned backend and rolling the image back. Production is still at `r0003`, so the
revision can be replaced in place.

The tsvector moves to a `verse_tsv(verse_id PK, text_tsv)` side table maintained by a trigger. No
rewrite, and — unlike the shadow-table and batched-`UPDATE` alternatives — no rebuild of
`idx_verse_embedding_hnsw` over 403,856 1536-dimension vectors. Measured on identical data: 6.3 ms
for the whole migration against 7.5 s for the `ALTER TABLE` alone, before production's ~40× wider
rows and throttled CPU.

**The justification is safety, not speed**, and the benchmark is why. Over 403,856 rows the
`ts_rank` sites get 11.5× faster (2.750 ms → 0.238 ms per hybrid query), but `search_verses_text`
is **37% slower** through the side table (0.105 ms → 0.144 ms) — `idx_verses_fts_simple` is an
expression index that already stores the computed tsvectors, so that lookup was never recomputing
anything. It therefore stays as it is, `verse_tsv.text_tsv` carries no index at all, and BITB-095
Phase 2 (dropping the expression index) is cancelled.

**Acceptance Criteria (summary):**

- [x] `r0004` rewritten in place, with `lock_timeout`/`statement_timeout` set inside the migration
- [x] `VerseTsv` ORM model; **no** tsvector column on `Verse`, so `select(Verse)` no longer depends
      on the migration having run — the coupling that made the outage total
- [x] `scripts/backfill_verse_tsv.py`: batched, resumable, idempotent, ends in `ANALYZE verse_tsv`
- [x] Benchmarked rather than assumed; `search_verses_text` left on the expression index
- [x] Verified against a real Postgres 16 at 403,856 rows, including downgrade and re-upgrade
- [x] Applied in production: `r0004 (head)`, 403,856 rows backfilled, expression parity true
- [x] Query switch landed on the two `ts_rank` sites; `search_verses_text` left on the
      expression index, BITB-095 Phase 2 cancelled

**Full Story:** `docs/BACKLOG_STORIES/BITB-096-verse-tsv-side-table.md`

---

### 🎯 BITB-094: Audit Column Types Against Production — the Blind Spot `alembic check` Cannot See

**Status:** 🎯 Todo
**Size:** S–M
**Depends on:** BITB-093 (structural reconciliation) — done

**As a** maintainer who has just made Alembic authoritative, **I want** to know whether production's
column *types* match the ORM models, **so that** "the schema is reconciled" is a complete statement
rather than one that quietly excludes a whole category of difference.

`api/alembic/env.py` sets `compare_type=False`, correctly — `Vector(dim)` is 1024 locally and 1536
in production, so type comparison would flap the CI gate forever. The cost is that it suppresses
**all** type comparison. Every `alembic check` run during BITB-089 and BITB-093, including the clean
one against production, compared structure and no types whatsoever. A `varchar(50)` vs `varchar(100)`
or a `timestamp` vs `timestamptz` would have passed silently.

A concrete candidate already exists: `translations.created_at` is `DateTime` (naive) while
`feedback.created_at` and `contact_submissions.created_at` are `DateTime(timezone=True)`.
`scripts/init.sql` agrees with the models, so it is probably faithful rather than drift — but that
is the standard this story replaces.

**Acceptance Criteria (summary):**

- [ ] Type comparison run against a schema-only copy of production, output in the PR
- [ ] Vector columns reported as expected-difference, not silently skipped
- [ ] Each finding classified: faithful-but-questionable vs genuine drift
- [ ] `translations.created_at` resolved explicitly, or documented as intentionally naive
- [ ] Any `ALTER TABLE ... TYPE` deferred to its own revision with a lock/rewrite assessment
- [ ] `api/alembic/README.md` invariant #2 states plainly that **no** type is ever compared

**Full Story:** `docs/BACKLOG_STORIES/BITB-094-audit-column-types-against-production.md`

---

### ✅ BITB-092: Fix Dev Stack `db-init` Migration Failure and Embedding Config Drift

**Status:** ✅ Done (2026-08-09)
**Size:** S

**As a** developer running `make docker-up-dev`, **I want** `db-init` to successfully run
migrations and embedding config to match the main local stack, **so that** local dev testing
works out of the box.

`db-init` in `docker-compose.dev.yml` lacked the `./api:/api:ro` mount that
`scripts/migrations/run_migrations.py` needs to import `api/config.py` (it resolves `../../api`
relative to itself), so migrations crashed with `ModuleNotFoundError: config`. Separately, `api`
was missing `EMBEDDING_DIMENSIONS` and `db-init` was missing `EMBEDDING_PROVIDER` /
`EMBEDDING_DIMENSIONS`, causing embedding config drift versus the main stack.

**Follow-up (same day):** `db-init` runs as non-root UID 1000 while the host-owned `./data` bind
mount can be a different host UID, so `scripts/load_bible.py` downloaded KJV successfully but then
crashed with a `PermissionError` writing it back into `./data`. Fixed by mounting `./data:/data:ro`
in both compose files and adding an optional `BIBLE_DOWNLOAD_CACHE_DIR` env var
(`scripts/load_bible.py`'s `resolve_bible_data_path()`) that redirects first-run downloads to a
writable container path (`/tmp/bible-translations`) while committed source files (including
manual-only Hindi/Luther data) still always win when present.

**Acceptance Criteria (summary):**

- [x] `db-init` mounts `./api:/api:ro`, matching `docker-compose.yml`'s reference contract
- [x] `api` and `db-init` both set matching `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` /
      `EMBEDDING_DIMENSIONS` defaults (`ollama` / `mxbai-embed-large` / `1024`)
- [x] Regression test in `api/tests/test_docker_compose_dev.py`, collected by the standard API suite
- [x] No production files changed
- [x] `db-init` mounts `./data:/data:ro` (read-only) in both `docker-compose.yml` and
      `docker-compose.dev.yml`, and sets `BIBLE_DOWNLOAD_CACHE_DIR=/tmp/bible-translations`, so a
      fresh `docker-up`/`docker-up-dev` can download KJV without a host-UID-mismatch
      `PermissionError`, with no chmod/chown/root workaround
- [x] Committed manual-only translations (Hindi, Luther 1912) remain loadable from the read-only
      primary path unchanged
- [x] Regression tests in `api/tests/test_load_bible_data_path.py` and
      `api/tests/test_docker_compose_bible_cache.py`

**Full Story:** `docs/BACKLOG_STORIES/BITB-092-fix-dev-db-initialization.md`

---

## P2 - Medium Priority (Backlog)

> **Beta-tester feedback batch (Oliver Osthoever, 2026-06-11/12) → BITB-045…050.**
> Six stories captured from a German beta tester's usage notes: typo tolerance, more
> German Bibles, copy-prompt, keyboard dismissal, fresh-chat-on-launch, and thematic
> search/response depth.

### ✅ BITB-069: Splash-Screen Cookie Check Causes SSR/CSR Hydration Mismatch

**Status:** ✅ Done (PR #917, pending merge)
**Size:** S (< 4 hrs)
**Created:** 2026-07-16

**As a** returning visitor, **I want** the page to render consistently between the server-sent
HTML and the client's first paint, **so that** the browser console stays clean and the app doesn't
silently discard and re-render the entire tree on every load.

**Why P2:** Found while manually testing PR #840 locally (unrelated — that PR touches zero
frontend files). `frontend/src/app/[locale]/providers.tsx:76` seeds `splashDone` from a lazy
`useState(() => hasSplashCookie())`. The server always renders `splashDone = false` (no
`document` during SSR), but for a **returning visitor** the client's real hydration-pass read of
`document.cookie` can see `splash_seen=1` from a prior visit and render `splashDone = true` instead
— server and client trees disagree, and React logs a hydration-mismatch error and re-renders the
whole tree client-side. First-time visitors don't trigger it (both sides agree on `false`), which
is likely why it wasn't caught earlier. Not user-blocking today, but it's a real SSR/CSR divergence
worth fixing, not just console noise.

**Acceptance Criteria:**

- [x] No hydration-mismatch error/warning on load for a returning visitor (cookie already set)
- [x] First-time visitor still sees the full splash screen unchanged
- [x] Returning visitor doesn't see a visible splash flash before it's skipped

**Full Story:** `docs/DONE/BITB-069-splash-screen-hydration-mismatch.md`

---

### ✅ BITB-055: Scripture/Chat Pipeline Observability — Fail Loud, Not Silent

**Status:** ✅ Done — shipped mostly under PR #910 (untracked at the time); this pass closed the
remaining gap plus test coverage
**Size:** M (1-2 days)
**Created:** 2026-06-20

**As the** operator, **I want** the scripture/chat pipeline to emit explicit failure and
degradation signals (metrics, alerts, synthetic checks) instead of swallowing errors and serving a
verse-less answer, **so that** a broken search/grounding path is detected in minutes, not weeks.

**Why P2:** A misplaced `# nosec` broke all DB-backed verse retrieval for ~2 weeks with zero alerts
(fixed in PR #764). The pipeline fails open through three `except` blocks, monitoring is reactive
log-scraping the bug slipped through twice, no metric distinguished "served with verses" from
"served empty," and CI never executes the real SQL. This hardens the whole class of failure.

**Acceptance Criteria (summary — full story has detail):**

- [x] Explicit error counters in the three `except` paths; alert on the metric, not log text
- [x] Business SLI: rate of responses served with zero DB verses / zero resolved citations
- [x] End-to-end synthetic check that the chat path returns cited/grounded verses
- [x] Log-scan robustness (structured levels + allowlist, not a hand-kept keyword denylist)
- [x] Fail loud (guard/CI check) when prod alerting is disabled
- [x] Integration test running the real search/grounding SQL against the Postgres service container

**Full Story:** `docs/DONE/BITB-055-scripture-pipeline-observability.md`

---

### 🎯 BITB-045: Typo-Tolerant Queries with Clarification Fallback

**Status:** 🎯 Todo
**Size:** S (< 4 hrs)
**Created:** 2026-06-12

**As a** user who makes spelling mistakes (especially in German), **I want** the app to interpret my
likely intended meaning, **so that** "reichsheilugtm bet el" is answered as "Reichsheiligtum Bet-El"
instead of a generic "I don't understand".

**Acceptance Criteria (summary):**

- [ ] Obvious typos are silently interpreted and answered; no remark about the misspelling
- [ ] Genuinely ambiguous queries get one short clarifying question in the user's language
- [ ] Typo guidance present in all three chat system prompts; test asserts it for German

**Full Story:** `docs/BACKLOG_STORIES/BITB-045-typo-tolerant-queries.md`

---

### 🎯 BITB-046: Add German Bible Translation (Luther 1912)

**Status:** 🎯 Todo
**Size:** M (1-2 days, mostly data loading)
**Created:** 2026-06-12

**As a** German-speaking user, **I want** a familiar Bible translation (Luther), **so that** I'm not
limited to Schlachter 1951. Luther 1984/2017, Einheitsübersetzung, NGÜ, and Schlachter 2000 are
copyrighted; **Luther 1912** is public domain (shipped as a committed data file — getBible does not
host it). Elberfelder was dropped: getBible only offers the archaic 1905 edition, and Luther 1912
covers the need while saving a full Bible's worth of verses/embeddings in the DB.

**Acceptance Criteria (summary):**

- [ ] German picker shows Luther 1912 (default), Schlachter 1951
- [ ] Text + embeddings loaded and searchable for Luther 1912
- [ ] German-default assertions updated `schlachter` → `luther1912`; all tests pass

**Full Story:** `docs/BACKLOG_STORIES/BITB-046-german-translations-luther-elberfelder.md`

---

### 📋 BITB-068: Refresh & Expand Bible Translations from Bible SuperSearch

**Status:** 📋 Backlog
**Size:** M (1-2 days, mostly data loading + registration)
**Created:** 2026-07-10

**As a** reader, **I want** additional and more current Bible translations — starting with Italian —
**so that** I can read Scripture in more contemporary wording and compare versions, instead of a single
century-old translation per language. Source: Bible SuperSearch JSON collection. Bounded by licensing —
only public-domain / freely redistributable texts (NIV, ESV, CEI 2008 excluded).

**Acceptance Criteria (summary):**

- [ ] Italian gets a second option (e.g. Diodati) alongside Riveduta 1927
- [ ] Add newer free options where clearly licensed: Reina Valera 2010 (es), Ostervald 1996 / l'Épée
      2005 (fr), NET Bible (en); each license-verified before import
- [ ] Each new translation loaded (text + embeddings), book-name coverage clean, and selectable via
      `/scripture/translations`; provenance/license note recorded

**Full Story:** `docs/BACKLOG_STORIES/BITB-068-refresh-and-expand-bible-translations.md`

---

### 🎯 BITB-047: One-Tap Copy of the User's Prompt (Web + Android)

**Status:** 🎯 Todo
**Size:** S (< 4 hrs)
**Created:** 2026-06-12

**As a** user, **I want** a one-tap button to copy just my prompt text, **so that** I can paste it
into another tool (e.g. Perplexity) without copying the whole Q&A. Extends the prior Android
selection-only story with an explicit button and web support.

**Acceptance Criteria (summary):**

- [ ] Copy icon on user bubbles (web + Android) copies only the raw question text
- [ ] Web shows a checkmark ~2 s; Android shows a Toast; no new Android string resources
- [ ] Assistant copy/share controls unchanged

**Full Story:** `docs/BACKLOG_STORIES/BITB-047-copy-user-prompt-button.md`

---

### 🎯 BITB-048: Auto-Dismiss Keyboard After Sending a Message (Android)

**Status:** 🎯 Todo
**Size:** S (< 1 hr)
**Created:** 2026-06-12

**As an** Android user, **I want** the keyboard to disappear after I tap Send, **so that** I can see
the full response without manually dismissing it.

**Acceptance Criteria (summary):**

- [ ] Keyboard collapses immediately after Send via `focusManager.clearFocus()`
- [ ] Multi-line input (Enter = newline) unchanged; Stop icon while streaming unchanged

**Full Story:** `docs/BACKLOG_STORIES/BITB-048-android-dismiss-keyboard-on-send.md`

---

### 🎯 BITB-049: Always Start with a Fresh Chat on App Launch (Android)

**Status:** 🎯 Todo
**Size:** S (< 1 hr)
**Created:** 2026-06-12

**As an** Android user, **I want** the app to open a new empty chat on every launch, **so that** I
begin fresh instead of landing in my last conversation (history stays reachable via the drawer).

**Acceptance Criteria (summary):**

- [ ] App launch always lands on `chat/new`; drawer still lists/loads past conversations
- [ ] `LastConversationPreferences` / `resolveResumeConversationId()` retained for a future toggle

**Full Story:** `docs/BACKLOG_STORIES/BITB-049-android-fresh-chat-on-launch.md`

---

### 🚧 BITB-051: Android Contact Form Shows "Message Too Long" When the Real Problem Is the (Required) Email

**Status:** 🚧 In Progress
**Size:** S (< 4 hrs)
**Created:** 2026-06-15

**As an** Android user submitting the contact form, **I want** an accurate error that names the
email field when my submission is rejected, **so that** I'm not misled into thinking my message was
too long.

**Acceptance Criteria (summary):**

- [ ] Android: a missing/invalid-email 422 shows an email-specific error, never the "max 300 characters" message
- [ ] Android: the chat message-length 422 still maps to `error_message_too_long`
- [ ] Android: email validated as required (no blank→null); `contact_email_label` updated from "optional" in all locales
- [ ] Tests: `ChatViewModelTest` pins the 422 split; web has no equivalent bug (verified — optional follow-up only)

**Full Story:** `docs/BACKLOG_STORIES/BITB-051-android-contact-form-misleading-validation-error.md`

---

### 🚧 BITB-043: Require Contact Email + Full Feedback Email Content + Negative-Feedback Reason Chips

**Status:** 🚧 In Progress
**Size:** M (1-2 days)
**Created:** 2026-06-08

**As a** user submitting a contact form or leaving feedback,
**I want** to be prompted for my email (so the team can actually reply) and to quickly label
what went wrong on a thumbs-down with a single-tap reason chip,
**so that** the team can follow up and act on precise, categorised feedback.

**Acceptance Criteria:**

- [ ] POST `/api/v1/feedback/contact` without email → HTTP 422 (email is required)
- [ ] POST `/api/v1/feedback/contact` with invalid email → HTTP 422
- [ ] Contact form send button disabled when email is empty; input has `required`
- [ ] `Contact.emailLabel` updated to required phrasing in all 11 locales
- [ ] Negative feedback email includes full (untruncated) user message and AI response + HTML + metadata
- [ ] Positive feedback WITH comment triggers maintainer email; bare positive does not
- [ ] Thumbs-down panel shows 5 reason chips; selected chip passed as `reason` to `onSubmit`
- [ ] Chip selection is optional — auto-commit still works without it
- [ ] `reason` column added to `feedback` table (migration 006)
- [ ] All 11 locales have 6 new reason keys + updated `emailLabel`
- [ ] Backend + frontend tests pass

**Full Story:** `docs/BACKLOG_STORIES/BITB-043-require-contact-email-and-actionable-negative-feedback.md`

---

### 🚧 BITB-044: Populate `verse_topics` to Activate Topic Boosting

**Status:** 🚧 In Progress — keyword-based population shipped; LLM tagging, golden-set
tuning, and prod enablement remain. See `docs/BACKLOG_STORIES/BITB-044-populate-verse-topics.md`.
**Size:** M (1-2 days)
**Created:** 2026-06-07

**As a** user, **I want** verses matching my detected theme to rank higher, **so that** the
most pastorally relevant verses surface first.

**Why P2:** Topic boosting was built under BITB-018 (detection in `api/chat/topics.py`,
ranking boost, repository joins on `verse_topics`, schema in migration `004`) but
**`verse_topics` is never populated** — no `INSERT` exists anywhere, so the feature is a
silent no-op. This story tags the corpus (~31k verses) against the 13 topics via a
repeatable population script, then validates and enables `topic_boosting_enabled`. P2
because it's data work gated behind BITB-043's eval set, not a live regression.

**Acceptance Criteria (summary — full story has detail):**

- [ ] Idempotent population script writes `(verse_id, topic_id)` rows; re-runnable
- [ ] Coverage + spot-check accuracy recorded across the 13 topics
- [ ] With boosting on, topic-laden golden queries improve; neutral queries don't regress
- [ ] `topic_boost_factor` tuned + documented; topic boosting enabled in prod

**Full Story:** `docs/BACKLOG_STORIES/BITB-044-populate-verse-topics.md`

---

### 🚧 BITB-042: Feedback "Rethink" Delay + Explicit Maintainer-Sharing Notice on Thumbs-Down

**Status:** 🚧 In Progress (web implemented; Android/iOS parity open)
**Size:** M (1-2 days)
**Created:** 2026-06-05

**As a** person who taps thumbs-up or thumbs-down on an AI answer,
**I want** a short (~10-second) window to reconsider/undo my rating before it commits, and a clear, short notice — right when I tap thumbs-down — that my message will be shared with the app's maintainer,
**so that** I don't lock in a mis-tap, and I'm genuinely aware (not just via the buried Terms of Use) that a negative comment goes to a real person.

**Why P2:** Today a rating is acted on the instant it's tapped (`ChatMessage.tsx` calls `onFeedback()` on click, buttons then lock) — no undo. And the only disclosure is a generic "logged" line (`Feedback.privacyNotice`), even though thumbs-down feedback is actually emailed to the maintainer (`api/utils/email_service.py`; routed per BITB-032). Product wants in-context transparency plus a chance to reconsider.

**Acceptance Criteria:**

- [ ] After tapping a thumb, no request is sent for ~10s; inline countdown + Undo shown
- [ ] Undo / re-tap / switch within the window cancels — verified no feedback POST is made
- [ ] After the window, the rating commits (POST sent) — no forced modal; comment is optional and inline
- [ ] Thumbs-down shows a short explicit "shared with the app's maintainer" notice next to the comment field, separate from the logging notice
- [ ] New i18n key(s) added to all 11 locales under `frontend/messages/`; `translations.test.ts` passes
- [ ] Countdown is accessible and honours `prefers-reduced-motion`; window length is a single named constant
- [ ] Tests cover pending/undo (no POST), timeout (POST sent), and thumbs-down notice

**Full Story:** `docs/BACKLOG_STORIES/BITB-042-feedback-rethink-delay-and-maintainer-notice.md`

---

### 🎯 BITB-036: Android Inline Amber Chip for Quoted Scripture — Web Parity

**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-05-26

**As a** user of the Android app, when an AI response quotes a Bible verse,
**I want** the quoted text to appear in an inline amber chip (same as the web app),
**so that** scripture stands out from commentary without breaking the prose flow.

**Acceptance Criteria:**

- [ ] Quoted scripture renders as an inline amber chip (amber-50 background, amber-600 left bar, amber-900 italic serif) without breaking the surrounding sentence
- [ ] All double-quoted text is highlighted — not only quotes adjacent to a verse link (matches web `highlightQuotes()` behaviour)
- [ ] Verse references remain bold amber links, tappable to open `VerseDetailBottomSheet`
- [ ] Soft-break rendering unchanged from current behaviour after library upgrade
- [ ] All CI checks pass (Unit Tests, Compose UI Tests, Android Lint, Build Prod APK)

**Full story:** [docs/BACKLOG_STORIES/BITB-036-android-inline-amber-quote-chip.md](BACKLOG_STORIES/BITB-036-android-inline-amber-quote-chip.md)

**References:** PR #629 (deferred amber styling), PR #619 (verse bold links), `ChatMessage.tsx → highlightQuotes()`

---

### 🎯 BITB-037: SEO Follow-ups — Server-Render Homepage, JSON-LD, OG Image

**Status:** 🚧 In Progress (server-render homepage confirmed done in code; JSON-LD + OG image landing 2026-07-03; only Search-Console submission remains, a manual operator action)
**Priority:** P1 for task 1 (server-render homepage); P3 for tasks 2–4
**Size:** M (server-render homepage needs care at the client/server boundary; rest are small)
**Created:** 2026-05-29 · **Updated:** 2026-07-03

**As a** person searching for Bible inspiration on Google (or asking an AI assistant),
**I want** Vox Quieta's pages to be fully indexable — real server-rendered text, structured data, rich link previews,
**so that** the site can actually be discovered rather than served as an empty client-rendered shell.

**Live findings (2026-05-31):** `/en` renders 0 server-side words (homepage is `'use client'`) — only real remaining gap. `/favicon.ico` returned 404 and is fixed in the same PR. Cloudflare `/robots.txt` is fine: Cloudflare appends the origin's `Sitemap:` directive after its own managed AI-bot block, so the served body contains both.

**Acceptance Criteria:**

- [x] **(P1)** Homepage hero text is server-rendered (live check shows `/en` is no longer thin); chat UI still hydrates (Turnstile, streaming, modals)
- [x] `/favicon.ico` returns 200 with the brand icon
- [x] Production `/robots.txt` contains `Sitemap: https://voxquieta.org/sitemap.xml` (verified)
- [x] `WebSite` + `Organization` JSON-LD present on all locales; `seo-static-check.sh` JSON-LD WARN clears
- [x] `og:image` resolves and Twitter card is `summary_large_image`
- [ ] Live check confirms `/sitemap.xml` 200, `/icon.svg` and `/favicon.ico` resolve, `/en` has canonical+OG+Twitter, `/en/privacy` hreflang points to `/it/privacy`; sitemap submitted to Search Console *(manual operator action remaining)*

**Full story:** [docs/BACKLOG_STORIES/BITB-037-seo-followups-server-render-homepage.md](BACKLOG_STORIES/BITB-037-seo-followups-server-render-homepage.md)

**References:** PR #636 (SEO metadata foundation, merged), `scripts/seo-static-check.sh`, `scripts/seo-live-check.sh`, `frontend/src/lib/seo.ts`

---

### 🎯 BITB-029: Surface Bible Version Information More Clearly

**Status:** 🎯 Todo
**Size:** S (< 4 hours)
**Created:** 2026-05-10

**As a** user reading AI answers with verse references,
**I want** the active Bible version to be visible and easy to open,
**so that** I can quickly confirm which translation is being used.

**Acceptance Criteria:**

- [ ] Active Bible version is shown prominently in the chat experience (web and Android) near verse responses
- [ ] Tapping/clicking the version indicator opens or navigates to the existing Bible version information surface
- [ ] If a user asks "which Bible version are you using?" (or equivalent), the assistant points them to the Bible version information location
- [ ] The "point back to version info" behavior is applied consistently across supported locales
- [ ] No change to scripture retrieval logic; this story focuses on visibility and response guidance only

**Full Story:** `docs/BACKLOG_STORIES/BITB-029-surface-bible-version-information.md`

---

### 🎯 BITB-026: Android Settings UX Improvements

**Status:** 🎯 Todo
**Size:** S (< 4 hours)
**Created:** 2026-05-08

**As an** Android user,
**I want** the Settings screen to be clean and purposeful,
**so that** I can find global preferences quickly without redundant controls that already exist in the chat screen.

**Problem:** The Settings screen duplicates the Bible translation picker that already exists as an in-chat bottom sheet. Both write to the same DataStore key, making the Settings version redundant and the page unnecessarily long.

**Acceptance Criteria:**

- [ ] Bible translation radio-button list removed from `SettingsScreen.kt`
- [ ] Read-only "Current translation" row added with a "Change from the chat screen" hint
- [ ] "Clear conversation history" button added with confirmation dialog (new Data & Privacy section)
- [ ] Settings sections reordered: Appearance → Bible → Data & Privacy → Support → Contact → About
- [ ] In-chat translation chip still persists selection across restarts (no regression)
- [ ] All existing preference unit tests pass

**Full Story:** `docs/BACKLOG_STORIES/BITB-026-android-settings-improvements.md`

---

### 🎯 BITB-006: Add Staging Environment

**Status:** 🎯 Todo
**Size:** L

**As a** product owner,
**I want** a staging environment that mirrors production,
**so that** we can validate changes before they affect real users.

**Acceptance Criteria:**

- [ ] Terraform workspace or separate config for staging
- [ ] Staging environment deployed to Azure with same services as prod
- [ ] Staging uses separate database with test data
- [ ] CI/CD deploys to staging on merge to `main`, production on tag/release
- [ ] Staging URL accessible to team (e.g., `staging.getinspiredbythebible.ai4you.sh`)
- [ ] Documentation includes staging deployment process

**Tech Constraints:**

- Must minimize cost (use lower-tier resources than prod)
- Must share same codebase as production
- Must support Terraform state isolation

**Out of Scope:**

- Automated promotion from staging to production
- Staging database anonymization (can use fresh Bible data)

**Related:** TASKS.md #6.2

---

### 🎯 BITB-007: Improve Embedding Generation Performance

**Status:** 🎯 Todo
**Size:** M

**As a** developer running `create_embeddings.py`,
**I want** embedding generation to be parallelized,
**so that** the 30-60 minute task completes in under 10 minutes.

**Acceptance Criteria:**

- [ ] `embed_batch()` uses `asyncio.gather()` with semaphore
- [ ] Configurable concurrency limit (default: 10)
- [ ] Partial results saved if batch fails mid-way
- [ ] Progress bar shows accurate completion estimate
- [ ] Documentation updated with new timing estimates

**Tech Constraints:**

- Must not overwhelm Ollama server (hence semaphore)
- Must work with existing Ollama provider
- Must handle failures gracefully (no silent data loss)

**Out of Scope:**

- Switching embedding providers
- Caching embeddings (separate story)

**Related:** TASKS.md #1.2

---

### ✅ BITB-008: Add Request Tracing with Correlation IDs

**Status:** ✅ Done
**Size:** S

**As a** developer debugging production issues,
**I want** every request to have a unique trace ID,
**so that** I can follow a single user's request through logs.

**Acceptance Criteria:**

- [x] Middleware generates UUID for each request (`api/middleware/correlation_id.py`)
- [x] `X-Request-ID` header added to all responses, including error responses
- [x] Trace ID logged in every log entry for that request (`api/utils/logging_config.py`)
- [x] Trace ID propagated to database queries as a SQL comment (`before_cursor_execute` listener
      in `api/scripture/database.py`)
- [x] Documentation includes how to search logs by trace ID (`docs/TROUBLESHOOTING.md`,
      "Tracing a single request by its correlation ID")

**Tech Constraints:**

- Must work with existing logging configuration
- Must have minimal performance impact
- Must handle both sync and async endpoints

**Out of Scope:**

- Full OpenTelemetry integration (separate story)
- Distributed tracing across services

**Related:** TASKS.md #5.1

---

### 🎯 BITB-009: Refactor SQLAlchemy Models to 2.0 Syntax

**Status:** 🎯 Todo
**Size:** L

**As a** developer,
**I want** SQLAlchemy models to use `Mapped[]` annotations,
**so that** MyPy can type-check database code and we remove `# type: ignore` comments.

**Acceptance Criteria:**

- [ ] All models in `api/scripture/models.py` use `Mapped[]` syntax
- [ ] MyPy suppressions removed from `scripture/*` and `routes/*`
- [ ] All tests pass with no type errors
- [ ] Database queries still work correctly
- [ ] Documentation updated with new model syntax examples

**Tech Constraints:**

- Must maintain compatibility with existing database schema
- Must work with AsyncPG
- Must not break existing queries in `repository.py`

**Out of Scope:**

- Migrating to SQLAlchemy 2.0 declarative base (can use hybrid syntax)
- Rewriting all queries to use new-style syntax

**Related:** TASKS.md #3.3, TECHNICAL_DEBT.md #1

---

### 🎯 BITB-074: "Support Us" Funding Entry Points (Web, Android, GitHub)

**Status:** 🎯 Todo
**Size:** M (4–8 hrs, excluding manual Ko-fi/GitHub Sponsors account setup)
**Created:** 2026-07-21

**As a** supporter of Vox Quieta, **I want** a clear, low-friction way to
financially support the project from the website, the Android app, and the
GitHub repo, **so that** I can help cover hosting/LLM inference costs, without
the app ever touching payment data itself.

Research compared GitHub Sponsors, Ko-fi, Buy Me a Coffee, Patreon, Open
Collective, Stripe Payment Links, and PayPal. Recommendation: **Ko-fi**
(0% platform fee, one-time + recurring, supports Stripe and PayPal checkout)
as the primary user-facing donation page, plus **GitHub Sponsors** enabled on
the repo for the developer audience. Both are pure external link-outs — no
feature is gated or unlocked in exchange for donating, keeping this out of
Google Play Billing scope (to be re-verified against the current Play
Developer Program Policy before shipping).

**Acceptance Criteria (summary):**

- [ ] `.github/FUNDING.yml` added (GitHub Sponsors + Ko-fi)
- [ ] Web `Footer.tsx` gets a "Support us" link to the Ko-fi page; new
      `Footer.supportUs` key added across all 10 locale files
- [ ] Android `SettingsScreen.kt` gets a "Support Vox Quieta" row in the About
      section, opening the donate URL via `LocalUriHandler`
- [ ] No payment data/webhooks handled by Vox Quieta's own code; no perks
      gated behind the donation

**Full Story:** `docs/BACKLOG_STORIES/BITB-074-support-us-funding.md`

---

### 🎯 BITB-076: "About" Page — Why Vox Quieta Exists

**Status:** 🎯 Todo
**Size:** M (1–2 days, mostly copywriting + 11 locales)
**Created:** 2026-07-25

**As a** visitor who has just found Vox Quieta, **I want** to read who built this and why, **so
that** I can decide whether to trust a chatbot with something as personal as my faith and my grief.

The site answers "what are you doing with my data" (privacy, terms) but never "why does this exist
and who made it" — the question that actually earns the first message. The motivation is already
written: **["Building Something That Matters: How Claude Code Helped Me Create a Bible Inspiration
Chatbot"](https://ai4you.sh/posts/Building-Something-That-Matters-How-Claude-Code-Helped-Me-Create-a-Bible-Inspiration-Chatbot/)**
is the foundation and canonical reference for the page. New static localized route at
`/{locale}/about`, built like the existing `/app` page.

The post's motivation is the mental-health one — "something simple, accessible, and deeply rooted in
Scripture that could offer encouragement when someone needed it most. Not a replacement for therapy
or pastoral care, but a gentle companion for moments of struggle." Note that the post describes
**v1.0** and is now stale on the name, the stack and the language list (see the story's *Source
Material* section): it is the origin story to adapt, not text to transcribe.

**Acceptance Criteria (summary):**

- [ ] `/{locale}/about` renders for all 11 locales, server-rendered and statically generated
- [ ] Copy adapted from the ai4you.sh post, which is linked as the full story
- [ ] States plainly what Vox Quieta is *not* (not pastoral care, not counseling)
- [ ] Reflects the project as it is today; one sentence of continuity for the rename from
      "Get Inspired by the Bible" to "Vox Quieta"
- [ ] `About` namespace complete in all 11 `frontend/messages/*.json`; Arabic RTL correct
- [ ] Linked from the footer **and** from the chat screen; added to `sitemap.ts` `PATHS`

**Full Story:** `docs/BACKLOG_STORIES/BITB-076-about-page-motivation.md`

---

### 🎯 BITB-077: "Why Vox Quieta" Intro Modal — Once for Everyone Now, New Visitors Afterwards

**Status:** 🎯 Todo
**Size:** S (< 4 hrs, after BITB-076)
**Created:** 2026-07-25
**Blocked by:** BITB-076

**As a** person opening Vox Quieta, **I want** a short, dismissible introduction explaining who made
this and why, **so that** I know what I am talking to before typing something personal into it.

A page nobody clicks changes nothing, so the new message warrants one deliberate interruption — then
it belongs in the onboarding path only. Both halves of the mechanism already exist in the repo: the
one-time splash cookie (`providers.tsx:13-24`) and the show-once-per-version localStorage gate with
silent first-visit seeding (`WhatsNewModal.tsx:33-40`). A single versioned
`vq:aboutIntroSeen` key gives "everyone now, new visitors later" for free.

**Acceptance Criteria (summary):**

- [ ] Every visitor sees it exactly once after deploy; dismissal persists forever
- [ ] Never stacked on `SplashScreen` or `WhatsNewModal`; appears after the splash completes
- [ ] Copy from the `About` namespace in all 11 locales; primary action opens `/about`
- [ ] No SSR/CSR hydration mismatch (see BITB-069); keyboard accessible
- [ ] Bumping the version constant re-shows it — proven by a test

**Full Story:** `docs/BACKLOG_STORIES/BITB-077-about-intro-modal.md`

---

### 🎯 BITB-082: Android — About Settings Row + First-Run Intro Fold-In

**Status:** 🎯 Todo
**Size:** S (~1 day)
**Created:** 2026-07-27

**As an** Android user, **I want** to read who built Vox Quieta and why, from Settings, **so
that** I have the same answer web visitors get from `/about`. **As an** Android user opening the
app for the first time after this ships, **I want** the same one-time intro web users get,
**so that** I'm not left out without a fifth first-run interruption competing for attention.

BITB-076 and BITB-077 both excluded Android and pointed here. Part A links Settings → About out
to `voxquieta.org/{locale}/about`, the same external-link pattern already used for Privacy/Terms
(`SettingsScreen.kt:174-224`, `LegalUrls.kt`) — no native content duplication. Part B mirrors the
splash-cookie "seen once ever" pattern (`MainActivity.kt:51-57`), not the What's-New
per-version pattern, and requires making the What's New version-seen write conditional
(currently unconditional at `MainActivity.kt:121`) so the two sheets never render on the same
cold start — About intro wins, What's New defers to the next launch. Note: BITB-054 (first-run
spotlight), floated as an alternative fold-in target, is still `Todo` — not available today.

**Acceptance Criteria (summary):**

- [ ] Settings → About gets a third row opening `/about` in-language, same pattern as Privacy/Terms
- [ ] About intro sheet shows once ever per install; dismissal persists
- [ ] About intro and What's New never render on the same cold start; What's New's version-seen
      write becomes conditional so a deferred run re-evaluates next launch
- [ ] All new strings in `values/strings.xml` + all 11 `values-*/strings.xml`, sourced from the
      same copy as web's `About.intro*` keys — not re-derived independently

**Full Story:** `docs/BACKLOG_STORIES/BITB-082-android-about-settings-and-intro.md`

---

### 🎯 BITB-083: About Page — Personal Voice + Screenshots from the Origin Story

**Status:** 🎯 Todo
**Size:** M (~1 day, mostly copywriting + asset sourcing, ×11 locales)
**Created:** 2026-07-27

**As a** visitor reading `/about`, **I want** to feel a real person behind Vox Quieta, **so that**
the page earns the trust BITB-076 set out to earn — not read like a feature list.

Maintainer feedback after BITB-076/077 shipped: *"it looks like a feature description... make it
personal — add screenshots or renderings from the original post."* Concrete evidence: `About.todayBody`
("Scripture-grounded conversation... in 11 languages... free to use") reads exactly like the
`/app` marketing copy, and the post's own closing line — *"I'm just happy it exists... someone
having a rough day can visit that URL and find encouragement. That's what matters"* — was captured
in BITB-076's Source Material but never made it onto the shipped page. The post also has two real
app screenshots (`bible-chatbot-welcome-screen.png`, `bible-chatbot-response-example.png`), though
they show the pre-rename v1.0 UI — must be labeled as "then," not presented as current.

**Acceptance Criteria (summary):**

- [ ] `todayBody` no longer reads as a feature/spec list
- [ ] Opening hook ("Have you ever had an idea...") gets its own beat, including the dropped
      follow-up question
- [ ] A closing personal beat (adapted from "I'm just happy it exists...") lands before Get in touch
- [ ] At least one screenshot renders, labeled if origin-era
- [ ] `notBody`'s safety-boundary language stays unambiguous — not softened
- [ ] Applied across all 11 locales; `About.introBody` (BITB-077) rechecked for consistency

**Full Story:** `docs/BACKLOG_STORIES/BITB-083-about-page-personal-voice-and-photos.md`

---

### 🎯 BITB-078: Ask Before Answering — Clarify a Vague Request Instead of Guessing

**Status:** 🎯 Todo
**Size:** M (1–2 days, prompt work + eval)
**Created:** 2026-07-25

**As a** user who types something short and raw like "I'm lost", **I want** the companion to ask one
gentle question about what I'm facing, **so that** the answer speaks to my actual situation instead
of whatever the model guessed.

The worst failure mode for this product is sounding caring while addressing someone else's problem.
The instruction exists (`SYSTEM_PROMPT_TEMPLATE`, "## When the Request Is Unclear") but is
outweighed: "## Your Role" step 2 reads as an unconditional order to bring in a verse, the per-intent
addenda reinforce it, and scripture context is already retrieved and injected before the model is
asked whether it understood the question. This makes clarification a first-class intent
(`NEEDS_CLARIFICATION`) that skips retrieval, capped at one question per conversation.

**Acceptance Criteria (summary):**

- [ ] Vague openings get a warm one-question reply with no verse citation; search is skipped
- [ ] At most one clarifying question per conversation; specific messages never trigger one
- [ ] Never asked for verse lookups or `compassionate_response_needed` (crisis) turns
- [ ] Works across en/it/de/es; clarification rate logged so rollout can be judged
- [ ] Vague-opening cases added to the retrieval-eval harness (BITB-051)

**Full Story:** `docs/BACKLOG_STORIES/BITB-078-clarify-before-answering.md`

---

### 🎯 BITB-080: Suggested Follow-Up Questions as One-Tap Buttons Under Each Answer

**Status:** 🎯 Todo
**Size:** M (1–2 days, backend + web + Android)
**Created:** 2026-07-25

**As a** user who has just read an answer, **I want** two or three suggested next questions offered
as buttons, **so that** I can keep exploring without working out what to ask — or typing it on a
phone.

The welcome screen already proves the pattern works (tap a starter prompt, it sends), and it
disappears exactly when the user has the most to explore. The streaming `completion` event is the
natural carrier: it already grew `resolved_verses` and `corrections` as optional fields that older
clients ignore (`service.py:1375-1386`). v1 generates follow-ups in-prompt via a machine-readable
trailer, mirroring the existing `<!-- VERSES: -->` mechanism — no extra call, no extra latency.

**Acceptance Criteria (summary):**

- [ ] 2–3 chips under the **latest** assistant message only, in the user's language; tap sends
- [ ] Suppressed for off-topic, crisis-flagged and error turns; trailer never leaks into the answer
- [ ] Clients on an older backend are unaffected (absent field renders nothing)
- [ ] Shares one chip component with BITB-078; accessible on web and Android
- [ ] Interaction with the 10-message session limit (BITB-024) checked before rollout

**Full Story:** `docs/BACKLOG_STORIES/BITB-080-suggested-followup-questions.md`

---

### 🎯 BITB-084: iPhone-Ready Web — Installable PWA, Standalone Safe Areas, iOS Path on `/app`

**Status:** 🎯 Todo
**Size:** M (1–2 days)
**Created:** 2026-07-29

**As an** iPhone user, **I want** Vox Quieta to install to my home screen and behave like an app,
**so that** I open it like any other app instead of hunting for a browser tab.

**Why P2:** Stage 0 of the iOS plan and the only stage needing no Apple account, no Mac, and no new
codebase — worth shipping even if the native app never happens. Three concrete gaps today:
`frontend/public/` has no manifest or service worker; the safe-area CSS at `globals.css:57-62` is
**inert** because `[locale]/layout.tsx:46-50` omits `viewportFit: "cover"` (and becomes a real
overlap the moment the app runs standalone); and `/app` tells iPhone visitors, in 11 languages, to
"Get it on Google Play".

**Acceptance Criteria (summary):**

- [ ] Valid installable manifest (192/512/maskable icons from `public/app-icon.png`) + apple-touch icons
- [ ] `viewportFit: "cover"` set and every `env(safe-area-inset-*)` consumer re-checked against
      non-zero insets, portrait + landscape, LTR **and** RTL
- [ ] Pinch-zoom preserved (`maximumScale: 5`; `userScalable` not disabled)
- [ ] Service worker caches the shell + scripture `GET`s only — never chat POSTs or anything
      carrying the single-use `X-Turnstile-Token`; a deploy invalidates the cache
- [ ] `/app` shows iOS install instructions to iPhone visitors, Play badge to everyone else, in all
      11 locales; **no** App Store badge until BITB-088

**Full Story:** `docs/BACKLOG_STORIES/BITB-084-iphone-ready-web-installable-pwa.md`

---

### 🎯 BITB-085: Decide the iOS Delivery Approach — Decision Record + Apple Prerequisites

**Status:** 🎯 Todo
**Size:** S–M (1 day of analysis + the setup it unblocks)
**Created:** 2026-07-29

**As the** maintainer, **I want** the iOS approach chosen once, in writing, against explicit criteria,
**so that** the multi-week build in BITB-087 is not restarted halfway through.

**Why P2:** The repo currently carries **three contradictory iOS strategies** with no recorded
reasoning — `docs/ROADMAP.md:219` ("native iOS app"), BITB-012's *Out of Scope* below ("future
consideration"), and `docs/ARCHITECTURE.md:926` (still says **React Native**, stale since Android
shipped as native Kotlin). Gates BITB-087 and BITB-088.

**Acceptance Criteria (summary):**

- [ ] `docs/ios/delivery-approach.md` rates PWA-only / WebView wrapper / native SwiftUI / KMP-shared
      against 7 weighted criteria with evidence, and records the decision + what would reverse it
- [ ] The fourth-verse-parser question is answered concretely (BITB-086 as hard prerequisite, or how
      the chosen option otherwise avoids a fourth grammar)
- [ ] Turnstile in a WKWebView proved by an **actual token obtained**, not by reading docs — if it
      cannot be, every POST endpoint is unreachable and the plan changes
- [ ] Apple Developer enrolment, bundle id, macOS-CI cost, and signing strategy decided/owned
- [ ] Donation decision recorded: **no Ko-fi entry point on iOS v1** (Apple 3.2.1(vi) is stricter
      than the Play carve-out BITB-074 relies on)
- [ ] `ROADMAP.md:219` and `ARCHITECTURE.md:926` corrected to point at the record

**Full Story:** `docs/BACKLOG_STORIES/BITB-085-ios-delivery-approach-decision.md`

---

### 🎯 BITB-086: Server-Emitted Citation Spans — Linkify Verses Without a Client Regex

**Status:** 🎯 Todo
**Size:** L
**Created:** 2026-07-29

**As a** maintainer about to add a fourth client, **I want** the backend to tell clients *where* each
citation appears in the answer, **so that** tappable verses stop requiring an 11-language citation
grammar per platform.

**Why P2 (raise to P1 the moment BITB-087 is scheduled):** The backend already knows every citation —
`api/chat/service.py:1310-1321` merges structured + regex extraction and ships `verses_cited` at
`:1375-1386` — yet **no client consumes it**: grepping `verses_cited`/`versesCited` across
`frontend/src/` and `android/app/src/main` returns nothing. Instead three clients re-derive it in
three regex dialects, which is audit finding **A1 (CRITICAL)** and BITB-059's unfinished Phase 3. A
native iOS client would add a fourth. BITB-059's *Out of scope* names this as the alternative to
revisit — a fourth client is the revisit trigger.

**Acceptance Criteria (summary):**

- [ ] Additive `citations` array on the streaming `completion` event (`text`, `start`, `end`,
      `occurrence`, book/chapter/verse/`verse_end`); `verses_cited`/`resolved_verses` unchanged
- [ ] Spans computed **after** grounding, against `corrected_message` when present — with a
      regression test, since that is exactly where silent off-by-N would hide
- [ ] Offset unit specified (UTF-16 code units) and asserted with Arabic marks, Devanagari, CJK, emoji
- [ ] `text` + `occurrence` make the contract self-verifying so a Swift client can use substring
      search and ignore offsets; corrupt spans degrade to plain text, never crash or duplicate
- [ ] Web becomes the reference consumer **behind a flag**, regex retained as fallback; parity with
      the regex path over the shared corpus from `tests/fixtures/` (PR #906)
- [ ] Old clients (no `citations`) provably unaffected
- [ ] Does **not** delete the existing three parsers — that stays BITB-059 Phase 3

**Full Story:** `docs/BACKLOG_STORIES/BITB-086-server-emitted-citation-spans.md`

---

### 🎯 BITB-090: Remove `init_db()` / `create_all()` Once Alembic Owns the Schema

**Status:** 🎯 Todo
**Size:** S
**Depends on:** BITB-089 — **hard** dependency, must not be done first

**As a** maintainer, **I want** exactly one system allowed to create schema, **so that** the
migration history is a truthful record of the database rather than one of two competing accounts.

`api/main.py:201` → `init_db()` → `create_all()` (`api/scripture/database.py:175-186`) is a second
schema authority. While it exists, a table added to an ORM model appears in the database on the
next app boot with no revision and no `alembic_version` change — Alembic then believes the DB is at
`r0001` when it is not. Latent today (Alembic is inert); a real divergence the moment BITB-089 lands.

**Acceptance Criteria (summary):**

- [ ] `create_all()` removed; everything else `init_db()` does is preserved or its removal justified
- [ ] Fresh local DB fully usable via `alembic upgrade head` alone — verified from empty
- [ ] Test fixtures no longer depend on `create_all`; suite passes from an empty database
- [ ] CI job that starts empty, runs only `alembic upgrade head`, and boots the app
- [ ] Startup no longer silently swallows a schema-setup failure
      (`docs/audits/2026-07-adversarial-audit.md:174`) — or a follow-up is filed

**Full Story:** `docs/BACKLOG_STORIES/BITB-090-remove-create-all-once-alembic-owns-schema.md`

---

## P3 - Low Priority (Future)

### ✅ BITB-072: Repo Hygiene & Build Quick Wins (360° Review Compartments)

**Status:** ✅ Done (PR #916, 2026-07-20)
**Size:** S (< 4 hrs)
**Created:** 2026-07-20

**As a** maintainer, **I want** the low-risk items from the 2026-07-20 360° review
shipped as independent commits, **so that** build hygiene and the doc surface improve
with zero behavioural risk.

**Acceptance Criteria (summary):**

- [x] Dead `AGENTS.md.old`/`AGENTS.old.md` deleted; stale 2026-01 root planning docs archived to `docs/archive/`
- [x] `.dockerignore` added for `api/` and `frontend/` build contexts (keeps local `.env` and `tests/` out of images)
- [x] `eslint-config-next` aligned with `next` 16 (lint + tsc verified)
- [x] Review report at `docs/audits/2026-07-20-360-review.md`; follow-up story BITB-073 filed

**Full Story:** `docs/BACKLOG_STORIES/BITB-072-repo-hygiene-build-quick-wins.md`

---

### ✅ BITB-073: Split Dev/Prod Python Requirements (Stop Shipping pytest in the Prod Image)

**Status:** ✅ Done (PR #928 merged 2026-07-23)
**Size:** S (< 4 hrs)
**Created:** 2026-07-20
**Completed:** 2026-07-23

**As a** maintainer, **I want** test-only deps out of `api/requirements.txt`
(into a new `requirements-dev.txt`), **so that** the production image doesn't carry the
test framework. Finding F3 of the 2026-07-20 360° review; deferred from BITB-072
because it touches 2 workflows + Makefile + docs.

**Acceptance Criteria (summary):**

- [x] Clean-venv install of `requirements.txt` contains no pytest; `requirements-dev.txt` runs the full suite
- [x] Backend CI (unit + integration) green with updated install lines and cache keys
- [x] Docker image builds unchanged; dependabot still covers both files

**Full Story:** `docs/DONE/BITB-073-split-dev-prod-python-requirements.md`

---

### 🎯 BITB-070: Re-evaluate `hybrid` Content-Safety Mode (Two-Vendor Defense-in-Depth)

**Status:** 🎯 Todo
**Size:** M (1-2 days, mostly infra + a small code change)
**Created:** 2026-07-17

**As a** maintainer, **I want** a documented, ready-to-execute plan for switching content
safety to `hybrid` mode, **so that** when the team decides two-vendor defense-in-depth is
worth the added infra/cost, it's a scoped task instead of a fresh investigation.

**Why deferred:** `ml_only` (current default) is reliable today — after the BITB-061 follow-up
work, a 100-sample live benchmark measured 0 total failures (the secondary Llama Guard model
recovers every primary failure). `hybrid` would add a genuinely independent second vendor
(Azure Content Safety, chained after OpenAI Moderation) rather than just retry resilience
within one vendor — a real but not urgent upgrade. Blocked today by: no `OPENAI_API_KEY`
infrastructure anywhere (Terraform variable, `main.tf` env wiring, GitHub secret all missing —
the only OpenAI-related key that exists, `AZURE_OPENAI_API_KEY`, is for embeddings, not
moderation), no Azure Content Safety credentials wired either, and a code-level constraint:
Azure Content Safety can currently only run as `hybrid`'s Stage 3, gated by
`content_safety_mode == "hybrid"` — there's no path to "Llama Guard + Azure" without also
adding an OpenAI key, unless a new mode is added.

**Full Story:** `docs/BACKLOG_STORIES/BITB-070-reevaluate-hybrid-content-safety-mode.md`

---

### ✅ BITB-052: Web Contact Form Should Show an Email-Specific Error on a 422 (Not Generic "Failed to Send")

**Status:** ✅ Done
**Size:** S (< 2 hrs)
**Created:** 2026-06-16

**As a** web user submitting the contact form, **I want** an email-specific error when my
submission is rejected for an invalid email, **so that** I can fix it instead of seeing a generic
"failed to send". Web follow-up to BITB-051 (web has no 300-char misreport, just a generic error).

**Acceptance Criteria (summary):**

- [x] A 422 email rejection renders an email-specific message, not the generic `errorSend`
- [x] `submitContactForm` parses the 422 `detail` (mirroring `streamMessage`/`MessageTooLongError`); other failures still show `errorSend`
- [x] `Contact.errorEmailInvalid` added in all 11 locales; tests in `api.test.ts` + `ContactForm.test.tsx`

**Full Story:** `docs/BACKLOG_STORIES/BITB-052-web-contact-form-email-specific-error.md`

---

### 🚧 BITB-030: ChatScreen Top App Bar Cleanup — Language + Bible Version Only

**Status:** 🚧 In Progress
**Size:** S (< 4 hours)
**Created:** 2026-05-10

**As an** Android user on the Chat screen,
**I want** the top-right of the screen to expose only the controls I reach for most often (language, Bible version, and the verses panel when present),
**so that** the top bar stays uncluttered while less-frequent actions live in the left hamburger drawer.

**Acceptance Criteria:**

- [ ] `ChatScreen` `TopAppBar.actions` shows only Bible-version chip, verses panel (conditional), and language picker — in that order
- [ ] Drawer adds "Clear conversation" entry (visible only when messages exist); New chat / Settings preserved
- [ ] `chatTopBarPolicy(...)` pure helper covers the visibility rules and is unit-tested
- [ ] No new string resources, no ViewModel / navigation changes, no other screens touched

**Full Story:** `docs/BACKLOG_STORIES/BITB-030-android-chat-language-picker.md`

---

### 🎯 BITB-028: Simplify Church Finder Headers (Banner + Bottom Sheet)

**Status:** 🎯 Todo
**Size:** XS (< 1 hour)
**Created:** 2026-05-10

**As an** Android user,
**I want** a clean, single-tap way to dismiss the church-finder banner *and* the bottom sheet,
**so that** I'm not distracted by unclear secondary text or low-contrast "Dismiss" labels.

**Acceptance Criteria:**

- [ ] Right-side subtitle text removed from the Church Finder bottom sheet header
- [ ] Close (X) `IconButton` added on the right of the bottom sheet header, dismissing the sheet on tap
- [ ] In-chat suggestion banner replaces the "Dismiss" text label with a clear `Icons.Default.Close` icon
- [ ] Banner close icon has a `contentDescription` for accessibility
- [ ] Swipe-to-dismiss still works on the bottom sheet (no regression)
- [ ] No changes to search behaviour or `ChurchResultCard` content

**Full Story:** `docs/BACKLOG_STORIES/BITB-028-church-finder-bottom-sheet-cleanup.md`

---

### 🎯 BITB-025: Traditional→Simplified Chinese Conversion Layer for Verse Parsing

**Status:** 🎯 Todo
**Size:** M (1-2 days)
**Created:** 2026-04-03

**As a** Chinese-speaking user (traditional script),
**I want** verse references written in traditional Chinese characters (e.g. 約翰福音 3:16, 馬太福音 5:3) to be detected and linked,
**so that** I can see verse lookups regardless of whether the LLM produces simplified or traditional characters.

**Why P3:** PR #389 added 28 aliases covering the highest-impact variants (记↔纪 swaps
and Catholic 思高本 names). Traditional character support is the remaining gap, but
it requires a different approach than individual aliases — there are 66 books × 2 scripts
plus mixed-script edge cases.

**Background:**

CUV (Chinese Union Version/和合本) exists in both simplified (CUVS) and traditional (CUVT)
editions. LLMs may produce traditional characters for any book name. Examples:

| Simplified (current) | Traditional (unhandled) | Book |
|---|---|---|
| 约翰福音 | 約翰福音 | John |
| 马太福音 | 馬太福音 | Matthew |
| 使徒行传 | 使徒行傳 | Acts |
| 传道书 | 傳道書 | Ecclesiastes |
| 启示录 | 啟示錄 | Revelation (already aliased) |
| 历代志上 | 歷代志上 | 1 Chronicles |
| 罗马书 | 羅馬書 | Romans |
| ... | ... | all 66 books potentially affected |

Adding 66+ individual aliases is fragile and won't handle mixed-script text
(e.g. `約翰福音` with traditional 約 but simplified 音).

**Proposed approach — T2S (Traditional→Simplified) normalization function:**

A single function that converts Traditional Chinese characters to Simplified *before*
the verse regex lookup runs. This handles all books, mixed script, and future additions
with zero per-book maintenance.

*Backend (Python):*

```python
# Option A: opencc-python-reimplemented (most robust, ~2MB)
import opencc
converter = opencc.OpenCC('t2s')
text = converter.convert(text)

# Option B: hanziconv (lightweight, ~500KB)
from hanziconv import HanziConv
text = HanziConv.toSimplified(text)
```

*Frontend (TypeScript):*

```typescript
// Option A: chinese-conv npm package (~50KB gzipped)
import { traditionalToSimplified } from 'chinese-conv';
text = traditionalToSimplified(text);

// Option B: Minimal custom T2S table covering only the ~120 unique
// characters used in Bible book names (smallest bundle impact)
const BIBLE_T2S: Record<string, string> = { '約': '约', '馬': '马', ... };
text = text.replace(/[\u4e00-\u9fff]/g, ch => BIBLE_T2S[ch] || ch);
```

*Android (Kotlin):*

```kotlin
// Use ICU Transliterator (built into Android)
val t2s = Transliterator.getInstance("Traditional-Simplified")
text = t2s.transliterate(text)
```

**Acceptance Criteria:**

- [ ] Backend: Traditional Chinese book names are normalized to simplified before verse parsing
- [ ] Frontend: Traditional Chinese book names are normalized before verse extraction
- [ ] Android: Traditional Chinese book names are normalized in client-side regex
- [ ] Mixed-script text handled correctly (e.g. partial traditional)
- [ ] No regression on existing simplified Chinese tests
- [ ] Minimal bundle size impact (frontend: prefer Option B if < 20 unique chars needed)
- [ ] Performance: normalization adds < 1ms overhead per call

**Tech Constraints:**

- Backend dependency must be pip-installable and compatible with Python 3.11+
- Frontend solution must not significantly increase bundle size
- Must not affect non-Chinese text (normalization should be a no-op for Latin/Cyrillic/etc.)

**Out of Scope:**

- Simplified→Traditional conversion (output is always simplified)
- Full CJK variant unification (only T2S needed for verse parsing)

---

### 🎯 BITB-010: Add Blue-Green Deployment

**Status:** 🎯 Todo
**Size:** XL

**As a** product owner,
**I want** zero-downtime deployments with instant rollback,
**so that** users never experience service interruptions during updates.

**Acceptance Criteria:**

- [ ] Azure Container Apps revisions configured for traffic splitting
- [ ] Deployment creates new revision, tests it, then switches traffic
- [ ] Rollback script can instantly revert to previous revision
- [ ] Health checks validate new revision before traffic switch
- [ ] Documentation includes deployment and rollback procedures

**Tech Constraints:**

- Must work with existing Azure Container Apps setup
- Must support database migrations (may require multi-step deployments)
- Must handle stateful sessions gracefully

**Out of Scope:**

- Canary deployments (can be added later)
- Multi-region deployments

**Related:** TASKS.md #6.1

---

### 🎯 BITB-011: Add Frontend Testing Suite

**Status:** 🎯 Todo
**Size:** XL

**As a** developer,
**I want** comprehensive frontend tests,
**so that** UI changes don't break existing functionality.

**Acceptance Criteria:**

- [ ] Vitest configured for unit tests
- [ ] React Testing Library tests for all major components
- [ ] Playwright E2E tests for critical user flows (chat, verse lookup, language switching)
- [ ] CI runs frontend tests and enforces 80%+ coverage
- [ ] Documentation includes testing guidelines

**Tech Constraints:**

- Must work with Next.js App Router
- Must support i18n testing (multiple locales)
- Must mock API calls for unit tests

**Out of Scope:**

- Visual regression testing
- Performance testing

**Related:** TECHNICAL_DEBT.md #2, TASKS.md #4.2

---

### 🎯 BITB-012: Migrate Android App to Production

**Status:** 🎯 Todo (BITB-003 unblocked ✅)
**Size:** XL

**As a** mobile user,
**I want** to download the app from Google Play Store,
**so that** I can use it on my phone without installing from APK.

**Acceptance Criteria:**

- [x] Turnstile bot protection enabled (BITB-003 ✅)
- [x] App icon and branding finalized (`android/play_store_assets/`)
- [x] Privacy policy written (`docs/privacy-policy.md`)
- [x] Terms of service written (`docs/terms-of-service.md`)
- [x] Play Store metadata created (`android/fastlane/metadata/android/en-US/`)
- [x] Fastlane configured for Play Store uploads (`android/fastlane/`)
- [x] Release signing config added to `android/app/build.gradle.kts`
- [x] GitHub Actions publish workflow created (`.github/workflows/android-publish.yml`)
- [ ] Production keystore generated and GitHub secrets set (`KEYSTORE_FILE`, `KEYSTORE_PASSWORD`,
  `KEY_ALIAS`, `KEY_PASSWORD`, `GOOGLE_PLAY_JSON_KEY`)
- [x] Screenshots captured (9 screens) and added to `android/play_store_assets/screenshots/` and
  `android/fastlane/metadata/android/en-US/images/phoneScreenshots/`
- [ ] Google Play Console: app created, listing filled, content rating completed
- [ ] App submitted and approved by Google
- [ ] Post-launch monitoring verified (Firebase Crashlytics + Analytics)

**Tech Constraints:**

- Must meet Google Play Store policies
- Must comply with GDPR/privacy regulations
- Must have Turnstile enabled before public release

**Out of Scope:**

- iOS app (future consideration)
- In-app purchases or monetization

**Dependencies:**

- ✅ BITB-003 (Turnstile on Android) — done

**Note (2026-07-29):** the *Out of Scope* line above ("iOS app — future consideration") is now
superseded. iOS is planned as BITB-084 → BITB-085 → BITB-086 → BITB-087 → BITB-088.

---

### 🎯 BITB-087: iOS App v1 — SwiftUI Chat Parity, TestFlight-Ready

**Status:** 🎯 Todo (blocked on BITB-085; BITB-086 is a hard prerequisite)
**Size:** XL (2+ weeks; re-estimate once BITB-085 picks the approach)
**Created:** 2026-07-29

**As an** iPhone user, **I want** an app that streams a Scripture-grounded answer with tappable
verses, remembers my conversations, and speaks my language, **so that** I get the companion Android
users already have.

**Why P3:** Large, and correctly gated behind a decision (BITB-085) and a prerequisite (BITB-086).
"Same features as Android" is 21k lines of Kotlin across 144 files, so v1 is a deliberate vertical
slice — chat, verses, translations, 11 locales, history, feedback, settings — with church finder,
contact form, changelog, What's New, diagnostics and follow-up chips explicitly deferred to a
follow-on story filed *after* v1 lands.

**Acceptance Criteria (summary):**

- [ ] Streaming chat works against production on a physical iPhone
- [ ] Turnstile state machine matches `TurnstileInterceptor.kt`: `X-Turnstile-Token` on POSTs,
      single-use tokens, 403 → reset → one retry, fail-open on timeout
- [ ] **No verse-reference regex anywhere in the iOS codebase** — enforced by a CI grep, not review
      diligence; citations come from BITB-086's spans and degrade to plain text when absent
- [ ] Conversations persist across cold launch and are readable offline
- [ ] All 11 locales render, `ar` in RTL, CI fails on a missing key (mirrors Android
      `translation-validation`); translations **generated** from existing `strings.xml`/`messages/*.json`,
      not hand-copied (255 × 11 = 2,805 strings)
- [ ] Dynamic Type at max size, VoiceOver, light/dark, notch + keyboard safe areas all correct
- [ ] No new permissions, no donate link, no changes outside `ios/` (plus the strings script + CI)
- [ ] XCUITest ships as a separate non-required CI tier first, mirroring `android/COMPOSE_TESTS.md`

**Full Story:** `docs/BACKLOG_STORIES/BITB-087-ios-app-v1-chat-parity.md`

---

### 🎯 BITB-088: iOS Release Pipeline & App Store Compliance

**Status:** 🎯 Todo (blocked on BITB-087)
**Size:** L (3–5 days + App Review latency)
**Created:** 2026-07-29

**As an** iPhone user, **I want** to install Vox Quieta from the App Store; **as the** maintainer,
**I want** iOS releases as automated as Android's, **so that** a second store does not double the
manual work of every release.

**Why P3 and separate from BITB-087:** on Android the release machinery was the fiddlier half —
`android-publish.yml`, `android-promote.yml`, `android/fastlane/`, plus a Console-only compliance
checklist that needed its own file because it "otherwise has no home in the repo"
(`docs/android/play-console-compliance.md`). iOS needs all three; folding them into the app story is
how they get skipped.

**Acceptance Criteria (summary):**

- [ ] A `vX.Y.Z` tag produces a TestFlight build with no manual Xcode step; version read from
      `.release-please-manifest.json` (as `android/app/build.gradle.kts` already does)
- [ ] Publish refuses to upload on tag/manifest mismatch or non-green iOS CI (mirrors the Android
      gate); local build/test succeeds with **no** Apple credentials present
- [ ] `PrivacyInfo.xcprivacy` + App Privacy answers **derived from the agreed Play Data safety
      answers** (chat text shared with OpenRouter/Azure OpenAI per PR #900; no location) — the two
      stores must not describe the same backend differently
- [ ] Age rating + review notes state the LLM content-safety pipeline (Llama Guard 3, BITB-020), no
      account/IAP/ads/tracking/permissions, and pre-empt Guideline 4.2 with the native-capability list
- [ ] `ITSAppUsesNonExemptEncryption` set; store listing English-only (matches today's Android
      listing) with native iPhone screenshots reusing Android's 9-scene list
- [ ] **App approved and downloadable**; `/app` shows the App Store badge in all 11 locales
- [ ] `docs/ios/app-store-compliance.md` created (modelled on the Play one, including its
      check-off-and-archive discipline); `docs/RELEASE_PROCESS.md` documents the two-store tag fan-out

**Full Story:** `docs/BACKLOG_STORIES/BITB-088-ios-release-pipeline-and-app-store-compliance.md`

---

### 🎯 BITB-091: Backfill the Five Legacy Non-ORM Tables into Alembic

**Status:** 🎯 Todo
**Size:** M
**Depends on:** BITB-089

**As a** maintainer, **I want** every table managed by one migration system, **so that** no category
of table changes only by hand-edited SQL.

`sessions`, `verse_topics`, `rate_limit_hits`, `rate_limit_sessions`, `schema_migrations` have no
ORM model and are excluded from Alembic by the `include_name` allowlist in `api/alembic/env.py`.
That filter is **load-bearing** — without it the first `--autogenerate` would propose
`op.drop_table(...)` for all five. The current state is safe and can stay indefinitely; the cost is
that changing any of them means hand-rolled SQL with no history or rollback. Do this when one of
them next needs to change.

⚠️ `schema_migrations` should probably be **retired**, not adopted — it is the legacy system's own
bookkeeping table.

**Acceptance Criteria (summary):**

- [ ] Models verified against a *restored copy of prod*, not against `scripts/init.sql`
- [ ] `alembic revision --autogenerate` produces an **empty** diff — evidence in the PR
- [ ] No `drop_table` / `drop_column` in any generated revision — explicitly reviewed and stated
- [ ] Decision recorded for `schema_migrations`: retire, adopt, or leave excluded
- [ ] `api/alembic/README.md` invariant #1 updated to match

**Full Story:** `docs/BACKLOG_STORIES/BITB-091-backfill-legacy-tables-into-alembic.md`

---

## Done (Recent Completions)

### ✅ BITB-024: Add Phase 2 Language Support (Russian, Chinese, Hindi, Korean)

**Status:** ✅ Done (PR #258 merged; PR #261 open for Bible data loading)
**Size:** L (3-5 days)
**Created:** 2026-03-08
**Completed:** 2026-03-08

**As a** non-English speaker,
**I want** the app's UI and Bible responses in my native language (Russian, Chinese, Hindi, or Korean),
**so that** I can engage with scripture in the language closest to my heart.

**Acceptance Criteria:**

- [x] Russian (ru), Chinese Simplified (zh), Hindi (hi), Korean (ko) UI translations added (`frontend/messages/`)
- [x] Frontend routing updated: all 4 locales added to `routing.ts` locale list
- [x] Language switcher labels added to `LanguageSwitcher.tsx` for all 4 locales
- [x] `hreflang` alternate links added in `layout.tsx` `generateMetadata()` for all 4 locales
- [x] Backend `SUPPORTED_LANGUAGES` and `LANGUAGE_TRANSLATIONS` extended for ru, zh, hi, ko
- [x] `TRANSLATION_INFO` metadata (native names, locale codes) added for all 4 languages
- [x] 4 × 66 Bible book name maps added (ru, zh, hi, ko)
- [x] `lingua` language detector `lang_map` extended to recognise all 4 new languages
- [x] LLM prompt `LANGUAGE_NAMES` and `SOURCE_ATTRIBUTION_EXAMPLES` updated for all 4 languages
- [x] `scripts/translations.py` updated with synodal/cuv/hindi/krv entries and book name dicts
- [x] `scripts/init.sql` seeded with Phase 2 translation rows
- [x] `scripts/load_bible.py` handles `url=None` for manual-source translations gracefully
- [x] Tests cover all new translation keys, book maps, detector mappings, and prompt constants
- [x] Full CI suite passes (all tests green)

**Implementation Notes:**

- Frontend: 4 new `frontend/messages/{ru,zh,hi,ko}.json` files; all translation keys match `en.json`
- Backend: `api/utils/language.py` extended with book name maps and language metadata
- Language detection: `lingua-language-detector` already installed; only `lang_map` entries needed
- No new dependencies introduced (frontend or backend)
- getBible API codes differ from internal codes for Chinese (`cuv` internal → `cus` URL)
  and Korean (`krv` internal → `korean` URL)
- Hindi has no free getBible source; `url=None`, `source="manual"` — data must be loaded
  separately if needed
- `scripts/translations.py` now contains a full **ADDING A NEW LANGUAGE** checklist in the
  module docstring

**PRs:**

- [#258](https://github.com/zioalex/getinspiredbythebible/pull/258)
  (`feat/bitb-024-phase2-languages`) — API/UI layer ✅ merged
- [#261](https://github.com/zioalex/getinspiredbythebible/pull/261)
  (`feat/bitb-024-bible-data-loading`) — data loading scripts ✅ CI green, awaiting merge

---

### ✅ BITB-000: Bootstrap Android App

**Status:** ✅ Done (PR #156 merged)
**Completed:** 2026-02-20

Basic Android app scaffold with Kotlin, Jetpack Compose, and Ollama embedding provider.
Includes chat interface, verse display, and local-first architecture.

**PR:** #156

---

## Icebox (Ideas for Future Consideration)

- **Multi-Bible Translation Support**: Allow users to select KJV, NIV, ESV, etc.
- **Daily Devotional Notifications**: Push notifications with daily verses
- **Verse Memorization Game**: Gamified scripture memorization feature
- **Community Prayer Requests**: Social feature for sharing prayer needs
- **Audio Bible Integration**: Read-along audio for verses
- **Offline Mode (Web)**: Service worker for offline scripture access
- **Dark Mode**: User preference for light/dark theme (frontend only)
- **Verse Sharing**: Generate shareable images of verses for social media

---

## Notes

- **Source of Truth**: This backlog is the canonical source for prioritized feature work
- **Technical Debt**: See `docs/TECHNICAL_DEBT.md` for engineering-focused items
- **Tasks**: See `docs/TASKS.md` for detailed technical improvements and quick wins
- **Tracking**: Active PRs tracked in `docs/WIP/PR-*.md` files
