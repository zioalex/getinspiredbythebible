---
id: BITB-286
status: in-progress
priority: P2
size: S
created: 2026-11-09
---

# BITB-286: 2026-11-07→09 Session Cost Retrospective — $20.27 / 80 Sessions, What to Change

**Migration note (2026-11-13, status):** protocol/config fixes in the same PR; tooling follow-ups in BITB-287
**Migration note (2026-11-13, size):** (this record) + dispatched follow-ups
**Source:** operator request, after the arc exhausted a full $20 weekly OpenRouter key

## The ledger (from `/data/sessions/opencode.db`, table `session`)

Arc = 2026-11-07 21:20 UTC → 2026-11-09 ~17:00 UTC (the PR-queue triage →
question-deadlock → fallback-chain → config-gate → k8s-outage → folder-sunset →
stream-stall-watchdog arc).

- **80 sessions, $20.27 total** · 8.59M fresh input tokens · 593K output ·
  267M cache-read (the arc is only affordable because caching discounts
  ~97% of re-read history — long sessions are a cache-subsidized pattern).
- Cost concentration (top-heavy):
  - infra-engineer lane, 3 dispatches resumed into one session: **$4.64**
  - fullstack lane, 3 dispatches + 2 recoveries, one session: **$4.57**
  - orchestrator session (2 days): **$3.48**
  - one deepseek verifier-class session: **$2.38**
  - ~76 small sessions (smoke tests, scratch-instance probes, aborted
    spawns, noop children): **~$5.2** combined

## Value assessment (what was worth it)

- ~$13 of the $20 bought **~12 merged PRs of durable infrastructure** at
  ~$0.80/PR: the entire BITB-269/279/280/285/270 hardening stack (question-deny,
  registry + watchdogs, loader-contract plugin, free-tier fallback chains,
  checkout lockstep, pre-merge live-config gate, folder sunset, stream-stall
  watchdog) plus the dependabot unblock and integration validation.
- The tooling **already amortized**: the [T-270A] cancel-and-recover cost one
  registry grep + one resume (cents) versus the 2026-11-07 forensic marathon
  that consumed a large fraction of the orchestrator's early context.
- The resume-based lanes (3 dispatches per session) were the single best
  cost pattern: one brief amortized three times.

## Waste inventory (ranked)

1. **Two verifier dispatches that could not verify (~$4 + double latency).**
   Both returned static "cannot run tests/gh" reviews the orchestrator then
   redid with a handful of commands. Root cause: the verifier's bash
   allowlist had no `gh`, `node --test`, or venv-python patterns.
2. **The [T-1248LINT] odyssey (~$1.1 across 3 sessions + a 9h34m hang +
   the forensics to diagnose it)** — a 2-line YAML reflow became the most
   expensive single event, triggered by an orchestrator brief naming the
   wrong branch + the question-tool deadlock (both since fixed: brief
   hygiene codified; `question: deny` live).
3. **Two k8s-outage misdiagnoses** ("controller image mapping", "upstream
   broke :latest") — cheap in tokens, expensive in risk: the operator's
   falsifying question ("how did it suddenly work?") produced the correct
   root cause (probe budget vs slow cold boot), and the controller-restart
   advice actively accelerated the reverting re-render.
4. **The key-exhaustion evening** — tier-1 fallbacks never worked (dead
   `opencode/*` references), so a $20 limit killed every lane until manual
   intervention. Fixed permanently (free-tier tier-1); an evening of
   orchestrator turns died to it first.
5. **The BACKLOG.md reconciliation tax** — 4 manual union merges, each a
   full orchestrator turn, all the same mechanical pattern.
6. **Trivial dispatches on paid lanes** — smoke tests ran on fullstack
   (glm-5.3) to execute `git log`; free lanes existed for exactly this.

## Improvements (this PR implements the protocol/config tier)

1. ✅ **Verifier tool allowlist** extended (`.opencode/agents/verifier.md`):
   gh read commands, node test runners, venv python/pre-commit, make
   test/verify targets, timeout-wrapped variants — a verifier that cannot
   execute is theater.
2. ✅ **Falsification-first diagnostic discipline** (orchestrator.md):
   no theory without its disproof-check; model the controller's reaction
   before advising infra actions.
3. ✅ **Free-lane routing for trivial dispatches** (orchestrator.md).
4. ✅ **Session-per-incident guidance** (orchestrator.md): re-orient from
   stories + registry, not carried context.
5. ✅ **Resume-over-rebrief + `autoupdate` labels on every opened PR**
   (orchestrator.md; labels also applied to the open queue).
6. ✅ **Risk-tiered verification relay** (AGENTS.md): fresh verifier
   mandatory for high-risk diffs only; builder+CI+spot-checks for
   mechanical changes; verifier-tool readiness requirement.
7. ⏳ **Tooling tier → BITB-287**: BACKLOG.md merge driver, registry cost
   telemetry, budget guardrail.

## Acceptance Criteria

- [x] Ledger captured from the session DB (reproducible: SELECT against
      `/data/sessions/opencode.db`)
- [x] Verifier allowlist covers the actual verification surface (gh polls,
      node suites, venv python, make targets)
- [x] Falsification-first + free-lane + session-economics + autoupdate +
      resume-preference rules codified in the orchestrator definition
- [x] Risk-tiered verification amendment in AGENTS.md
- [ ] BITB-287 tooling implemented (separate PR)
- [ ] (owner) merge + sync + restart; the next verification round runs with
      an executing verifier; next arc's trivial dispatches land on free lanes

## Out of Scope

- Changing the paid-model posture (BITB-236) — the lanes are expensive by
  design; this story fixes waste, not posture
- OpenRouter key-limit configuration (owner-side dashboard setting; the
  repo-side guardrail is BITB-287's check target)
