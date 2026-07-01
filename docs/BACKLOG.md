# Product Backlog

Prioritized list of user stories and features for Vox Quieta.

**Last Updated:** 2026-07-01

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
- [ ] Hybrid search enabled (PR #727, trimmed to the flag flip)
- [ ] Golden eval set + scorer (Precision@5 / Recall@10 / MRR) — see **BITB-051**
- [ ] Baseline measured; hybrid weights tuned + documented; retrospective in `docs/DONE/`

**Full Story:** `docs/BACKLOG_STORIES/BITB-043-validate-and-enable-phase1-search.md`

---

### 🚧 BITB-051: Search Retrieval-Evaluation Harness (golden set + scorer)

**Status:** 🚧 In Progress (P0 + P1 landed; P2–P4 todo)
**Size:** L (3-5 days, 5 small PRs)
**Created:** 2026-06-16

**As the** maintainer, **I want** a repeatable scorer that measures verse-retrieval
ranking (Precision@5 / Recall@10 / MRR) over a curated multilingual golden set, **so
that** I can validate whether query expansion / hybrid search actually help and tune
their weights instead of shipping search changes blind.

**Why P1:** Directly unblocks BITB-043 validation — expansion is live but unmeasured.
Delivered in 5 phases: **P0** trim PR #727 to the hybrid flip ✅; **P1** metric +
normalization core (`api/search_eval/`) ✅; **P2** 55+ case golden set (all 11
languages) + `--validate` + non-blocking CI; **P3** runner over real retrieval + A/B
report/CLI; **P4** full-corpus eval automated in CI (prod read-only + cached rebuild,
Azure embeddings, manual + nightly). Embeddings are **Azure `text-embedding-3-small`
(1536) everywhere** to match prod; per-PR CI is validate-only.

**Acceptance Criteria (summary — full story has detail):**

- [x] P0: PR #727 trimmed to hybrid-search enablement only
- [x] P1: `api/search_eval/` core (normalize + P@5/R@10/MRR + false-positive guard) with no-DB tests
- [ ] P2: 55+ multilingual golden set (11 languages) + loader + `--validate` + non-blocking CI
- [ ] P3: runner over real retrieval + report/CLI; manual prod-read-only A/B table
- [ ] P4: manual + nightly full-corpus eval (Routes A & B + smoke) on Azure

**Full Story:** `docs/BACKLOG_STORIES/BITB-051-search-retrieval-eval-harness.md`

---

### 🎯 BITB-052: Audit & Close Bible Reference-Normalization Gaps

**Status:** 🎯 Todo
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

- [ ] Per-language coverage matrix identifying every gap
- [ ] Missing localized singular/abbreviation aliases added (Psalms + common books)
- [ ] Case/diacritic-insensitive + numbered-book-variant matching, no regressions
- [ ] Versification offsets quantified + documented handling decision (with tests)
- [ ] Table-driven tests across all 11 languages green

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

### 🎯 BITB-039: Android — Keep the Current Chat When the Phone Is Rotated

**Status:** 🎯 Todo
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

- [ ] New chat + send message + rotate → same messages and conversation remain visible
- [ ] Existing saved conversation survives rotation
- [ ] Rotating during an in-flight response does not start a new chat
- [ ] Locale switching from Settings still works (still recreates Activity, applies new language)
- [ ] Existing Android unit tests pass; guard logic is covered by a test

**Full Story:** `docs/BACKLOG_STORIES/BITB-039-android-preserve-chat-on-rotation.md`

---

### 🎯 BITB-041: Verse Detail Never Loads — Add Timeout, Error/Retry, and Monitoring

**Status:** 🎯 Todo
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

- [ ] Slow/unreachable chapter fetch shows a clear error + working Retry within a bounded time — never an infinite spinner
- [ ] Verse text area never shows `////`/empty quotes (loading → verse or error)
- [ ] Backend verse/chapter reads time out to 504 instead of hanging
- [ ] Italian (ITA1927) detail loads for the reported references; corrupt data repaired + empty-text integrity check added
- [ ] Monitoring alert fires on elevated verse/chapter fetch error-rate or p95 latency/timeouts (existing action group)
- [ ] New Android + backend tests cover timeout, error, retry, and empty-text paths

**Test note:** existing tests over-mock and skip integration — `loadChapter` is tested
only for `IOException`, `VerseDetailBottomSheet` has no UI test, and the chapter route
covers only 200/404. These gaps let the bug ship.

**Full Story:** `docs/BACKLOG_STORIES/BITB-041-verse-detail-load-resilience-and-monitoring.md`

---

### 🎯 BITB-040: Verse-Detail Header Shows English Book Name Instead of Localized

**Status:** 🎯 Todo
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

### 🎯 BITB-004: Add Database Migration Framework (Alembic)

**Status:** 🎯 Todo
**Size:** L

**As a** developer,
**I want** a version-controlled database migration system,
**so that** schema changes are tracked, reversible, and safely deployed.

**Acceptance Criteria:**

- [ ] Alembic installed and configured
- [ ] Initial migration created from current schema
- [ ] Migration runs successfully on fresh database
- [ ] Rollback tested and working
- [ ] CI runs migration check before deploying
- [ ] Documentation updated with migration workflow

**Tech Constraints:**

- Must work with existing SQLAlchemy models
- Must work with asyncpg connection pool
- Must support zero-downtime deployments (future-proofing)

**Out of Scope:**

- Converting existing production database (manual one-time task)
- Auto-generated migrations from model changes (can be added later)

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

### 🎯 BITB-057: Android — In-App Update API (Flexible Flow)

**Status:** 🎯 Todo
**Size:** M (1–2 days)
**Created:** 2026-07-01

**As an** Android user, **I want** the app to tell me when a new version is available, **so that**
I can update and get the latest features and fixes without checking the Play Store manually.

**Why P1:** The app has no mechanism to detect or prompt for Play Store updates. Users on outdated
builds receive no signal that improvements exist. Implements the flexible (background-download,
non-disruptive) flow via `com.google.android.play:app-update-ktx`; guarded by `BuildConfig.DEBUG`
so debug and sideloaded builds are unaffected.

**Acceptance Criteria (summary — full story has detail):**

- [ ] `app-update-ktx` v2.1.0 added to `libs.versions.toml` + `build.gradle.kts`
- [ ] `InAppUpdateManager.kt` wraps `AppUpdateManager` with constructor injection for testability
- [ ] Flexible flow triggered on cold start when update available and staleness ≥ 3 days
- [ ] Snackbar with "Install update" action shown when download completes; calls `completeUpdate()`
- [ ] `onResume` re-checks for a pending install (app backgrounded during download)
- [ ] Unit tests with `FakeAppUpdateManager`; graceful no-op in debug and on sideloaded builds

**Full Story:** `docs/BACKLOG_STORIES/BITB-057-android-inapp-update-api.md`

---

### 🎯 BITB-058: Android — "What's New" Bottom Sheet on First Launch After Update

**Status:** 🎯 Todo
**Size:** S (< 1 day)
**Created:** 2026-07-01

**As an** Android user, **I want** to see a brief "What's New" summary the first time I open the
app after an update, **so that** I notice new features without digging into Settings manually.

**Why P1:** The app updates silently; users have no post-update signal. BITB-031 added a changelog
screen in Settings > About but requires active navigation. This story surfaces the top changelog
entry automatically — once per update, never on fresh install — using the existing `changelog.json`
asset, `ChangelogEntry` model, and `MarkdownText` dependency (no new library).

**Acceptance Criteria (summary — full story has detail):**

- [ ] `last_seen_version_code` persisted in `app_prefs`; helpers added alongside `hasSplashBeenSeen()` pattern
- [ ] Modal skipped on fresh install (stored == -1); shown exactly once per update
- [ ] `WhatsNewBottomSheet.kt` renders top `ChangelogEntry` via `MarkdownText`; graceful empty state
- [ ] "Dismiss" closes sheet and marks version seen; "See All" navigates to `changelog` route and marks seen
- [ ] String keys `whats_new_title`, `whats_new_dismiss`, `whats_new_see_all` added in all 11 locales
- [ ] Unit tests: stored==-1 → false; stored==current → false; stored==current-1 → true

**Full Story:** `docs/BACKLOG_STORIES/BITB-058-android-whats-new-on-launch.md`

---

## P2 - Medium Priority (Backlog)

> **Beta-tester feedback batch (Oliver Osthoever, 2026-06-11/12) → BITB-045…050.**
> Six stories captured from a German beta tester's usage notes: typo tolerance, more
> German Bibles, copy-prompt, keyboard dismissal, fresh-chat-on-launch, and thematic
> search/response depth.

### 🎯 BITB-055: Scripture/Chat Pipeline Observability — Fail Loud, Not Silent

**Status:** 🎯 Todo
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

- [ ] Explicit error counters in the three `except` paths; alert on the metric, not log text
- [ ] Business SLI: rate of responses served with zero DB verses / zero resolved citations
- [ ] End-to-end synthetic check that the chat path returns cited/grounded verses
- [ ] Log-scan robustness (structured levels + allowlist, not a hand-kept keyword denylist)
- [ ] Fail loud (guard/CI check) when prod alerting is disabled
- [ ] Integration test running the real search/grounding SQL against the Postgres service container

**Full Story:** `docs/BACKLOG_STORIES/BITB-055-scripture-pipeline-observability.md`

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

### 🎯 BITB-046: Add German Bible Translations (Luther 1912 + Elberfelder 1871)

**Status:** 🎯 Todo
**Size:** M (1-2 days, mostly data loading)
**Created:** 2026-06-12

**As a** German-speaking user, **I want** a familiar Bible translation (Luther), **so that** I'm not
limited to Schlachter 1951. Luther 1984/2017, Einheitsübersetzung, NGÜ, and Schlachter 2000 are
copyrighted; **Luther 1912** and **Elberfelder 1871** are public domain (getBible).

**Acceptance Criteria (summary):**

- [ ] German picker shows Luther 1912 (default), Schlachter 1951, Elberfelder 1871
- [ ] Text + embeddings loaded and searchable for both new translations
- [ ] German-default assertions updated `schlachter` → `luther1912`; all tests pass

**Full Story:** `docs/BACKLOG_STORIES/BITB-046-german-translations-luther-elberfelder.md`

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

### 🎯 BITB-044: Populate `verse_topics` to Activate Topic Boosting

**Status:** 🎯 Todo
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

**Status:** 🎯 Todo (production verified 2026-05-31 — favicon and robots.txt addressed; server-render-homepage remains)
**Priority:** P1 for task 1 (server-render homepage); P3 for tasks 2–4
**Size:** M (server-render homepage needs care at the client/server boundary; rest are small)
**Created:** 2026-05-29 · **Updated:** 2026-05-31

**As a** person searching for Bible inspiration on Google (or asking an AI assistant),
**I want** Vox Quieta's pages to be fully indexable — real server-rendered text, structured data, rich link previews,
**so that** the site can actually be discovered rather than served as an empty client-rendered shell.

**Live findings (2026-05-31):** `/en` renders 0 server-side words (homepage is `'use client'`) — only real remaining gap. `/favicon.ico` returned 404 and is fixed in the same PR. Cloudflare `/robots.txt` is fine: Cloudflare appends the origin's `Sitemap:` directive after its own managed AI-bot block, so the served body contains both.

**Acceptance Criteria:**

- [ ] **(P1)** Homepage hero text is server-rendered (live check shows `/en` is no longer thin); chat UI still hydrates (Turnstile, streaming, modals)
- [x] `/favicon.ico` returns 200 with the brand icon
- [x] Production `/robots.txt` contains `Sitemap: https://voxquieta.org/sitemap.xml` (verified)
- [ ] `WebSite` + `Organization` JSON-LD present on all locales; `seo-static-check.sh` JSON-LD WARN clears
- [ ] `og:image` resolves and Twitter card is `summary_large_image`
- [ ] Live check confirms `/sitemap.xml` 200, `/icon.svg` and `/favicon.ico` resolve, `/en` has canonical+OG+Twitter, `/en/privacy` hreflang points to `/it/privacy`; sitemap submitted to Search Console

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

### 🎯 BITB-008: Add Request Tracing with Correlation IDs

**Status:** 🎯 Todo
**Size:** S

**As a** developer debugging production issues,
**I want** every request to have a unique trace ID,
**so that** I can follow a single user's request through logs.

**Acceptance Criteria:**

- [ ] Middleware generates UUID for each request
- [ ] `X-Request-ID` header added to all responses
- [ ] Trace ID logged in every log entry for that request
- [ ] Trace ID propagated to database queries (as SQL comment)
- [ ] Documentation includes how to search logs by trace ID

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

## P3 - Low Priority (Future)

### 🎯 BITB-052: Web Contact Form Should Show an Email-Specific Error on a 422 (Not Generic "Failed to Send")

**Status:** 🎯 Todo
**Size:** S (< 2 hrs)
**Created:** 2026-06-16

**As a** web user submitting the contact form, **I want** an email-specific error when my
submission is rejected for an invalid email, **so that** I can fix it instead of seeing a generic
"failed to send". Web follow-up to BITB-051 (web has no 300-char misreport, just a generic error).

**Acceptance Criteria (summary):**

- [ ] A 422 email rejection renders an email-specific message, not the generic `errorSend`
- [ ] `submitContactForm` parses the 422 `detail` (mirroring `streamMessage`/`MessageTooLongError`); other failures still show `errorSend`
- [ ] `Contact.errorEmailInvalid` added in all 11 locales; tests in `api.test.ts` + `ContactForm.test.tsx`

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
