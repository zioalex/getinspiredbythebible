# AGENTS.md - Claude Code Context

## Project Overview

**Vox Quieta** is a multilingual AI-powered Bible study app.
Users chat with an AI about the Bible, and the app detects verse references
in responses, linking them to scripture. Deployed on Azure.

**Tech stack:** Python 3.12 / FastAPI / PostgreSQL 16 + pgvector /
Next.js / React / TypeScript / Kotlin / Jetpack Compose / Terraform / Azure

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
cd android && ./gradlew lint
```

### All at once

```bash
make test           # Backend + frontend
make android-test   # Android unit tests
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

### Conventional Commits enforcement

**Conventional Commits are enforced on every PR** via
`.github/workflows/commitlint.yml` (`wagoid/commitlint-github-action`). PRs
whose commit messages do not follow the `type(scope): description` format will
fail CI. See `commitlint.config.cjs` for the full allowed type list.

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

## Common Pitfalls

1. **DATABASE_URL required for DB tests** - Most unit tests mock the DB,
   but integration tests need a real PostgreSQL with pgvector extension
2. **CJK verse regex** - Chinese/Korean patterns need special handling
   (no space between book name and chapter). Always test with CJK inputs
   when modifying verse parsing
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
