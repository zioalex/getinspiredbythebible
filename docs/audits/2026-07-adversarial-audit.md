# Adversarial Architecture & Risk Audit — July 2026

**Scope:** `api/` (FastAPI), `frontend/` (Next.js), `android/` (Kotlin/Compose), infra (`docker-compose*`, `deployment/`, `.github/workflows/`, `scripts/`), docs.
**Method:** Full-repo exploration by four parallel code scans, followed by hand re-verification of every CRITICAL/HIGH finding. Every `[ROOT CAUSE]` below cites a file:line that was actually read — nothing is speculative. Severity = blast radius × likelihood.
**Persona:** Cynical Principal Software Architect & Adversarial Project Risk Auditor. Praise is rationed; see "Load-bearing strengths" for the short list of things that must not be broken while fixing the rest.

---

## Executive summary

This project ships, works, and is visibly loved. It is also a **three-platform product held together by hand-synchronized copies of the same logic**, running on a **single small database exposed to the public internet**, behind **security controls that fail open by design**, gated by **CI tiers that are deliberately allowed to fail**. It survives because one team knows it intimately. It will not survive a team change, a traffic spike, or a determined abuser gracefully.

### Top 5 risks (ranked by blast radius × likelihood)

1. **The verse-parsing engine exists three times** — in Kotlin, TypeScript, and Python — synchronized by hand and by "mirrors the web" comments. The commit log proves it drifts (PRs #799, #801, #804 are all drift repairs). This is the project's largest recurring tax and its most likely source of user-visible cross-platform inconsistency. *(A1)*
2. **Synchronous HTTP inside async routes freezes the whole backend replica for up to 10 seconds** per email send. One feedback submission during SMTP2GO latency stalls every concurrent chat on that replica. *(S1)*
3. **The abuse-control stack fails open at every layer**: Turnstile verification returns "allow" on any exception, the rate limiter is per-process in-memory (halved-effectiveness at 2 replicas, amnesia on restart), and the content-safety master switch defaults to off. *(E2, S3, O2)*
4. **The public semantic-search endpoint runs the exact full-scan predicate the hybrid path was rewritten to avoid**, on a 2-vCPU/4GB Postgres that the team's own migration notes admit may thrash. *(S2, S5)*
5. **A total LLM outage returns generic 500s instead of the intended 503**, because the route matches an error substring the provider never emits. The one scenario the fallback chain was built for is the one it misreports. *(E1)*

**Finding counts:** 47 findings — 2 CRITICAL · 15 HIGH · 24 MEDIUM · 6 LOW.
*(Corrected from an initial hand-count of 36; the tally is now machine-verified by `tools/audit-metrics/`.)*

---

## Load-bearing strengths (do not break these while refactoring)

- The **hybrid search candidate-pool CTE** (`api/scripture/repository.py:35–70`) is genuinely well-designed HNSW-friendly SQL. It is the pattern the rest of the search code should converge on.
- The **embedding resilience layer** (`api/providers/embedding_resilience.py`) — circuit breaker, bounded timeout, jittered retry, transient-vs-permanent classification — is the best-engineered module in the backend.
- The **unit-test corpus is large and serious** (56 backend test files; `verseExtraction.test.ts` at 2,370 lines; `ChatViewModelTest.kt` at 2,325 lines). The gaps are in *which* things are tested, not in willingness to test.
- **Dependency discipline is real where it exists**: pinned version catalogs on Android, bounded DB pool with statement timeouts, release-please + pre-commit + detect-secrets toolchain.
- The **DB engine configuration** (`api/scripture/database.py:69–91`) — pool_pre_ping, pool_recycle, per-query statement timeout — is production-grade.

---

## 1. ARCHITECTURAL DEBT

### A1 — The triple-maintained verse parser

- **[SEVERITY]:** CRITICAL
- **[RISK PROFILE]:** Maintainability / Correctness
- **[THE ROOT CAUSE]:** The verse-reference engine is implemented three separate times in three languages and two regex dialects: Kotlin (`android/.../ChatMessageItem.kt:104–362`, Java regex `\p{IsHan}`), TypeScript (`frontend/src/lib/versePatterns.ts` + `verseExtraction.ts`, JS regex `\p{Script=Han}`), and Python (`api/utils/verse_parser.py`). The 737-line `LocalizedBookToEnglish.kt` is a self-described "parity copy — do not edit by hand" of the 1,073-line web map, guarded only by an **entry-count** test — counts can match while contents diverge.
- **[FAILURE SCENARIO]:** Already happening. PRs #799, #801, #804 are all cross-platform drift repairs ("web + android"). Next iteration: someone fixes a French citation edge case in TypeScript, forgets Kotlin, and Android users get dead verse links for a locale nobody on the team reads. Nobody notices for months because the parity test only counts entries.
- **[REFACTOR ACTION]:** Pick one source of truth. Either (a) generate all three artifacts (regex source + book maps) from a single spec file at build time, or (b) move reference extraction server-side entirely — the backend already parses verses — and have both clients render server-annotated spans. At minimum, replace the entry-count test with a full content-equivalence check generated from the web map.

### A2 — `ChatIsland.tsx`: a 1,357-line client-side monolith

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Maintainability
- **[THE ROOT CAUSE]:** One `"use client"` component (`frontend/src/app/[locale]/ChatIsland.tsx`) owns chat state, the SSE consumer, verse filtering, church-finder gamification, language switching, feedback, translation selection, mobile panels, and splash — via ~30 `useState`/`useRef` hooks and 9 effects. The streaming consumer alone (`submitMessage`, lines 368–677) is ~310 lines.
- **[FAILURE SCENARIO]:** Every feature touches this file; every PR conflicts here; every regression hides here. A new contributor cannot modify the church finder without understanding the streaming state machine, so they don't modify it — they bolt on another `useState`.
- **[REFACTOR ACTION]:** Extract the streaming consumer into a `useChatStream` hook with an explicit reducer, and split church-finder/language-switch/translation-picker into sibling components. Mechanical, low-risk, high-payoff.

### A3 — `ChatViewModel.kt`: the Android god-object

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Maintainability
- **[THE ROOT CAUSE]:** `android/.../ChatViewModel.kt` is 1,214 lines with a 23-field `ChatUiState` (lines 82–139), owning chat, chapter sheet, church finder, contact form, diagnostics, feedback, locale, theme, and translation prefs. Its test file is 2,325 lines — the test size is the debt made visible.
- **[FAILURE SCENARIO]:** Same as A2, but worse: on Android the ViewModel is also the process-death/rotation survival boundary, so state bugs here become data-loss bugs (see E10).
- **[REFACTOR ACTION]:** Split by feature into focused ViewModels (chat, settings, church) sharing scoped state holders. The 23-field UiState should decompose along the same seams.

### A4 — Duplicated request plumbing in `api.ts`

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Maintainability / Correctness
- **[THE ROOT CAUSE]:** `frontend/src/lib/api.ts` (947 lines) contains two parallel request paths: `turnstilePost` (221–252) and a hand-inlined fetch in `streamMessage` (584–619). The Turnstile 403-retry block and the request body are duplicated verbatim; the status→typed-error mapping is duplicated (470–498 vs 621–661) **and already diverged** — 422 message-too-long is handled only in the streaming path. Turnstile tokens are bridged through module-level mutable globals (129–132) wired imperatively from `providers.tsx`.
- **[FAILURE SCENARIO]:** Someone adds a new error status to one copy. The other path silently returns a generic error. This is not hypothetical — the 422 divergence proves the copies are already out of sync.
- **[REFACTOR ACTION]:** One request core: a single `apiFetch` that handles Turnstile attach/retry and status mapping, consumed by both the JSON and streaming paths. Kill the module-global token bridge in favor of the existing React context.

### A5 — Cosmetic dependency injection in the provider factory

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Maintainability / Testability
- **[THE ROOT CAUSE]:** `api/providers/factory.py:137–146` — `get_llm_provider`/`get_embedding_provider` are `@lru_cache` singletons that bind the module-level `settings`, ignoring the `Settings` FastAPI injects. Meanwhile `config.py:22` allows `llm_provider="openai"` as a valid Literal, but the factory raises `ProviderError("not yet implemented")` (`factory.py:71`) — config validation passes, boot fails.
- **[FAILURE SCENARIO]:** A test overrides settings via DI and wonders why the provider ignores it; an operator sets `LLM_PROVIDER=openai` in prod (the config schema said it was fine) and the app dies at first request.
- **[REFACTOR ACTION]:** Make the factory take `Settings` as a real parameter with app-lifetime caching in `lifespan`, and remove `openai` from the Literal until it exists.

### A6 — Circuit breaker with side-effecting reads and thread locks in an async app

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability
- **[THE ROOT CAUSE]:** `api/utils/circuit_breaker.py:54–68` — `is_open()` mutates state (OPEN→HALF_OPEN) as a side effect and guards with `threading.Lock` inside an asyncio app; it's called inside boolean expressions (`providers/openrouter.py:230–235, 395–400`). Half-open admits one probe in theory, but concurrent coroutines can all read `is_open()==False` before any records a result. Separately, `chat()` and `chat_stream()` duplicate the entire breaker+fallback dance (both tagged `# noqa: C901`).
- **[FAILURE SCENARIO]:** During recovery from an outage, N concurrent requests all "probe" the half-open breaker simultaneously, hammering the still-sick upstream and re-tripping it — exactly the stampede a breaker exists to prevent.
- **[REFACTOR ACTION]:** Make `is_open()` pure; add an explicit `try_acquire_probe()` guarded by `asyncio.Lock`. Extract the shared fallback loop from `chat`/`chat_stream` into one generator-friendly helper.

### A7 — Circular import with a load-order contract

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Maintainability
- **[THE ROOT CAUSE]:** `frontend/src/lib/verseExtraction.ts:12–18` ↔ `versePatterns.ts:15–21, 58–70` import each other and *document* that it only works because of ES-module live-binding evaluation order.
- **[FAILURE SCENARIO]:** A bundler upgrade, a barrel-file refactor, or a well-meaning import sort changes evaluation order; verse patterns initialize against an empty book map; every verse link silently disappears in the built bundle while unit tests (different module graph) stay green.
- **[REFACTOR ACTION]:** Extract the shared book-name data into a third leaf module both import. One hour of work removes a documented landmine.

### A8 — Client/server contracts as magic numbers and error-string grep

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Correctness
- **[THE ROOT CAUSE]:** Android hardcodes `MAX_INTERACTIONS=10` (`ChatViewModel.kt:163`) and `MAX_MESSAGE_LENGTH=300` (`:173`), mirroring backend `config.py` values by convention only, and classifies backend failures by substring-matching `errorBody().string()` for `"session_lifetime_limit"` / `"content_blocked"` (`ChatViewModel.kt:1176, 1185`).
- **[FAILURE SCENARIO]:** Backend ops raise the session limit to 20 via env var; Android keeps locking users out at 10. Backend renames an error code; Android's error mapping silently falls through to the generic message.
- **[REFACTOR ACTION]:** Serve limits from the existing `GET /config` endpoint (it already exists!) and return machine-readable error `code` fields instead of prose to be grepped.

### A9 — Transaction hygiene: commit-on-every-GET

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Correctness / Performance
- **[THE ROOT CAUSE]:** `api/scripture/database.py:126–143` — the `get_db_session` dependency commits unconditionally on every request, including pure reads. Combined with `utils/session_tracker.py:52` swallowing its own exceptions mid-transaction, the dependency's final `commit()` can throw on an already-aborted transaction (see E6).
- **[FAILURE SCENARIO]:** A read-only endpoint starts failing with "current transaction is aborted" errors that have nothing to do with the endpoint's own query, and the on-call engineer spends a day looking in the wrong file.
- **[REFACTOR ACTION]:** Commit only where writes happen; give read paths a no-commit session dependency.

### A10 — Dead code kept on life support

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Maintainability
- **[THE ROOT CAUSE]:** Five exported `api.ts` functions (`sendMessage`, `searchScripture`, `getVerse`, `getVerseContext`, `checkHealth` — lines 444, 743, 768, 827, 847) are referenced only by their own tests. Android's `injectVerseQuoteHighlights` is a documented no-op (`ChatMessageItem.kt:377`); `resolveResumeConversationId` is dead (`MainActivity.kt:712`). Committed cruft: `scripts/load_bible.py.backup`, `AGENTS.md.old`, `AGENTS.old.md`.
- **[FAILURE SCENARIO]:** Every refactor pays a tax keeping unused code compiling and its tests green; new contributors study `sendMessage` (dead) instead of `streamMessage` (real) and copy the wrong error-handling.
- **[REFACTOR ACTION]:** Delete all of it in one PR. Git remembers.

---

## 2. EDGE-CASE FAILURES

### E1 — The 503 that can never fire *(hand-verified)*

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Reliability / Observability
- **[THE ROOT CAUSE]:** `api/providers/openrouter.py:308, 491` raise `RuntimeError("All models unavailable or rate limited…")` / `("All models unavailable in streaming…")` when all fallbacks are exhausted. The routes check `if "All models rate limited" in str(e)` (`api/routes/chat.py:75, 124`). **That substring appears in neither message.** The intended 503 branch is unreachable.
- **[FAILURE SCENARIO]:** OpenRouter has a bad day. Every chat returns a generic 500. Monitoring pages the on-call for "server errors" instead of "upstream outage"; clients that would back off on a 503 retry-hammer a dead upstream instead.
- **[REFACTOR ACTION]:** Raise a typed `AllModelsExhaustedError` and catch the type, not prose. Add the one test that would have caught this: assert the provider's exhaustion error maps to 503 at the route.

### E2 — Turnstile verification fails open on *any* exception *(hand-verified)*

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Security / Abuse
- **[THE ROOT CAUSE]:** `api/utils/turnstile.py:92–103` — timeout → allow; HTTP error → allow; **any `Exception` → allow**. Bot verification is availability-first by design at every failure branch.
- **[FAILURE SCENARIO]:** An attacker doesn't need to solve Turnstile; they need Cloudflare's siteverify endpoint to be slow — or to induce any error at all — and every request sails through to the LLM, which is the expensive thing Turnstile exists to protect.
- **[REFACTOR ACTION]:** Fail closed on verification *rejection* and on repeated errors (breaker-style: fail open for the first blip, closed when siteverify is persistently erroring), and alarm loudly when the fail-open branch is taken. At minimum emit a metric; today the bypass is silent.

### E3 — Verse click handler forgot half the alphabet *(hand-verified)*

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Correctness (i18n)
- **[THE ROOT CAUSE]:** `frontend/src/components/ChatMessage.tsx:52–74` — the click path does `parseInt(match[2])` / `parseInt(match[3])` with no `normalizeDigits()`, and passes the raw localized `match[1]` book name to `onVerseClick`. The extraction path right next door does it correctly (`verseExtraction.ts:997–1002`). The shared regex explicitly matches Devanagari/Eastern-Arabic numerals (`versePatterns.ts:281`).
- **[FAILURE SCENARIO]:** A Hindi user clicks a verse rendered with Devanagari numerals: `parseInt("१४")` → `NaN`, and `getChapter("रोमियों", NaN, NaN)` goes to the backend. The feature the last three releases were dedicated to polishing is broken on click for the locales it was polished for.
- **[REFACTOR ACTION]:** Route the click handler through the same `normalizeDigits`/`normalizeBookName` pipeline as extraction — it's four lines away. Add one test with non-Latin numerals on the click path.

### E4 — Room database with no escape hatch

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Reliability (mobile data loss / crash loop)
- **[THE ROOT CAUSE]:** `android/.../VoxQuietaDatabase.kt` is `version = 1` with zero `Migration` objects and no `fallbackToDestructiveMigration()` anywhere. Verses are stored as a serialized JSON blob column (`MessageEntity.kt:33`), unqueryable and schema-opaque.
- **[FAILURE SCENARIO]:** The first release that touches an entity ships version 2. Every existing install throws `IllegalStateException: A migration from 1 to 2 was required` **at startup** — a crash loop for the whole user base, fixable only by another release or users wiping app data.
- **[REFACTOR ACTION]:** Before the *next* schema change: add a migration test harness (Room's `MigrationTestHelper` + the exported `schemas/1.json`), decide the destructive-fallback policy explicitly, and write Migration 1→2 alongside whatever change triggers it.

### E5 — Retry helper used against its own contract

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability
- **[THE ROOT CAUSE]:** `api/utils/db_retry.py:56–72` documents that the retried function must acquire a *fresh* session per attempt. `chat/service.py:759` and `feedback/repository.py:43, 81` retry against the same request-scoped session anyway (the feedback repo's docstring admits it and bets on `pool_pre_ping`).
- **[FAILURE SCENARIO]:** Postgres drops the connection mid-operation. The retry re-runs `add/commit` on a session in a failed, pending-rollback state; the "retry" deterministically fails with a different, more confusing error than the original.
- **[REFACTOR ACTION]:** Give the retry wrapper a session *factory*, not a session. The one correct usage (`feedback/blocked_samples.py:75–118`) already shows the pattern.

### E6 — Streamed chats are invisible to your own analytics

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Observability / Correctness
- **[THE ROOT CAUSE]:** `track_session` is called only on the non-streaming path (`api/routes/chat.py:70`); the streaming endpoint — which is what both clients actually use — never calls it. It also swallows its own DB errors (`utils/session_tracker.py:52`) after possibly aborting the shared transaction (see A9).
- **[FAILURE SCENARIO]:** DAU/MAU dashboards report a fraction of real usage; product decisions get made on data that excludes essentially all production traffic.
- **[REFACTOR ACTION]:** Track on stream completion (the `completion` chunk already exists as the hook point), in its own short-lived session.

### E7 — Boot-anyway startup — ✅ RESOLVED (BITB-090, 2026-09-04)

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability
- **[THE ROOT CAUSE]:** `api/main.py:127–132` — `init_db()` failure at startup is caught and logged; the app boots anyway and 500s on first DB use.
- **[FAILURE SCENARIO]:** A bad DB credential rollout produces a container that passes "is the process up" checks, gets traffic, and fails every request — instead of crash-looping where the orchestrator would catch, hold, and roll back the deploy.
- **[REFACTOR ACTION]:** Let startup die on DB init failure (Container Apps revisions handle the rollback), or wire the failure into `/health/ready` so the replica never receives traffic.
- **[RESOLUTION]:** `api/main.py`'s lifespan now re-raises on a failed `check_db_connection()` instead of logging and continuing, so a dead database crash-loops the revision.

### E8 — Unguarded `localStorage` writes

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability
- **[THE ROOT CAUSE]:** `ChatIsland.tsx:249–252` writes `localStorage` bare, while `api.ts:264–303` carefully try/catches the identical operation two directories away. Safari private mode and storage-blocked contexts throw here.
- **[FAILURE SCENARIO]:** A privacy-conscious user changes their Bible translation and the click handler throws, taking the React subtree down to the ErrorBoundary — for a preference write that was optional.
- **[REFACTOR ACTION]:** One `safeStorage` util, used everywhere. Delete both inline patterns.

### E9 — English-only guardrail in an 11-language product

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Correctness (safety UX)
- **[THE ROOT CAUSE]:** `api/chat/service.py:578` — the safe-filter heuristic checks `if "Not from the Bible" in response.content[:120]`. The product ships in 11 locales; the LLM answers in the user's language.
- **[FAILURE SCENARIO]:** The Italian model output says "Non proviene dalla Bibbia…" and the filter that exists specifically to catch that response waves it through. The recent safe-filter false-positive fix (#799) shows this area is already generating bugs.
- **[REFACTOR ACTION]:** Have the prompt emit a language-independent sentinel token (e.g. `[NOT_SCRIPTURE]`) and match that, not English prose.

### E10 — Android's two-brains language store and fire-and-forget session reset

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Correctness
- **[THE ROOT CAUSE]:** `android/.../LanguagePreferences.kt:35–61` writes both SharedPreferences and DataStore but reads initial state from one and the flow from the other; `ChatViewModel.kt:766–780` documents a locale-revert race in a comment instead of fixing it. `startNewConversation` (`:723–743`) resets the session id in a detached, un-awaited coroutine while synchronously resetting UI state.
- **[FAILURE SCENARIO]:** One write path fails or interleaves → app opens in the wrong language, or a fast message-send after "new conversation" goes out under the *old* session id and inherits its rate-limit count.
- **[REFACTOR ACTION]:** Single store (DataStore) with one synchronous initial read; make session reset a suspend point the send path awaits.

### E11 — Migration runner: checksums for decoration, duplicate version numbers

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability (schema drift)
- **[THE ROOT CAUSE]:** `scripts/migrations/run_migrations.py:229–231` computes a SHA-256 checksum per migration, records it — and never compares it: already-applied versions are skipped by name alone. The directory contains duplicate number prefixes (two `002_*`, two `003_*`), no rollback support, and empty SQL files get recorded as successfully applied.
- **[FAILURE SCENARIO]:** Someone edits an applied migration file to "fix" it for fresh environments; prod and every new environment now have silently different schemas, and the tool designed to prevent exactly this says nothing.
- **[REFACTOR ACTION]:** Verify checksums on every run (fail loudly on mismatch), enforce unique version prefixes in CI, or accept reality and adopt Alembic — you have already reimplemented a third of it.

### E12 — Mutable closure index inside React state updaters

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Correctness
- **[THE ROOT CAUSE]:** `ChatIsland.tsx:391, 413` — `assistantMessageIndex` is a closure variable assigned *inside* a `setMessages` updater, then read by later updaters. Updaters must be pure; StrictMode double-invocation or batched re-execution can skew the index.
- **[FAILURE SCENARIO]:** Under concurrent-features rollout or a React upgrade, streamed tokens append to the wrong message. Intermittent, unreproducible, blamed on the backend.
- **[REFACTOR ACTION]:** Identify the placeholder by a stable message id, not a captured array index.

### E13 — A 600-character regex with nested quantifiers on untrusted input

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Reliability (ReDoS) / Maintainability
- **[THE ROOT CAUSE]:** `frontend/src/lib/versePatterns.ts:274–281` builds a single ~600-char pattern with multiple lookbehinds and a connector branch `[\p{L}\p{M}]{2,}(?:\s+(?:of|dei|…)\s+[\p{L}\p{M}]+)+` — nested unbounded quantifiers — executed over every LLM output chunk on every render (and re-implemented on Android, see A1).
- **[FAILURE SCENARIO]:** A pathological LLM output (long runs of letters and connector words) sends the regex engine super-linear; the tab freezes mid-stream. Also: nobody can safely modify this pattern — which is why it took three PRs to fix separators.
- **[REFACTOR ACTION]:** Benchmark against adversarial input now; longer term, replace the mega-regex with a two-stage match (cheap candidate scan → strict validator), which also becomes the single spec that fixes A1.

---

## 3. SCALABILITY BOTTLENECKS

### S1 — Synchronous HTTP freezes the async event loop *(hand-verified)*

- **[SEVERITY]:** CRITICAL
- **[RISK PROFILE]:** Performance / Reliability
- **[THE ROOT CAUSE]:** `api/utils/email_service.py:73` uses **sync** `httpx.Client(timeout=10.0)`, called directly (no `await`, no thread offload) from `async def` routes: `routes/feedback.py:72, 145` and `routes/admin.py:47`.
- **[FAILURE SCENARIO]:** SMTP2GO has 8 seconds of latency. One user submits the contact form. For those 8 seconds the **entire event loop** on that replica is frozen: every in-flight chat stream stalls, health probes time out, and the readiness-probe flapping you already fought in PR #796 comes back wearing a mask.
- **[REFACTOR ACTION]:** `httpx.AsyncClient` (three-line change), or wrap in `anyio.to_thread.run_sync`. Then add a lint/test guard against sync HTTP clients in `api/`.

### S2 — Public search endpoint does the full scan the hybrid path was built to avoid *(hand-verified)*

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Scalability
- **[THE ROOT CAUSE]:** `api/scripture/repository.py:283` — pure semantic search filters `WHERE (1 - cosine_distance) >= threshold`, the exact predicate the candidate-pool CTE's own docstring (lines 46–48) says forces a full scan past the HNSW index. Same pattern in `search_passages_semantic` / `search_topics_semantic` (668–691, 799–811); `topics.embedding` has **no vector index at all** (`models.py:233`); `search_verses_text` uses leading-wildcard `ILIKE '%q%'` (247–255). All reachable from the public `GET /api/v1/scripture/search`.
- **[FAILURE SCENARIO]:** Twelve translations × ~31k verses each and a B2s Postgres: a handful of concurrent unauthenticated search calls saturate 2 vCPUs with sequential scans, and chat — the actual product — starves behind them. Your own migration 007 README already worries about exactly this box thrashing.
- **[REFACTOR ACTION]:** Route the pure-semantic path through the existing candidate-pool CTE (rank by index first, filter by threshold in the outer query). Add the missing HNSW index on `topics.embedding`. Replace ILIKE with the FTS machinery you already have.

### S3 — Rate limiting that forgets and divides

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Scalability / Abuse
- **[THE ROOT CAUSE]:** `api/utils/rate_limiter.py:54–56` — in-memory dicts, per process. Prod runs up to 2 replicas (`deployment/terraform.tfvars:56–59`); each replica enforces the full limit independently, and every deploy/restart resets all counters including the 10-message session lifetime cap.
- **[FAILURE SCENARIO]:** Effective limits are 2× configured today and N× the day you scale out; an abuser needs only to wait for a deploy (or force a restart via S1) to refresh their session allowance. LLM spend scales with the gap.
- **[REFACTOR ACTION]:** Move counters to Postgres (an `UPSERT`-based sliding window is fine at this traffic; you already run pg_cron for cleanup) or a managed Redis. Keep the in-memory limiter as a local pre-filter only.

### S4 — Per-token full re-render of an unbounded, unmemoized chat list

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Performance (client)
- **[THE ROOT CAUSE]:** Every streamed token copies the whole message array (`ChatIsland.tsx:486–496`) and re-renders every `ChatMessage` — no `React.memo`, keys are array indices (`:974`), and each render re-runs ReactMarkdown plus the A1 mega-regex over every message. `relevantVerses` grows append-only across the whole conversation (`:461–465`) with dedup applied only to the other verse source.
- **[FAILURE SCENARIO]:** A long pastoral conversation on a mid-range phone: typing latency climbs with every exchange, the verse rail accumulates duplicates, and streaming visibly stutters — the flagship interaction degrading in proportion to how engaged the user is.
- **[REFACTOR ACTION]:** `React.memo` on `ChatMessage` keyed by stable message ids; isolate the streaming message so only it re-renders per token; dedupe `relevantVerses` at append.

### S5 — The whole product balances on one small public database

- **[SEVERITY]:** MEDIUM (capacity) — see O3 for the exposure half
- **[RISK PROFILE]:** Scalability / Reliability
- **[THE ROOT CAUSE]:** `deployment/main.tf:338–356` — single `B_Standard_B2s` (2 vCPU / 4 GB) Postgres Flexible Server, no HA standby, serving vector search for 12 translations plus all app traffic, with the backend allowed to scale to 2 replicas against it.
- **[FAILURE SCENARIO]:** Migration 007's README already documents the fear: concurrent multilingual HNSW queries evict each other's index pages and the box thrashes. Any burst of S2 full scans turns fear into incident; there is no replica to fail over to.
- **[REFACTOR ACTION]:** Fix S2 first (it buys the most headroom per euro), add `pg_prewarm` for hot indexes (extension is already allow-listed), and write down the upgrade trigger: at what P95 do you move off B2s?

### S6 — `runBlocking` in the hot path, twice

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Performance (mobile)
- **[THE ROOT CAUSE]:** `android/.../TurnstileInterceptor.kt:85, 97` — `runBlocking { withTimeoutOrNull(5s/8s) }` parks OkHttp worker threads waiting for a WebView token. `ChatViewModel.kt:183` — `runBlocking { themePreferences.themeModeFlow.first() }` blocks the main thread at ViewModel construction on a cold DataStore disk read.
- **[FAILURE SCENARIO]:** Slow Turnstile widget + OkHttp's default 5-thread-per-host dispatcher = all network I/O queued behind token waits. The main-thread `runBlocking` is a startup-ANR candidate on slow storage — precisely the devices your global audience uses.
- **[REFACTOR ACTION]:** Make token acquisition a suspend fun in an Authenticator-style layer, not an interceptor block; load the theme asynchronously with a sensible default frame.

### S7 — Death by a thousand round-trips

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Performance
- **[THE ROOT CAUSE]:** Every hybrid search runs ranking SQL then a second hydration `SELECT … WHERE id IN (…)` (`repository.py:405–410` et al.); FTS recomputes `to_tsvector('simple', v.text)` per query in the CTE (`:366–369`) with no persisted tsvector/GIN column; frontend `isVerseReferenced` is O(verses × refs) inside a render-path memo (`verseExtraction.ts:1015–1073`).
- **[FAILURE SCENARIO]:** None of these fails alone; together they set the baseline latency floor that makes S5's small box feel smaller.
- **[REFACTOR ACTION]:** Persist a generated tsvector column with a GIN index; fold hydration into the ranking query; index verse refs into a Set before the loop.

### S8 — Ollama: five minutes of hope, no breaker

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Reliability
- **[THE ROOT CAUSE]:** `api/providers/ollama.py:55` — `AsyncClient(timeout=300.0)`, no retry, no circuit breaker, and `model_override` silently ignored (`:66, 100`) while other providers honor it.
- **[FAILURE SCENARIO]:** In any Ollama-backed deployment a wedged model holds request slots for 5 minutes each; a "switch model" config change appears to work while silently serving the old model.
- **[REFACTOR ACTION]:** Sane timeout (≤60s), wrap with the same breaker OpenRouter gets, honor or reject `model_override` explicitly.

---

## 4. DOCUMENTATION & TEST GAPS

### D1 — The deployment doc describes a deployment that no longer exists

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Maintainability / Operations
- **[THE ROOT CAUSE]:** `DEPLOYMENT.md:19–54` documents docker-compose behind a Cloudflare Tunnel to `getinspiredbythebible.ai4you.sh`. Actual production is Azure Container Apps + Terraform + `voxquieta.org` (`azure-deploy.yml`, `deployment/main.tf`). Azure is not mentioned once.
- **[FAILURE SCENARIO]:** The person doing incident response at 2 a.m. — or your successor — follows the only deployment document in the repo and operates on infrastructure that was decommissioned. Every minute of an outage spent discovering the doc is fiction is a minute the doc caused.
- **[REFACTOR ACTION]:** Rewrite `DEPLOYMENT.md` around the Azure reality (the `azure-deploy.yml` job graph is the outline); move the compose instructions to `LOCAL_DEVELOPMENT.md`.

### D2 — End-to-end coverage: one spec, and it's about a button

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Test coverage
- **[THE ROOT CAUSE]:** The entire Playwright suite is `e2e/turnstile-ready.spec.ts` (4 tests on button/prompt state). Playwright's `webServer` auto-start is commented out "due to Node version compatibility" (`playwright.config.ts:19–27`). Untested end-to-end: chat streaming, verse-link click → chapter modal, church finder, feedback, language switch with conversation preservation, error states.
- **[FAILURE SCENARIO]:** The exact class of bug you keep shipping (E3 — works in unit-tested extraction, broken on real click) is invisible to CI, because the only tests that would catch integration seams don't exist.
- **[REFACTOR ACTION]:** Fix the webServer config (the Node issue is a pinned-version problem, not a law of physics), then add the two highest-value specs: full chat stream against a mocked SSE backend, and verse-click → chapter modal in a non-English locale.

### D3 — Android's merge gate is decorative where it matters

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Test coverage / Process
- **[THE ROOT CAUSE]:** Compose UI tests are excluded from the required unit-test task (`app/build.gradle.kts:337–341`) and run in a separate workflow with `continue-on-error: true` (`android-compose-tests.yml:32–42`) so "flakiness cannot block merges". The OWASP CVE scan runs nightly-only and never gates PRs (`android-dependency-check.yml`). Instrumented coverage is a single `MainActivityTest`.
- **[FAILURE SCENARIO]:** A UI regression merges with a red-but-ignored check that everyone has trained themselves not to read; a critical CVE lands Friday evening and ships in Saturday's release because the scan that knew about it runs at 3 a.m. and blocks nothing.
- **[REFACTOR ACTION]:** Quarantine the individually-flaky tests, not the whole tier — make the Compose workflow required with a retry policy. Add the dependency check (fail on CVSS ≥ 9) to the PR pipeline; keep the deep nightly scan.

### D4 — The untested modules are precisely the load-bearing ones

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Test coverage
- **[THE ROOT CAUSE]:** No dedicated tests for: `utils/rate_limiter.py` (the abuse control), `utils/session_tracker.py` (the analytics), `feedback/blocked_samples.py`, `providers/azure_openai.py` (the *production* embedding provider — its content-safety cousin is tested, it isn't). And no test pins the OpenRouter exhaustion message to the route's substring match — which is exactly how E1 shipped and survived.
- **[FAILURE SCENARIO]:** E1 already demonstrated the scenario. The next silent contract break between provider and route ships the same way.
- **[REFACTOR ACTION]:** One test file per module above; for cross-module string/code contracts, a single contract test that imports both sides.

### D5 — The type checker is excused from checking the tests

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Test coverage / Maintainability
- **[THE ROOT CAUSE]:** `frontend/tsconfig.json` excludes `*.test.ts(x)` and `src/test/**` from `tsc --noEmit`; 26 test files (including the 2,370-line verse suite) are never typechecked. `react-hooks/exhaustive-deps` is warn-only, and `ChatIsland.tsx:213, 221, 244, 282` lean on `[]` effects that reference outer values.
- **[FAILURE SCENARIO]:** A refactor changes a function signature; tests keep "passing" against stale typed assumptions until they fail at runtime in CI — or worse, keep passing while asserting the wrong thing. The suppressed deps warnings are exactly where stale-closure bugs incubate.
- **[REFACTOR ACTION]:** Add a `tsconfig.test.json` that includes tests in typecheck; promote `exhaustive-deps` to error and annotate the intentional cases individually.

### D6 — Two sources of configuration truth, both confident

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Operations
- **[THE ROOT CAUSE]:** `api/.env.example` disagrees with `api/config.py` defaults: `DEBUG=true` (`:88`) vs safe-off; `content_safety_mode` documented as `keyword_only` (`:160`) vs actual default `ml_only` (`config.py:235`); different `turnstile_skip_paths` lists; a concrete `bible123` DATABASE_URL (`:49`) where config demands a placeholder. `RateLimiter.__init__` carries a divergent default (100) from config (10) (`rate_limiter.py:38` vs `config.py:177`).
- **[FAILURE SCENARIO]:** An operator copies `.env.example` in good faith and boots production with `DEBUG=true` — uvicorn reload plus SQLAlchemy `echo=True` logging every query *including embedding vectors* into App Insights, at App-Insights prices.
- **[REFACTOR ACTION]:** Generate `.env.example` from the pydantic `Settings` schema (one script, run in CI) so it cannot drift. Ship example defaults safe-side (`DEBUG=false`).

### D7 — Doc rot as a lifestyle

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Maintainability
- **[THE ROOT CAUSE]:** Three agent-guidance files (`AGENTS.md`, `AGENTS.md.old`, `AGENTS.old.md`); committed backups (`scripts/load_bible.py.backup`, stray `ChapterModal.test.tsx.backup`); duplicate BITB story numbers across `docs/BACKLOG_STORIES/` (multiple BITB-018/-037/-043/-050); `changelog.json` both committed and regenerated at build (`app/build.gradle.kts:274–331`); six docker-compose variants with no README explaining which is canonical.
- **[FAILURE SCENARIO]:** Nothing explodes. Instead, every newcomer (human or AI agent — and the `.old` files get slurped into agent context) burns an hour distinguishing live truth from fossils, forever.
- **[REFACTOR ACTION]:** One deletion PR; add `*.backup`/`*.old` to `.gitignore` and a pre-commit deny pattern; document the compose-file matrix in five lines.

---

## 5. OPERATIONAL / SECURITY RISK

### O1 — The default compose file is a dev stack with the keys taped to the door *(hand-verified)*

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Security / Operations
- **[THE ROOT CAUSE]:** `docker-compose.yml` (the file `docker compose up` picks by default): `POSTGRES_PASSWORD=bible123` in plaintext (`:67`), Postgres published on `0.0.0.0:5432` (`:64`), Ollama on `0.0.0.0:11434`, uvicorn `--reload` with a source bind-mount, frontend as `npm run dev`, zero restart policies or resource limits, `ollama/ollama:latest` unpinned (`:38`). The hardened bindings live in `docker-compose.dev.yml` — the *non-default* file.
- **[FAILURE SCENARIO]:** Anyone runs the documented quick start on a VPS or a laptop on café Wi-Fi: their Postgres and their GPU-backed Ollama are now open to the network with a password that is literally in this public repository. Shodan finds open 11434 ports daily.
- **[REFACTOR ACTION]:** Swap the file roles: default compose binds `127.0.0.1`, requires an env file for credentials, pins images. Keep the all-interfaces variant behind an explicit `-f` flag with a warning banner.

### O2 — Content safety: off by default, open on failure

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Security / Safety
- **[THE ROOT CAUSE]:** `content_safety_enabled` defaults `False` (`api/config.py:234`). When on, every stage fails open: OpenAI moderation → keyword fallback on bare `except Exception` (`content_safety.py:426–428`), Llama Guard → allow on transient error (`:351–361`) and on *empty response* (`llama_guard.py:111–113`), Azure stage → allow on exception (`:482–494`).
- **[FAILURE SCENARIO]:** A pastoral-care product serving people in crisis, in 11 languages, silently loses its self-harm/violence screening whenever a moderation upstream hiccups — and no alert fires, because fail-open branches only log.
- **[REFACTOR ACTION]:** For self-harm/violence categories specifically, fail *closed* (keyword-stage minimum always runs — it's local and free). Emit a metric on every fail-open branch and alert on its rate. Flip the default on.

### O3 — Production database on the public internet, disaster recovery: hope

- **[SEVERITY]:** HIGH
- **[RISK PROFILE]:** Security / Reliability
- **[THE ROOT CAUSE]:** `deployment/main.tf:349` — `public_network_access_enabled = true` on the prod Postgres Flexible Server; `:342` `geo_redundant_backup_enabled = false`; 7-day backup retention; no HA (`high_availability` appears only in `ignore_changes`, `:355–356`).
- **[FAILURE SCENARIO]:** Exposure: the DB's attack surface is every IP on earth plus a firewall rule, guarding rows of user-adjacent feedback and contact data. DR: a region incident or a bad migration discovered on day 8 means the data — including all generated embeddings, which cost real API money to rebuild — is simply gone.
- **[REFACTOR ACTION]:** Private endpoint + VNet integration to Container Apps (Terraform change, no app change). Enable geo-redundant backup — at B2s scale it costs pocket change. Document the restore procedure and *test it once*.

### O4 — CORS: credentials allowed, everything allowed, localhost forever

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Security
- **[THE ROOT CAUSE]:** `api/main.py:245–246` — `allow_credentials=True` with `allow_methods=["*"]`, `allow_headers=["*"]`, and origins that unconditionally include `localhost:3000/3001` even in production (`:211–215`).
- **[FAILURE SCENARIO]:** Any process on a user's machine that can bind localhost:3000 gets a credentialed, any-method, any-header pass to your production API in that user's browser context. Low likelihood, zero cost to fix.
- **[REFACTOR ACTION]:** Localhost origins only when `settings.debug`; enumerate the methods and headers actually used.

### O5 — Free-for-all telemetry endpoint

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Security / Cost
- **[THE ROOT CAUSE]:** `POST /api/v1/client-errors` (`api/main.py:324`) is unauthenticated, Turnstile-exempt (`config.py:208` skip-list), un-rate-limited, and does `await request.json()` on arbitrary bodies before any size check. Its output flows to App Insights, which bills by ingestion.
- **[FAILURE SCENARIO]:** A script POSTs garbage at line rate; you pay Azure for the privilege of storing it, and real client errors drown in noise. Secondary: multi-megabyte JSON bodies chew event-loop time on parse.
- **[REFACTOR ACTION]:** Content-length cap (16 KB), per-IP token bucket (the limiter exists), and a schema check before accepting.

### O6 — The 72-kilobyte deploy workflow

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Operations / Maintainability
- **[THE ROOT CAUSE]:** `.github/workflows/azure-deploy.yml` is a single 72 KB file: `workflow_run`-chained triggering, ~10 jobs, repeated `always() && (result=='success' || result=='skipped')` gating (`:1339–1343, 1423–1426`), Azure SP credentials assembled inline in multiple jobs, and resource names hardcoded under an explicit TODO (`:122–126`, `bible-app-*` vs the Vox Quieta rename).
- **[FAILURE SCENARIO]:** The `always()/skipped` lattice means one mis-set output skips deploy *silently* — CI is green, prod is stale, and nobody knows until a user reports a fixed bug still broken. The rename TODO means every future infra change must remember the lie in the names.
- **[REFACTOR ACTION]:** Split into composite actions / reusable workflows per concern (build, tf, deploy, seed); replace result-string gating with explicit `needs` + job-level `if`; do the rename or delete the TODO — a two-year-old TODO is documentation of learned helplessness.

### O7 — Supply-chain seams

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Security
- **[THE ROOT CAUSE]:** Bandit skips B608, the SQL-string-construction check, repo-wide (`.pre-commit-config.yaml:59`) — in a codebase that hand-builds SQL (`repository.py:304–657`). Dependabot ignores **all** semver-major updates in every ecosystem (`.github/dependabot.yml:19–21, 70–72`). Frontend runs `node:25-alpine` (bleeding-edge, short-support). Android pulls markdown rendering from JitPack (`settings.gradle.kts:25–27`) and force-downgrades BouncyCastle to 1.77 (`build.gradle.kts:20–28`).
- **[FAILURE SCENARIO]:** Majors ignored forever = a security-fix-only major (they happen) never gets proposed, and the eventual forced upgrade is a multi-major death march. The B608 skip means the one tool positioned to catch a future injection in the hand-built SQL is told not to look.
- **[REFACTOR ACTION]:** Re-enable B608 with targeted `# nosec` on the audited query builders; change dependabot majors from *ignored* to *grouped quarterly*; pin Node to the current LTS; vendor or mirror the JitPack dependency.

### O8 — Release engineering by coincidence (Android)

- **[SEVERITY]:** MEDIUM
- **[RISK PROFILE]:** Operations
- **[THE ROOT CAUSE]:** `versionCode` = Unix epoch seconds (`android-publish.yml:194, 209`) — collides if two builds start the same second and burns the 2.1B code space; versionName is extracted by two different mechanisms (gradle regex on the release-please manifest vs workflow grep, `app/build.gradle.kts:24–35` vs `android-publish.yml:202–203`); the promote lane's default source track is the literal space-containing string `"extend testing"` parsed by comma-splitting bash (`fastlane/Fastfile:118`, `android-publish.yml:370–397`); CI's "Build Prod APK" artifact is a **debuggable, debug-keyed build pointed at production** (`android-ci.yml:341–346`).
- **[FAILURE SCENARIO]:** The two versionName extractors disagree after a manifest format change and Play rejects the upload mid-release; someone sideloads the "Prod APK" artifact believing it's a release build and files ghost bugs — or worse, distributes a debuggable binary.
- **[REFACTOR ACTION]:** Derive versionCode from the release-please version (monotonic by construction); one versionName extractor, used by both; rename the CI artifact `debug-apk-prod-backend`; give the track a space-free id.

### O9 — Monitoring that assumes the world never changes

- **[SEVERITY]:** LOW
- **[RISK PROFILE]:** Operations
- **[THE ROOT CAUSE]:** `prod-monitor.yml` hardcodes a fallback backend FQDN (`:62`) and resolves the Log Analytics workspace as `[0].name` (`:243–245`) — first-item-wins. `scripts/validate-env.py` cross-checks env vars by regex-parsing compose YAML and Terraform HCL (`:47–112`), and only the base compose file at that.
- **[FAILURE SCENARIO]:** A second workspace appears in the resource group and log-scan silently starts scanning the wrong one — the monitor keeps passing while blind. The env validator blesses configs it never actually parsed.
- **[REFACTOR ACTION]:** Resolve the workspace by name/tag, not index; point the fallback URL at a variable; have validate-env consume `terraform output` and `docker compose config` (real parsers) instead of regex.

---

## Closing verdict

The pattern across all five categories is the same pattern: **this codebase is excellent at the second implementation and negligent about the first abstraction.** Three verse parsers instead of one spec. Two fetch paths instead of one client. Two error maps, two language stores, two versionName extractors, six compose files, three AGENTS.md. Each copy was faster to write than the abstraction — and each is now a place where the next bug is already waiting.

The good news: almost nothing here requires a rewrite. S1 is a three-line fix. E1 is a typed exception. E3 is four lines. O3 and O4 are config. The two genuinely expensive items — A1 (unify the parser) and A2/A3 (split the monoliths) — are the ones that pay compounding dividends, because they are where the team demonstrably keeps paying today.

*Next audit: run `/risk-audit` (see `docs/AUDIT_PLAYBOOK.md`). Diff against this report; mark each finding NEW / STILL OPEN / RESOLVED.*
