# BITB-304: Align the Python Runtime, Fix the Claude Model Configuration, Probe Configured Models

**Status:** 🔍 In Review (PR #1291)
**Priority:** P1
**Size:** S
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows D1–D6.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 2.
**Commit:** `ci(api): test on the production Python version; fix Claude model config (BITB-304)`

## Problem

1. **Production runs code CI never ran.** `api/Dockerfile:8,29` builds on
   `python:3.14-slim`. Backend tests, MyPy, Black and Ruff all run on or target 3.12
   (`.github/workflows/test_update.yml:106,208,632`; `api/pyproject.toml:11,30,40`). No
   workflow mentions 3.14. Every pinned dependency in `api/requirements.txt` is exercised
   only on an interpreter that does not serve traffic. `AGENTS.md` also says
   "Python 3.12".
2. **Selecting Claude as the provider is broken twice over.**
   - `api/providers/factory.py:50` passes `config.llm_model`, whose default is
     `"llama3:8b"` (`api/config.py:24`), to `ClaudeProvider`. With `LLM_PROVIDER=claude`
     and no `LLM_MODEL`, Anthropic receives an Ollama model name.
   - The documented value, `claude-sonnet-4-20250514` (`api/providers/claude.py:29`,
     `api/.env.example:13`), was retired on 2026-06-15 according to Anthropic's
     deprecations page.
   Production uses OpenRouter, so this bites on the day someone switches provider during
   an outage.
3. **`LLM_PROVIDER=openai` passes validation and fails at first use**
   (`api/config.py:23`; July finding A5).
4. **Nothing tells you when a configured model disappears.** Primary and fallback are
   aggregator-hosted open models (`api/config.py:43-46`); the safety stack uses two more.
5. **Dependabot hides every major upgrade** (`.github/dependabot.yml:18-21,69-72`):
   `openai` is pinned at 1.109.1 with 3.49.0 published; `anthropic` at 0.125.0 with
   2.8.0 published.

## Decisions already made

1. **CI moves to 3.14; production stays on 3.14.** Both versions are supported until
   2028 or later, so the cheaper move is to test what is deployed. If a dependency has no
   3.14 wheel or a test fails only on 3.14, that is the finding this story exists to
   surface — fix it or pin the Dockerfile back to 3.12 **and say which** in the PR; do
   not leave the two different.
2. **One version, one place.** Add `.python-version` at the repo root; workflows use
   `python-version-file`; a test asserts the Dockerfile `FROM` tag matches it.
3. **Claude default:** the provider default becomes the current Sonnet alias from
   Anthropic's models page — look it up at build time, do not copy an ID from this file.
   The factory passes `config.llm_model` only when the operator set it explicitly;
   otherwise the provider's own default applies.
4. **Remove `"openai"` from the `llm_provider` literal.**
5. **Model probe is a scheduled workflow, not app code.** Weekly, it asks each provider's
   model-list endpoint whether every configured ID still exists and fails loudly if not.
   It makes no completion calls.
6. **Dependabot keeps ignoring majors**; a quarterly scheduled workflow writes one report to its
   job summary (no GitHub Issue) listing direct dependencies whose latest major is ahead.

## Requirements

1. `.python-version` (`3.14`); every `actions/setup-python` step in `.github/workflows/`
   reads it; `api/pyproject.toml` tool targets move to 3.14 (`py314` for Black and Ruff
   if the pinned tool versions support it — otherwise keep the highest supported target
   and say so).
2. Run the full backend suite and MyPy on 3.14 locally before pushing; fix what breaks.
3. Test: `api/Dockerfile` `FROM python:X.Y-slim` equals `.python-version`
   (add to an existing repo-consistency test module if there is one).
4. `AGENTS.md`: change "Python 3.12" to the real version in *Project Overview* and
   wherever else it appears (`grep -n "3\.12" AGENTS.md docs/*.md`).
5. Claude provider and factory (decision 3); update `api/.env.example` and
   `scripts/env-manifest.yaml` (`LLM_MODEL` is described there as Ollama-only — correct
   the description).
6. Remove `"openai"` from the literal (decision 4) and the "OpenAI: Coming soon" line
   in the API description (`api/main.py:332`).
7. `scripts/check_configured_models.py`: reads the configured model IDs from
   `api/config.py` defaults and `deployment/variables.tf` defaults; for OpenRouter IDs
   queries `GET https://openrouter.ai/api/v1/models` (public, no key); for the Claude
   default queries Anthropic's models endpoint only when `ANTHROPIC_API_KEY` is present,
   and otherwise prints "skipped". Exit non-zero when an ID is missing.
8. `.github/workflows/model-existence-probe.yml`: weekly cron + `workflow_dispatch`,
   runs the script. Pick a minute that is not `0` or `30`.
9. `.github/workflows/dependency-majors-report.yml`: quarterly, lists behind-by-a-major
   direct dependencies for `api/requirements.txt` and `frontend/package.json` in the job
   summary.
10. Document both workflows where the other scheduled workflows are documented.

## Tests (minimum)

- Factory: `LLM_PROVIDER=claude` with no `LLM_MODEL` → provider model equals the
  provider default, not `llama3:8b`; with `LLM_MODEL` set → that value.
- `Settings(llm_provider="openai")` → validation error.
- `check_configured_models.py` unit tests with the HTTP call mocked: all present → exit
  0; one missing → exit 1 and the ID is named; network error → exit 2 (distinct from
  "missing", so an outage is not read as a retirement).
- Dockerfile/`.python-version` consistency test.

## Acceptance criteria

- [ ] CI backend jobs run on the same minor version as `api/Dockerfile`
- [ ] A test fails if the two ever diverge again
- [ ] `LLM_PROVIDER=claude` works with no other variable than the API key
- [ ] `LLM_PROVIDER=openai` is rejected at start-up
- [ ] Weekly probe exists and passes on the day it merges
- [ ] `AGENTS.md` states the real Python version

## Out of scope

- Upgrading `openai` or `anthropic` to their current majors (file follow-ups from the
  first majors report).
- Changing the production model.

## Related

July audit A5, O7; BITB-236.
