# BITB-123: opencode Agent Graph + KubeOpenCode Deployment Config

**Priority:** P2 (Medium)
**Status:** 🚧 In Progress (PR #1042 opened 2026-09-05)
**Size:** M (1-2 days)
**Created:** 2026-09-05

---

## Background

`opencode.json` currently holds all 5 agents **inline** with legacy `tools:` keys and a
custom `acpx_claude` tool, plus an `ollama` provider block that is not used in practice.
There is no `.opencode/agents/` directory, and no KubeOpenCode deployment manifest for
running the agent graph remotely. The three auditors under `.claude/agents/` (risk,
failure, seo) exist in Claude format only and are disconnected from opencode.

---

## User Story

**As a** developer running agents locally or on KubeOpenCode,
**I want** a 12-agent orchestration graph defined in `.opencode/agents/*.md` with a slim
`opencode.json`, plus an adhoc `deployment/kubeopencode/` folder with the Agent CRD,
**so that** local runs stay small-config while remote runs get model, fallback and
permission routing from version-controlled manifests.

---

## Functional Requirements

- [ ] `.opencode/agents/*.md` holds 12 agents: orchestrator (primary) + 11 subagents
      (android-expert, fullstack-engineer, infra-engineer, android-gemini, data-engineer,
      verse-parity-keeper, i18n-qa, verifier, risk-auditor, failure-forecaster, seo-auditor)
- [ ] `opencode.json` slimmed: `ollama` provider removed, inline subagent blocks removed;
      keeps `$schema` + thin `agent.build`/`agent.plan` mode overrides
- [ ] `deployment/kubeopencode/agent.yaml` — Agent CRD with primary + small models, the
      `opencode-runtime-fallback@0.2.4` plugin, provider timeout options, per-agent
      `fallback_models` (including orchestrator), credentials wiring
- [ ] `deployment/kubeopencode/agents.md` — documented 12-agent model table
- [ ] `deployment/kubeopencode/README.md` — `kubectl apply` steps + prerequisites
- [ ] `.claude/agents/` left untouched (no deletion, no migration)
- [ ] `opencode.json` remains valid JSON (`python -m json.tool` exits 0)

## Model Assignment

| Agent(s) | Model | Rationale |
|---|---|---|
| orchestrator | `github-copilot/claude-opus-5` (paid) | Strongest planner; fallback `opencode/muse-spark-1.3-contributor-free` in spec |
| android-expert, fullstack-engineer, infra-engineer, data-engineer | `opencode/nemotron-3-ultra-free` | Strong free builders |
| android-gemini | `openrouter/qwen/qwen3-coder` | Paid-tier coder, already used in repo (BITB-023) |
| verse-parity-keeper, i18n-qa | `opencode/mimo-v2.5-free` | Multilingual strength |
| verifier | `github-copilot/claude-opus-5` | Read-only, Opus per the Plan → Build → Verify relay |
| risk-auditor | `github-copilot/claude-opus-5` | Read-only, max quality for adversarial blast-radius reasoning |
| failure-forecaster, seo-auditor | `opencode/nemotron-3-ultra-free` | Read-only, stronger for calibrated forecast + SEO checklist |

## Non-Functional Requirements

- [ ] `make pre-commit` passes; `opencode agent list` shows all 12 agents
- [ ] No secrets in any committed file (detect-secrets hook must pass)

---

## Verification

- `python -m json.tool opencode.json` exits 0
- `opencode agent list` lists orchestrator + 11 subagents
- `make pre-commit` green
- PR opened against `main` with `chore(agents):` conventional title

---

## Follow-up: shared agent context (2026-09-12)

A live delegation smoke test against PR #1042 surfaced two prompt-content gaps
once the 12 agents were actually exercised:

1. `fullstack-engineer` reported that it owned `/backend`. This repo's backend
   is `api/` — no agent prompt stated the repository layout.
2. Asked to name an escalation target, agents invented siblings that do not
   exist in the graph ("Backend Engineer", "Design Agent"). No agent knew the
   other 11.

Fixed in `scripts/generate-opencode-config.py` by appending a shared context
block — authoritative repo layout, plus an **agent roster derived from the
parsed `.md` files** — to every agent prompt, rather than duplicating it across
12 files. New agents inherit it automatically and the roster cannot drift.
Guarded by 5 regression tests in `scripts/test_generate_opencode_config.py`.

The same smoke test also found a parallel-dispatch fault, tracked separately as
BITB-124.
