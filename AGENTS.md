# AGENTS.md - Claude Code Context

## Project Overview

**Vox Quieta** is a multilingual AI-powered Bible study app.
Users chat with an AI about the Bible, and the app detects verse references
in responses, linking them to scripture. Deployed on Azure.

**Tech stack:** Python 3.12 / FastAPI / PostgreSQL 16 + pgvector /
Next.js / React / TypeScript / Kotlin / Jetpack Compose / Terraform / Azure

## Standard Workflow: Plan → Build → Verify

**This is the default operating procedure for any non-trivial task** (a feature,
a bug fix, or a refactor — anything beyond a true one-line/typo change). It runs
as a three-stage relay across models so that planning and verification are done
by a stronger model and the bulk implementation by a faster one:

1. **Plan — Opus.** Explore the codebase first (read the relevant files, find
   existing utilities/patterns to reuse), then write an explicit plan: the
   problem, the precise changes per file, and how it will be verified. Resolve
   ambiguity with the user *before* coding, not after. Also create/update the
   backlog story (see *Backlog Hygiene*) as part of planning.
2. **Build — Sonnet.** Delegate the implementation to a Sonnet subagent
   (`Agent` with `model: sonnet`), handing it the approved plan as its brief.
   It makes all the code, test, migration, and i18n changes on the feature branch.
3. **Verify — Opus.** Spin up a *separate* Opus subagent (`Agent` with
   `model: opus`) to independently run the backend + frontend (+ Android, if
   touched) test suites and review the diff against the plan's acceptance
   criteria. It reports pass/fail with evidence; the main session fixes any gaps
   it finds before commit/PR.

   > **Why the strongest model verifies (not a cheaper one).** Verification is
   > the hardest reasoning step — catching a subtle bug the builder missed is
   > harder than writing the code — so it runs on the strongest reasoner, not a
   > weaker model that would rubber-stamp the very bugs it should catch. The
   > lever that makes it independent is a *fresh subagent with no build context*
   > that actually **runs the tests**, not model diversity. If you want a second,
   > uncorrelated pass, add a **Sonnet 5** verifier alongside (different lineage,
   > fails differently) — but keep Opus in the primary critic seat. **Haiku 4.5**
   > is only for cheap pre-gating (lint / typecheck / a quick smoke run), never
   > the final correctness verifier.

This composes with — it does not replace — the **Testing** rule (every change
ships with tests) and **Backlog Hygiene** (every change has a story). Trivial
one-liners may skip the relay, but still need tests where behaviour changes.

> One-shot entry point: the `/plan-build-verify <task>` slash command
> (`.claude/commands/plan-build-verify.md`) runs this relay end to end.

## Repository Layout

```text
api/                  Python backend (FastAPI)
  chat/               Chat service, prompts, topic extraction
  providers/          LLM & embedding provider abstraction
  scripture/          Bible database models, repository, semantic search
  routes/             API route handlers
  middleware/         CORS, rate limiting, access audit
  tests/              pytest test suite
  config.py           Pydantic Settings (all env vars)
  main.py             FastAPI app entrypoint

frontend/             Next.js web app
  src/app/            App router pages (Next.js)
  src/components/     React components
  src/lib/            Verse parsing, API client, utilities
  src/i18n/           next-intl routing config
  src/test/           Vitest test suite
  messages/           i18n translation JSON files (11 languages)

android/              Native Android app (Kotlin / Jetpack Compose)
  app/src/main/       Main source set
  app/src/test/       JVM unit tests

deployment/           Terraform configs for Azure
scripts/              DB init, embedding generation, migrations, env validation
data/                 Bible data files
docs/                 Project documentation
```

## Development Setup

Docker run modes (full matrix in `docs/LOCAL_DEVELOPMENT.md`):

```bash
make docker-up               # fully local stack (Ollama + local Postgres), auto-creates .env.local
make docker-up-dev           # second stack on shifted ports (3001/8001), auto-creates .env.dev
make docker-up-local-prod    # local containers -> PROD DB + cloud LLMs (needs .env.production)
```

### Backend

```bash
make setup-dev            # Creates venv, installs deps, sets up pre-commit hooks
source .venv/bin/activate
cd api && uvicorn main:app --reload
```

### Frontend

```bash
cd frontend && npm install && npm run dev
```

### Android

Requires JDK 17. Open `android/` in Android Studio or use Gradle CLI.

### Environment Variables

Source of truth: `scripts/env-manifest.yaml`

Critical variables:

- `DATABASE_URL` - PostgreSQL connection string (required for backend and tests)
- `LLM_PROVIDER` - `claude` | `ollama` | `openrouter`
- `ANTHROPIC_API_KEY` - Required when LLM_PROVIDER=claude
- `OPENROUTER_API_KEY` - Required when LLM_PROVIDER=openrouter
- `EMBEDDING_PROVIDER` - `azure_openai` | `ollama`
- `EMBEDDING_DIMENSIONS` - Vector dimensions (default 1536)
- `NEXT_PUBLIC_API_URL` - Backend URL for frontend

## Testing

> **Rule: every code change must ship with tests. No exceptions.**
>
> - Bug fix → add a regression test that would have caught the bug
> - New feature → add tests covering the happy path and key edge cases
> - Refactor → ensure existing tests still pass; add tests for any newly
>   reachable behaviour
>
> Do not open or update a PR without tests. CI running green is necessary
> but not sufficient — reviewers will reject PRs that lack coverage for
> the changed code.

### Multilingual & Multi-Version Correctness (required)

> **Rule: any change touching verse parsing, scripture grounding,
> citation/reference handling, search/retrieval, prompts, or anything else
> that is translation-dependent MUST be planned, implemented, verified, and
> tested across ALL 11 supported languages AND representative bible versions.**
>
> - Ship a **parametrized cross-language test** (en, it, de, es, fr, pt, ar, ru,
>   zh, hi, ko) — not an English-only happy path. English-shaped coverage that
>   silently breaks CJK/RTL/Devanagari is exactly how regressions ship.
> - Cover the variants that actually occur in the wild: **parenthesized/bracketed
>   citations** `(John 3:16)` / `[Salmo 23:1]`, **CJK/fullwidth punctuation**
>   `（…）` `「…」` `：` `，`, **RTL Arabic**, **Devanagari**, **German comma
>   separators** `Johannes 3,16`, **numbered books**, and **ranges**.
> - Prove **version-faithfulness**: the result must use the *user's selected
>   translation's* text, never a hardcoded one (test e.g. KJV vs WEB).
> - Verse detection lives in **three parsers that must stay in sync** (backend,
>   frontend, Android — see *Verse Detection / Parsing*). Mirror the change and
>   add a parity test in each. They diverge subtly (e.g. the frontend does not
>   support German comma separators; the backend does) — assert, don't assume.

### Backend Tests

```bash
# Unit tests (no DB needed for most tests)
cd api && python -m pytest tests/ -x -q

# With a real DB (needed for integration/DB tests)
DATABASE_URL=postgresql://user:pass@localhost/dbname python -m pytest tests/ -x -q  # pragma: allowlist secret

# Migration tests
cd scripts/migrations && DATABASE_URL=postgresql://test:test@localhost/test python -m pytest test_run_migrations.py -v  # pragma: allowlist secret
```

Pytest markers: `network`, `golden_set`, `functional`, `e2e`

### Frontend Tests

```bash
cd frontend && npx vitest run          # Unit tests
cd frontend && npm run lint            # ESLint
cd frontend && npx tsc --noEmit        # Type check
cd frontend && npm run build           # Build check
```

### Android Tests

```bash
cd android && ./gradlew testDebugUnitTest --no-daemon
cd android && ./gradlew testDebugCompose --no-daemon   # Robolectric Compose UI tests (BITB-034)
cd android && ./gradlew lint
```

Compose UI tests follow the `*ComposeTest.kt` filename convention and run via the dedicated
`testDebugCompose` Gradle task. They are isolated from the standard `testDebugUnitTest` job.
See `android/COMPOSE_TESTS.md` for the full tier description and rollout plan.

### All at once

```bash
make test                  # Backend + frontend
make android-test          # Android JVM unit tests
make android-test-compose  # Android Compose UI tests (Robolectric — separate tier)
```

## Code Style & Linting

### Python (api/)

- **Black** - formatter, line length 100, target Python 3.12
- **Ruff** - linter (replaces flake8/isort), rules: E,F,W,C90,I,N (E501 ignored)
- **MyPy** - type checker, `ignore_missing_imports=true`
- **Bandit** - security linter (skips B101, B601, B608)

### Frontend (frontend/)

- **ESLint 9** - flat config (`eslint.config.mjs`)
- **Prettier** - formatting
- **TypeScript** - strict mode via `tsconfig.json`

### Pre-commit Hooks

Configured in `.pre-commit-config.yaml`. Install with `make install-hooks`.

Hooks: trailing-whitespace, end-of-file-fixer, check-yaml/json, Black,
Ruff, MyPy, Bandit, hadolint (Dockerfiles), Prettier (YAML + frontend),
yamllint, detect-secrets, shellcheck, markdownlint, ESLint.

Format commands: `make format` (auto-fix Python + frontend)

## CI/CD Pipeline

### On Pull Request (`test_update.yml`)

| Job | What it does |
| ----- | ------------- |
| `backend-tests` | Ruff, Black, MyPy, pytest (PostgreSQL 16 + pgvector service) |
| `frontend-tests` | npm lint, tsc, vitest, build (Node 20.x + 22.x matrix) |
| `integration-tests` | Docker Compose: health check, scripture search, chat, streaming, frontend |
| `security-check` | Python + npm dependency vulnerability scans |

### Android CI (`android-ci.yml`)

| Job | What it does |
| ----- | ------------- |
| `translation-validation` | Ensures all strings exist in all locale files |
| `unit-tests` | JVM testDebugUnitTest |
| `lint` | Kotlin lint with baseline |
| `compile-check` | compileDebugKotlin + compileReleaseKotlin |
| `instrumented-tests` | Android emulator (API 29) |
| `secrets-scan` | TruffleHog + detect-secrets |
| `dependency-check` | OWASP Dependency-Check (CVE threshold 7.0) |
| `apk-security-check` | Manifest security flags |
| `build` | Production APK (gated by security checks) |

### Android Compose UI Tests (`android-compose-tests.yml`)

Independent workflow — **not a required check** while the tier stabilises.

| Job | What it does |
| ----- | ------------- |
| `compose-ui-tests` | Robolectric `testDebugCompose` — `*ComposeTest.kt` classes only |

Artifacts uploaded on every run: HTML report + JUnit XML (14-day retention).
See `android/COMPOSE_TESTS.md` for the tier design and promotion checklist.

### Deployment (`azure-deploy.yml`)

Deploys to Azure on push to `main`.

## Git Conventions

- **Commit format:** `type(scope): description` (imperative mood, lowercase)
- **Types:** `feat`, `fix`, `docs`, `chore`, `ci`, `refactor`, `test`, `merge`
- **Scope:** optional, e.g. `api`, `android`, `frontend`, `deps`
- **Examples:**
  - `feat(api): add access audit middleware (#388)`
  - `fix: add 27 Chinese book name aliases`
  - `docs: add BITB-025 backlog item`
- **Branch naming:** `feature/description`, `fix/description`, or `claude/description`

### Choosing the right type: `feat` vs `chore`

> **If a user can see or feel the change → `feat:`**
> **If only the codebase or pipeline changes → `chore:`/`ci:`/`build:`**

`chore:` is hidden in the changelog (`"hidden": true` in `release-please-config.json`).
Using it for user-visible work causes those changes to be silently absent from the
release notes. When in doubt, prefer `feat:`.

| Change | Correct type |
|--------|-------------|
| New icon, splash screen, or graphics | `feat:` |
| New screen or UI component | `feat:` |
| Copy/text change visible to the user | `feat:` |
| Bug the user could observe | `fix:` |
| Internal refactor with no user impact | `chore:` |
| CI workflow or tooling change | `ci:` |
| Dependency bump | `build:` |

### Conventional Commits enforcement

**Conventional Commits are enforced on every PR** via
`.github/workflows/commitlint.yml` (`wagoid/commitlint-github-action`). PRs
whose commit messages do not follow the `type(scope): description` format will
fail CI. See `commitlint.config.cjs` for the full allowed type list.

**The PR title itself must also be a conventional commit.** This repo uses
squash-merge, so the PR title becomes the commit subject on `main`.
`release-please` scans only top-level commit subjects — a non-conventional
PR title produces an unrecognised commit and the change is silently dropped
from the next release's changelog (this happened on #565 → v1.6.2). The
`Lint PR Title` job in `commitlint.yml` blocks merging until the title is a
valid conventional commit; rename the PR if it fails.

### Automated release tagging (release-please)

**Do NOT create `vX.Y.Z` git tags manually.** Semver tags are created
automatically by [release-please](https://github.com/googleapis/release-please)
whenever a "Release PR" is merged into `main`. The tag triggers
`android-publish.yml` which uploads the AAB to the Google Play internal track.

See `docs/RELEASE_PROCESS.md` for the full release flow, the required
`RELEASE_PLEASE_TOKEN` PAT secret, and instructions for promoting builds to
beta/production.

### Git Worktree Pattern

When making code changes (especially for Android or any task that should not
disturb the main working directory), always use `git worktree` under `/tmp/`:

```bash
# Create a new worktree from the latest remote main
git fetch origin
git worktree add /tmp/<short-name> -b <branch-name> origin/main

# Or check out an existing branch
git worktree add /tmp/<short-name> origin/<branch-name>

# Work inside the worktree
cd /tmp/<short-name>
# … make changes, commit, push …

# Clean up when done
git worktree remove /tmp/<short-name>
```

**Why `/tmp/`?** The main working directory
(`/home/asurace/github/getinspiredbythebible`) is shared and should not be
modified directly by automated agents. `/tmp/` is writable by GitHub Copilot
CLI and other agents without permission issues, and is cleaned up automatically
on reboot.

**Always clean up** worktrees with `git worktree remove` after pushing, to
avoid stale entries accumulating in `.git/worktrees/`.

### Backlog Hygiene

**The backlog is always kept in sync — no exceptions.**

- **Stories live in the repo, not in GitHub Issues.** This project does
  **not** use GitHub Issues for backlog/story tracking. Never create a
  GitHub Issue to capture a story, requirement, or follow-up — record it in
  the backlog files described below instead.
- `docs/BACKLOG.md` is the canonical prioritized list. `docs/BACKLOG_STORIES/` holds the detailed story files.
- **When creating a new story:** create the full story file in `docs/BACKLOG_STORIES/BITB-<NNN>-<slug>.md` *and* add a summary entry (status, size, date, one-liner, acceptance criteria, link to full story) in `docs/BACKLOG.md` under the correct priority section.
- **When completing a story:** update its status to `✅ Done` in `docs/BACKLOG.md`, add the PR number and completion date, and move the full story file to `docs/DONE/` if the folder exists.
- **When cancelling a story:** mark it `❌ Cancelled` in `docs/BACKLOG.md` with a short reason.
- **Always update `Last Updated`** at the top of `docs/BACKLOG.md` whenever you touch the file.
- **Story IDs are sequential.** Before creating a new story, check the highest existing `BITB-NNN` number in `docs/BACKLOG_STORIES/` and increment by one.

### Branch & PR Hygiene

**Never push to a branch that has a closed or merged PR.** If the PR for
a branch has been closed or merged, that branch is done. Create a new
branch (from `main`) for any further work, even if it's related. Pushing
to a dead branch causes confusion and orphaned commits.

**Always open a PR after committing work to a feature branch.** Whenever
you commit and push changes to a `claude/*`, `feature/*`, or `fix/*`
branch, immediately open a pull request against `main` (or update the
existing open PR if one already exists for that branch). Do not leave
commits sitting on a branch without an active PR — work that is not in a
PR is invisible to review and CI.

**If CI doesn't trigger after pushing or opening a PR, check for merge
conflicts first.** GitHub does not run workflows on a PR with unresolved
merge conflicts. Symptoms: empty `get_check_runs` result that stays
empty for more than a minute or two; the PR page shows "This branch has
conflicts that must be resolved." Resolution: rebase or merge `main`
into the branch (`git fetch origin && git merge origin/main`), resolve
conflicts, push — CI will start. Don't sit waiting for a CI signal that
will never arrive.

### Reproducible Repo Analyses

**Any repo/process analysis whose numbers get published or committed
(docs, dashboards, content, PR descriptions) must be reproducible from
the analysis tooling whenever feasible** — `tools/repo-metrics/` for
productivity/history questions, `tools/audit-metrics/` for audit trends.
If answering a question required a one-off `git log` dig (a new
attribution, a milestone date, a per-era breakdown), codify it into the
script as a normal report section before (or along with) publishing the
numbers, so the next monthly run keeps them fresh instead of letting a
hand-computed snapshot rot. Hand-mined numbers are acceptable only for
throwaway exploration, or where the source isn't in this repo's history;
cite the exact command in that case.

## Architecture Patterns

### Provider Abstraction (api/providers/)

Abstract base classes `LLMProvider` and `EmbeddingProvider` in `base.py`.
Factory functions in `factory.py` use `match/case` to create providers
by name.

- **LLM providers:** Claude, Ollama, OpenRouter
- **Embedding providers:** Azure OpenAI, Ollama
- **DI:** `LLMProviderDep` and `EmbeddingProviderDep` FastAPI dependency
  annotations with `lru_cache()` singletons

### Multi-Language / Translation System

**Single source of truth:** `api/utils/translation_registry.py`

Each language gets:

- `ENGLISH_TO_<LANGUAGE>` dict (66 books, English name -> localized name)
- Optional **citation forms** for grammatically inflected languages (e.g., Italian "Genesi" vs "della Genesi")
- **Aliases** dict for common abbreviations and variant names

Adding a new language:

1. Add `ENGLISH_TO_<LANGUAGE>` dict in `translation_registry.py`
2. Add aliases dict (abbreviations, variant spellings)
3. Optionally add citation forms (for grammatical languages)
4. The verse parser regex auto-updates from the registry
5. Update `book_names.py` reverse mapping
6. Add frontend translations in `frontend/messages/<locale>.json`
7. Add locale to `frontend/src/i18n/routing.ts`
8. Update Android string resources in `android/app/src/main/res/values-<locale>/`

**Supported UI languages (frontend):** en, it, de, es, fr, pt, ar, ru, zh, hi, ko

### Verse Detection / Parsing

Verse references are detected in three places (must stay in sync):

| Platform | File | Notes |
| ---------- | ------ | ------- |
| Backend | `api/utils/verse_parser.py` | Builds regex from `ALL_BOOK_NAMES` (translation_registry). Canonical. |
| Frontend | `frontend/src/lib/versePatterns.ts` | Multi-word book names, CJK no-space patterns, guillemet `<<>>` support |
| Android | `android/.../ChatMessageItem.kt` | Regex with connector words (`of`, `de`, `van`, `ke`, `al`), CJK + guillemet |

**CJK-specific:** Chinese/Korean book names have no space between name
and chapter number. Chinese also uses guillemet notation `<<BookName>>`.

### Verse Grounding & Citation Resolution

Post-generation grounding (`api/chat/verse_grounding.py`) rewrites an LLM's inline
verse quote to the canonical DB text. It only acts on a quote that **(a)** parses to
a reference via `extract_all_references` / `extract_inline_quotes` **and (b)** resolves
to DB text for the user's translation. If either fails — e.g. a parenthesized
reference the parser misses, or a translation with no rows — it no-ops as
`reason=unresolved` and the model's (possibly wrong) text is shown unchanged.

> **Pure-function tests that feed canonical text directly will hide integration
> bugs in the parse → resolve → ground path.** Always add an integration test
> through `chat()` / `chat_stream()` (mock `search_service.get_verse`) for any
> grounding or parser change, and assert the cited verse is both *resolved* and
> *corrected* — across languages, per the rule above.

## Common Pitfalls

1. **DATABASE_URL required for DB tests** - Most unit tests mock the DB,
   but integration tests need a real PostgreSQL with pgvector extension
2. **Verse regex is multilingual — test ALL 11 languages, not just English.**
   Chinese/Korean need no-space handling; references are commonly wrapped in
   `( )` `[ ]` or fullwidth `（ ）`. The backend `_VERSE_PATTERN` uses a
   *positive-whitelist* lookbehind: a wrapped reference was once silently dropped
   (so it never resolved from the DB and grounding became a no-op), while the
   frontend/Android use a *letter-negative* boundary and didn't share the bug.
   Keep the three parsers in sync **by boundary behaviour**, not just book lists;
   always test parenthesized + CJK/fullwidth-punctuation citations
3. **Three verse parsers must stay in sync** - Changes to verse detection
   must be mirrored across backend, frontend, and Android
4. **Translation registry is the source of truth** - Never hardcode book
   names elsewhere; always derive from `translation_registry.py`
5. **Pre-commit hooks need NVM** - The ESLint hook sources NVM to find the correct Node.js version
6. **`make format`** - Run this before committing to auto-fix formatting issues
7. **Frontend excludes** - Pre-commit trailing-whitespace and
   end-of-file-fixer exclude `frontend/` (handled by Prettier instead)
8. **Android string validation** - CI checks that all strings in `values/strings.xml` exist in every locale directory
9. **Never push to closed/merged PR branches** - Always create a fresh branch from `main` for new work
10. **`chore:` hides from changelog** - Asset, graphic, and UI changes that users can see must use `feat:`, not `chore:`. Using `chore:` for user-visible work causes the change to be silently dropped from release notes by release-please (see Git Conventions → Choosing the right type)
