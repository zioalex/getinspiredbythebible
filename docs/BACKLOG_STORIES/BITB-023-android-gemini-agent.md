# BITB-023: Add Gemini 2.5 Pro Android Agent to opencode.json

**Priority:** P1 (High)
**Status:** 🎯 Todo
**Size:** S (< 2 hours)
**Created:** 2026-03-06

---

## Background

The project currently has a dedicated `android-expert` agent in `opencode.json` powered by
`anthropic/claude-sonnet-4-6`. As the Android surface grows toward Play Store readiness, we
want to add a second, specialised Android agent that uses **Google Gemini 2.5 Pro** as its
model.

Gemini 2.5 Pro is Google's flagship model and has demonstrated strong performance on
Android/Kotlin tasks — it is also the natural choice when the provider being tested is
Google-native. Having it available as a named agent lets any engineer (or the orchestrator)
explicitly route Android work to it when experimenting with model quality or cost trade-offs.

---

## User Story

**As a** developer working on the Android app,
**I want** a dedicated `android-gemini` agent in `opencode.json` backed by Gemini 2.5 Pro,
**so that** I can route Android development tasks to Google's model and compare quality
against the existing `android-expert` (Claude-based) agent, without touching any other
agent configuration.

---

## Functional Requirements

- [ ] A new agent named **`android-gemini`** is added to the `agent` block in `opencode.json`
- [ ] The agent's `model` is set to the correct Gemini 2.5 Pro model ID for the provider
      that is already configured in the project (check existing `provider` block and
      `opencode.json` conventions; if Google provider is not present, add the minimal
      provider entry needed)
- [ ] The agent's `mode` is `"subagent"` (consistent with `android-expert` and
      `fullstack-engineer`)
- [ ] The agent's `prompt` is a complete, self-contained Android engineering system prompt
      that includes:
      - Kotlin / Jetpack Compose / Material 3 expertise
      - MVVM Clean Architecture, Hilt DI, Room, Retrofit, Coroutines / Flow
      - All 7 workflow rules already present in the existing `android-expert` prompt
        (feature branches, PRs, `make pre-commit`, branch naming, PR description format, etc.)
      - A clear statement that it should prefer Google/Jetpack APIs and idioms
- [ ] The agent has `tools` block: `bash: true`, `edit: true`, `write: true`
      (matching the existing `android-expert` tool grants)
- [ ] The `orchestrator` agent's `permission.task` block is updated to also allow
      delegating to `android-gemini`
- [ ] No other agents, providers, or settings are modified

---

## Non-Functional Requirements

- [ ] **Correctness:** The Gemini 2.5 Pro model ID must be the real, currently-available
      model identifier. Validate with a live call before committing (Rule 7).
- [ ] **Consistency:** Prompt length, tone, and rule set must be consistent with the
      existing `android-expert` prompt so both agents are interchangeable for Android work.
- [ ] **No regressions:** All existing agents continue to work exactly as before.
- [ ] **JSON validity:** `opencode.json` must remain valid JSON after the change.

---

## Acceptance Criteria

- [ ] `opencode.json` contains a new `android-gemini` agent with `"mode": "subagent"` and
      the correct Gemini 2.5 Pro model ID
- [ ] The `orchestrator` permission table lists `android-gemini` alongside `android-expert`,
      `fullstack-engineer`, and `infra-engineer`
- [ ] Running `cat opencode.json | python3 -m json.tool` (or equivalent) exits 0 — valid JSON
- [ ] The model ID resolves to a real Gemini 2.5 Pro model (verified with a live test call
      before committing)
- [ ] No existing agent (`android-expert`, `orchestrator`, `fullstack-engineer`,
      `infra-engineer`, `product-owner`) has been modified in any way
- [ ] PR description documents: which provider entry was used, which model ID, and the
      result of the live validation call
- [ ] CI is green

---

## Tech Constraints

- `opencode.json` uses the OpenCode AI config schema (`"$schema": "https://opencode.ai/config.json"`)
- The Google / Gemini provider may need a new entry in the `provider` block — follow the
  same pattern as the existing `ollama` provider (npm package, options, models array)
- The correct npm package for Gemini via OpenCode is `@ai-sdk/google` (verify this)
- Model ID format for Gemini 2.5 Pro — research the exact string; likely
  `"gemini-2.5-pro"` or `"gemini-2.5-pro-preview-..."` — confirm with a live API call
  before hard-coding it
- The `GOOGLE_GENERATIVE_AI_API_KEY` environment variable (or equivalent) must be
  documented in the PR so the human can add it to their environment if not present

---

## Out of Scope

- Changing the model of any existing agent
- Adding agents for non-Android work
- Routing logic changes — the orchestrator continues to choose which agent to delegate to
- Any code changes to the Android app itself
- Any changes to CI/CD pipelines

---

## Definition of Done

- [ ] `opencode.json` updated with `android-gemini` agent
- [ ] `orchestrator` permission table updated
- [ ] JSON validity confirmed
- [ ] Live Gemini 2.5 Pro call validated before commit (Rule 7)
- [ ] PR open with green CI
- [ ] PR description documents model ID and validation evidence
- [ ] Story marked ✅ Done in backlog
