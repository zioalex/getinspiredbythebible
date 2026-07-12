# Which Models Actually Built This? — Toolchain Attribution Analysis

Companion to `dev-process-storyline.md`. Answers "which AI models and
harnesses did the work", mined from `Co-Authored-By` trailers across the full
`main` history (1,115 commits as of 2026-07-12), PR descriptions, and the
in-repo harness configs (`AGENTS.md`, `opencode.json`, `.claude/`).

## Headline

**642 of 990 non-bot commits — about 65% — carry an explicit AI co-author
trailer.** The real share is higher: the early history often shipped without
trailers, so "no trailer" does not mean "no AI".

## Commits by model (co-author trailers on `main`)

| Model / agent | Commits | Notes |
|---|---|---|
| Claude (unversioned trailer) | 294 | Claude Code sessions that signed without a version string |
| **Claude Opus 4.5** | **168** | The single biggest named contributor — the Jan–Feb workhorse |
| "Android Dev" alias | 77 | opencode subagents (mostly the March Android push) |
| Claude Opus 4.6 | 56 | Later Claude Code era |
| GitHub Copilot | 48 | 29 `copilot-swe-agent[bot]` + 19 `Copilot` trailers |
| Claude Sonnet 4.6 / 4.5 | 20 | Mostly Build-stage work in the relay |
| Moonshot Kimi K2.5 | 1 | A single experiment, preserved in the record |

Claude-family trailers total ~538 commits; 151 PR descriptions carry the
"Generated with Claude Code" footer.

## The three harnesses

1. **Claude Code** — the primary harness. `AGENTS.md` defines the
   Plan (Opus) → Build (Sonnet) → Verify (Opus) relay as the default
   operating procedure; `.claude/commands/` and `.claude/agents/` hold the
   slash commands (`/plan-build-verify`, `/risk-audit`) and auditor personas.
2. **opencode** — `opencode.json` defines a second, independent multi-agent
   org chart: an **orchestrator** on `github-copilot/claude-opus-4.6` that
   plans, delegates via `acpx_claude`, verifies, and is explicitly allowed to
   *self-improve by editing `AGENTS.md` and `opencode.json`*. Its specialist
   subagents run on deliberately cheaper/diverse models: `android-expert`,
   `fullstack-engineer`, and `infra-engineer` on **MiniMax M2.5 (free
   tier)**, `android-gemini` on **Qwen3-Coder via OpenRouter**, plus local
   **Ollama Qwen3 (8B / 30B)** models for offline work.
3. **GitHub Copilot coding agent** — delegated whole tasks end-to-end;
   `copilot-swe-agent[bot]` co-authored 29 commits, with 19 more Copilot
   trailers from review/completion assistance.

Runtime is multi-model too: the product itself falls back across
Ollama (local Mistral) → Claude → OpenRouter, so model plurality is an
architecture principle, not just a dev-tool choice.

## The eras (visible in the monthly trailer chart)

| Phase | Period | Signature |
|---|---|---|
| Opus 4.5 era | Jan–Feb 2026 | Bootstrap: backend, frontend, first deploy |
| opencode experiment | March 2026 | "Android Dev" alias spike — the Android app built by an opencode orchestrator + cheap subagents |
| Claude Code relay era | April 2026 → | Squash-merge discipline, Opus 4.6 + Sonnet, `/plan-build-verify`, audits |

## A perfect story beat: the attribution PR that never landed

PR **#816** ("add AI model and harness attribution to productivity
analysis") built exactly this analysis into the dashboard — and its
description contains the first-run findings. But it was **stacked on PR
#813's branch, which had already been merged**; GitHub merged #816 into the
now-dead base branch, so the feature never reached `main` and never shipped
to the live dashboard. Even the meta-analysis had a process bug. Use it in
the video: *"the dashboard that measures the AI's work was itself lost to an
AI workflow mistake — stacked-PR merge order. The numbers survived only
because the PR description recorded them."*

(Recovery is straightforward: cherry-pick #816's commit onto a fresh branch
from `main` — a good candidate for a follow-up PR.)

## Sources

- `git log origin/main --format='%(trailers:key=Co-authored-by)'` (2026-07-12, 1,115 commits)
- PR [#816](https://github.com/zioalex/getinspiredbythebible/pull/816) description (first-run findings, 2026-07-04)
- `opencode.json` (orchestrator + subagent models), `AGENTS.md` (relay), `.claude/` (commands, agents)
- PR body search: "Generated with Claude Code" → 151 PRs
