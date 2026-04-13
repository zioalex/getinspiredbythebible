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
