# BITB-212: Orchestrator Delegation Discipline — Never Edit Application Code Directly

**Status:** 🎯 Todo (PR pending)
**Priority:** P2
**Size:** S
**Created:** 2026-10-22
**Found by:** Live session-death diagnosis on BITB-054 / PR #1192, 2026-10-22

## User Story

**As** the operator of the KubeOpenCode orchestrator, **I want** the orchestrator
agent to dispatch every implementation — including trivial CI fixes — to specialist
subagents, **so that** heavy build/CI-log output lands in disposable subagent
sessions instead of exhausting the orchestrator's context window and killing the
workstream mid-flight.

## Why This Exists

Observed live on 2026-10-22 while landing BITB-054 (PR #1192):

1. The feature implementation was correctly delegated to `android-expert`.
2. The follow-up CI-fix loop was NOT: ~10+ rounds of direct orchestrator edits
   ("it's one import, faster to do it myself"), each ingesting
   `gh run view --log-failed` output (100+ lines) into the orchestrator session.
3. The session grew past the model context limit; compaction failed
   ("Session too large to compact — context exceeds model limit even after
   stripping media") and the workstream had to be handed off mid-flight.
4. Each individual fix was genuinely trivial — the failure was structural:
   nothing in the orchestrator prompt forbade direct implementation, every
   round felt like a legitimate exception, and AGENTS.md's "trivial one-liners
   may skip the relay" line reads as permission to self-fix.

The existing prompt *described* delegation (Plan → Delegate → Verify → Report)
but never *enforced* it: `edit`/`write` tools fully enabled, no CI-loop
procedure, no log-ingestion budget, no reporting requirement.

## Requirements

### R1 — Prompt: "Delegation Discipline" section (hard rules)

- Explicit never-implement contract with an **edit allowlist**: opencode config,
  `AGENTS.md`, backlog/story docs, PR metadata via `gh`, scratch files outside
  the repo.
- **CI red → dispatch** procedure: cheap status polls
  (`gh pr view --json statusCheckRollup`), bounded error excerpts (≤40 lines),
  a fix brief with unique task token, and the subagent reads full logs itself
  via the run URL.
- **Context-hygiene budget**: ~40-line cap on any log/tool output the
  orchestrator ingests; full logs belong in subagent sessions.
- **Report contract**: every report names the agent behind each change.
- **Stop-and-dispatch triggers**, including the "this fix is too small to
  delegate" reasoning that caused the failure.
- Mapping of AGENTS.md's Plan → Build → Verify relay onto opencode agents
  (Build = specialist dispatch, Verify = `verifier` dispatch) and an explicit
  note that the "trivial one-liners" exemption does not apply to the
  orchestrator.

### R2 — Permissions: `edit` denies on application-code paths

Orchestrator frontmatter gains `permission.edit` with `"*": allow` first and
denies last (last match wins) for `**/api/**`, `**/frontend/**`,
`**/android/**`, `**/deployment/**`, `**/scripts/**`, `**/data/**`. A
permission denial acts as an in-flow reminder to dispatch. Bash-based file
writes (`sed -i`, python scripts) cannot be permission-blocked and remain
covered by the prompt only — documented residual risk.

### R3 — Generator compatibility

`.opencode/agents/orchestrator.md` is the source of truth; `opencode.json` is
regenerated via `make gen-opencode-config`. The generator forwards the
`permission` dict verbatim (verified in `scripts/generate-opencode-config.py`).
Because the orchestrator's `description` changed, the roster suffix appended to
every agent's prompt also updates — expected regeneration noise.

## Acceptance Criteria

- [ ] Orchestrator prompt contains the Delegation Discipline section: allowlist,
      CI-red dispatch procedure, stop-and-dispatch triggers, report contract
- [ ] `permission.edit` denies present in frontmatter AND in the generated
      `opencode.json`
- [ ] `make verify-opencode-config` passes (valid JSON)
- [ ] Rollout documented in the PR: merge → `make sync-opencode-configmap` →
      pod restart (config is not hot-reloaded)
- [ ] Live validation (post-rollout, owner-observed): the next CI-red event is
      handled by a fix-brief dispatch visible in the task registry, with no
      orchestrator commits on application code

## Out of Scope

- Hard-enforcing bash-based file writes (would need a plugin hook on
  `tool.execute.before`; prompt-only for now)
- Changing AGENTS.md's "trivial one-liners" exemption for interactive Claude
  Code sessions
- BITB-169 follow-ups (L2 mailbox)

## References

- Session diagnosis: BITB-054 / PR #1192, 2026-10-22 ("Session too large to
  compact")
- Related: BITB-169 (task-reliability: dispatch recovery), BITB-173 (fallback
  model chain)
