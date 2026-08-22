# Adversarial Risk Audit Playbook

How to run the recurring architecture & risk audit of Vox Quieta. The audit is adversarial by design: its job is to find what will break, rot, or bite — not to celebrate what works.

## Cadence

- **Quarterly**, and additionally after any of: a new platform/module, a database schema overhaul, a deployment-target change, or a provider/LLM-stack change.
- Reports live in `docs/audits/YYYY-MM-adversarial-audit.md`. Never overwrite an old report — the diff between reports is the point.

## How to run

In Claude Code, from the repo root:

```
/risk-audit
```

The command (defined in `.claude/commands/risk-audit.md`) carries the full persona, procedure, output protocol, and diff rules. It reads this playbook for scope and severity. To run the audit with a different AI tool or a human reviewer, hand them both files.

Budget: a thorough run reads several hundred files. Expect it to take a while; the command delegates each of the four areas to a parallel `risk-auditor` subagent (`.claude/agents/risk-auditor.md`) to keep it tractable.

For a narrower or delegated audit that shouldn't touch `docs/audits/` or git — e.g. "just audit `api/` for this PR", or a check run from another agent/task — invoke the `risk-auditor` subagent directly (Agent tool, `subagent_type: risk-auditor`). It carries the same persona, checklists, and output format as the command but is strictly read-only: it returns the report as text instead of writing and committing it.

## Scope map & per-area checklists

Four areas. Each checklist item is a question the auditor must answer with file:line evidence, not vibes. These lists were distilled from the July 2026 baseline audit — extend them when a new class of finding appears.

### 1. Backend — `api/`

- Provider layer (`providers/`): fallback/breaker logic duplicated between stream and non-stream paths? Error contracts between provider and routes typed, or string-matched? Timeouts sane on every outbound call?
- Async hygiene: any sync HTTP clients (`httpx.Client`, `requests`) or other blocking calls reachable from `async def` routes? `runBlocking`-equivalents? Grep for `httpx.Client(` and check every call site.
- Database (`scripture/`, `feedback/`): do vector queries go through the index-friendly candidate-pool pattern, or full-scan `WHERE similarity >= x` predicates? Every embedding column indexed? Leading-wildcard ILIKE? Session/transaction contracts honored (fresh session per retry attempt; commit only on writes)?
- Guardrails: which security controls fail open (Turnstile, content safety, rate limiting)? Are fail-open branches metered/alerted? Is the rate limiter still per-process in-memory while prod runs multiple replicas?
- Config: does `.env.example` agree with `config.py` defaults? Any allowed config values that raise "not implemented" at runtime? Debug flags that would be catastrophic in prod?
- Startup: does the app boot when its dependencies are broken (DB init failure swallowed)? Does readiness reflect that?

### 2. Web frontend — `frontend/`

- The monolith watch: `ChatIsland.tsx` and `api.ts` — growing or shrinking since last audit? Duplicated request/error paths converged yet?
- Streaming: per-token re-render cost, memoization on message components, unbounded accumulations (verse lists, message arrays), mutable closures inside state updaters.
- Verse parsing: still hand-synchronized with Android/backend (see cross-cutting)? Regex complexity/ReDoS surface? Circular imports with load-order contracts?
- i18n edge cases: do interaction paths (click handlers) apply the same digit/book normalization as extraction paths? Test any new logic with non-Latin numerals and localized book names.
- Storage: all `localStorage`/`sessionStorage` access guarded?
- Build: `NEXT_PUBLIC_*` defaults that could leak localhost into a prod bundle; Node base-image on LTS?

### 3. Android — `android/`

- The god-object watch: `ChatViewModel.kt` line count and UiState field count vs last audit.
- Room: does every schema version bump have a Migration + migration test? Destructive-fallback policy explicit?
- Threading: `runBlocking` on the main thread or OkHttp interceptor threads? Blocking reads at ViewModel construction?
- Backend contract: magic numbers mirroring server config (session limits, message length)? Error classification by `errorBody` substring?
- Preferences: single source of truth, or dual SharedPreferences/DataStore stores that can desync?
- Release: versionCode/versionName derivation consistent and collision-free? What does CI publish as an artifact and is it labeled honestly?

### 4. Infra / CI / scripts / docs

- Compose files: is the *default* `docker-compose.yml` safe to run (loopback bindings, no committed credentials, pinned images, restart policies)? How many compose variants exist and is the matrix documented?
- Terraform (`deployment/`): DB network exposure, HA, geo-redundant backup, retention; resource sizing vs measured load; names still matching reality?
- Workflows (`.github/workflows/`): monolith workflows with `always()/skipped` gating that can skip deploys silently? Non-required test tiers (`continue-on-error`) that have become decorative? Security scans that run on cron but never gate PRs?
- Migrations (`scripts/migrations/`): checksums actually verified? Version-number collisions? Rollback story? Does the base schema (`init.sql`) still match what prod actually runs (vector dims, index types)?
- Docs: does `DEPLOYMENT.md` describe the real deployment? Committed `.backup`/`.old` files? Contradictory duplicate docs?
- Toolchain: pre-commit skips (bandit codes), dependabot ignore rules, unpinned base images, third-party registries (JitPack etc.).

### Cross-cutting: the parity ledger

This project maintains hand-synchronized logic across platforms. Every audit must re-check each entry — these drift silently:

| Logic | Copies |
|---|---|
| Verse-reference regex | `frontend/src/lib/versePatterns.ts` · `android/.../ChatMessageItem.kt` · `api/utils/verse_parser.py` — cross-checked by the shared regression corpus `tests/fixtures/verse_reference_corpus.json` (BITB-059 AC#4) |
| Localized book-name map | Canonical: `tests/fixtures/localized_book_map.json` (BITB-059). Generated: `android/.../utils/LocalizedBookToEnglish.kt` **and** `frontend/src/lib/localizedBookMap.generated.ts`, both via `scripts/generate_localized_book_map.py --check` (CI-guarded). Reconciled (not generated — see rationale in the story): `api/utils/translation_registry.py`, held contradiction-free by `api/tests/test_localized_book_map_registry_parity.py` against a reviewed, pinned gap allowlist (`tests/fixtures/localized_book_map_registry_gaps.json`). Still open: the regex grammar itself (Phase 3, see the row above) is not part of this generator. |
| Session/message limits | `api/config.py` · `android/.../ChatViewModel.kt` (`MAX_INTERACTIONS`, `MAX_MESSAGE_LENGTH`) |
| Error contracts | provider error strings ↔ route/client substring matches (backend routes, Android `mapExceptionToMessage`) |
| UI strings | `frontend/messages/*.json` · `android/.../res/values-*/strings.xml` |

If an entry has been unified since the last audit, celebrate briefly, remove the row, and check the generator instead.

## Severity rubric

| Severity | Meaning |
|---|---|
| **CRITICAL** | Actively causing damage or a single event away from outage/data loss/large cost; or a structural flaw the team demonstrably keeps paying for (recurring fix commits). |
| **HIGH** | Realistic production failure or security exposure with a plausible trigger; or debt that materially slows every change in an area. |
| **MEDIUM** | Needs a less likely trigger or has a contained blast radius; will bite eventually. |
| **LOW** | Friction, hygiene, or a landmine that requires bad luck to step on. |

Rank by **blast radius × likelihood**. A finding without a concrete failure scenario is not a finding.

## Report lifecycle

1. New report is written by `/risk-audit` with findings marked NEW / STILL OPEN / RESOLVED against the previous report.
2. Findings worth fixing get promoted to backlog stories (`docs/BACKLOG_STORIES/BITB-xxx-*.md`) referencing the finding ID (e.g. `2026-07 S1`).
3. A finding STILL OPEN across three consecutive audits gets escalated in the report's executive summary — at that point it's a decision, not an oversight, and the report should say whose.

## Baseline

The first report is `docs/audits/2026-07-adversarial-audit.md` (47 findings: 2 CRITICAL, 15 HIGH, 24 MEDIUM, 6 LOW — machine-verified by `tools/audit-metrics/`). All future runs diff against the latest report in that directory.

## Metrics & trends

`tools/audit-metrics/` (companion to `tools/repo-metrics/`) turns the audit history into a trend: a weighted risk score per report, hotspot-file line counts, and hygiene counters, rendered as `docs/audits/metrics/report.md` and a dashboard at `docs/audits/metrics/index.html` (published on the GitHub Pages site under `/audit/`, next to the coding-analysis dashboard at the root).

- Run `make audit-metrics` after every `/risk-audit` so each report gets a same-day snapshot.
- The `audit-metrics.yml` workflow also snapshots monthly and whenever a new audit report lands on `main`, so hotspot/hygiene drift stays visible between audits.
- When a finding is fixed or a new monolith appears, update `HOTSPOTS` / `HYGIENE_COUNTERS` at the top of `tools/audit-metrics/analyze.py` (keep them in sync with the parity ledger above).
