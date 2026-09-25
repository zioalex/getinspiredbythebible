# BITB-163: Sync KubeOpenCode Fallback Table Once PR #1079 Merges

**Status:** 🎯 Todo
**Priority:** P3 — doc-only drift, no functional impact
**Size:** XS (single table edit in one Markdown file)
**Created:** 2026-09-25
**Related:** BITB-158 (KubeOpenCode dev image — this follow-up was filed during that story's v2
build), PR #1079 (Ultra → Super-Free + GPT-OSS-120B fallback swap, not yet merged as of this
writing)

---

## Problem

`deployment/kubeopencode/README.md`'s "Cross-provider Resilience" section documents the
2-hop fallback chain (OpenCode Zen → OpenRouter) with a table naming the actual fallback
models:

```text
| Agent group | Tier 1 | Tier 2 | Covers |
|---|---|---|---|
| All agents (nemotron/mimo prim) | opencode/muse-spark | openrouter/gemma-3-27b:free | ... |
| android-gemini (OpenRouter prim) | opencode/muse-spark | openrouter/gemma-3-27b:free | ... |
```

PR #1079 changes the fallback model names in `.opencode/agents/*.md` (and therefore in
`agents.md` and the generated `opencode.json`) — Ultra → Super-Free, plus a GPT-OSS-120B
addition — but has not merged yet. The table above was deliberately left unsynced rather than
edited to a value that wouldn't match the merged state either. This story tracks that
sync explicitly instead of leaving it as an unowned code comment.

## Why it matters

- The table is the only place a human reading `deployment/kubeopencode/README.md` sees the
  actual fallback model names; once it drifts from `agents.md`/`opencode.json` it actively
  misleads whoever is debugging a fallback event.
- Small and mechanical enough that it should not wait on a full backlog triage pass once
  PR #1079 lands — but also not urgent enough to block anything today.

## Acceptance Criteria

- [ ] Once PR #1079 merges, update `deployment/kubeopencode/README.md`'s "Cross-provider
      Resilience" table (tier 1 / tier 2 model names, and the `agents.md` doc table if it also
      references the pre-#1079 names) to match the merged state
- [ ] Cross-check against the generated `opencode.json` (`make gen-opencode-config`) so the
      documented names are exactly what ships, not paraphrased
- [ ] `make verify-opencode-config` still passes (this is a documentation-only change; no
      functional/config edit expected)

## Notes

- Filed during BITB-158's v2 build/verify round as a scoped, tracked follow-up rather than a
  dangling code comment — see that story and `docs/BACKLOG.md`'s BITB-158 entry for context.
- No urgency: the table is stale relative to a not-yet-merged PR, not relative to what's
  actually deployed. Do not action this until PR #1079 is confirmed merged.
