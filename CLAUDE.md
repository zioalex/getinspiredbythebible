# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bible Inspiration Chat - A conversational AI that helps people find spiritual encouragement
and relevant scripture based on their life situations. Built with FastAPI backend, Next.js
frontend, and PostgreSQL with pgvector for semantic search.

## Development Commands

### Environment Setup

```bash
# Setup development environment (creates venv, installs hooks, installs deps)
make setup-dev

# Activate virtual environment
source .venv/bin/activate
```

### Running the Application

```bash
# Start all services (Docker - CPU mode)
make docker-up
# OR with GPU support
make docker-up-gpu

# Stop services
make docker-down

# View logs
make docker-logs
```

### Running Backend API Locally

```bash
cd api
uvicorn main:app --reload
# API will be at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### Running Frontend Locally

```bash
cd frontend
npm install
npm run dev
# Frontend will be at http://localhost:3000
```

### Testing

```bash
# Run all tests (backend + frontend)
make test

# Backend tests only
make test-backend

# Frontend tests only
make test-frontend

# Run pytest directly for a specific test
cd api
../.venv/bin/python -m pytest tests/test_api.py -v

# Run single test function
cd api
../.venv/bin/python -m pytest tests/test_api.py::test_function_name -v
```

### Linting and Formatting

```bash
# Auto-format all code
make format

# Run all linters
make lint

# Run type checkers
make type-check

# Run security checks
make security

# Run all checks (lint, type-check, security, test)
make check-all

# Run pre-commit hooks manually
make pre-commit
```

### Database Setup

```bash
# After starting Docker services, load Bible data
cd scripts
pip install httpx asyncpg sqlalchemy

# Load Bible text into database
python load_bible.py

# Generate embeddings (takes 30-60 minutes)
python create_embeddings.py
```

### Cleanup

```bash
# Clean build artifacts and caches
make clean

# Clean everything including venv
make clean-all

# Fix Docker-created file permissions
make fix-permissions
```

## Architecture

### Backend Structure (FastAPI)

The API follows a layered architecture with provider abstraction for LLM flexibility:

```text
api/
├── main.py              # FastAPI app, CORS, lifespan, health endpoints
├── config.py            # Pydantic Settings (env vars, .env file)
├── providers/           # LLM Provider Abstraction Layer
│   ├── base.py         # Abstract interfaces (LLMProvider, EmbeddingProvider)
│   ├── factory.py      # Provider factory, dependency injection
│   ├── ollama.py       # Ollama implementation (default, local)
│   └── claude.py       # Anthropic Claude implementation
├── scripture/           # Bible Data Layer
│   ├── models.py       # SQLAlchemy models (Book, Chapter, Verse, Passage)
│   ├── database.py     # AsyncPG connection management
│   ├── repository.py   # Database queries (semantic search, text search)
│   └── search.py       # ScriptureSearchService (high-level API)
├── chat/                # Chat Orchestration
│   ├── service.py      # ChatService (combines search + LLM)
│   └── prompts.py      # System prompts and context building
└── routes/              # FastAPI Routers
    ├── chat.py         # /api/v1/chat, /api/v1/chat/stream
    └── scripture.py    # /api/v1/scripture/*
```

**Key Design Patterns:**

- **Provider Pattern**: `providers/base.py` defines abstract interfaces that all LLM/embedding
  providers implement. Switch providers via `LLM_PROVIDER` env var.
- **Dependency Injection**: FastAPI dependencies (`LLMProviderDep`, `EmbeddingProviderDep`)
  inject the configured provider into routes.
- **Service Layer**: `ChatService` orchestrates the conversation flow: scripture search →
  context building → LLM generation.
- **Repository Pattern**: `ScriptureRepository` encapsulates database queries,
  `ScriptureSearchService` provides high-level search API.

### Frontend Structure (Next.js)

```text
frontend/src/
├── app/
│   ├── page.tsx        # Main chat interface (Server Component)
│   ├── layout.tsx      # Root layout
│   └── globals.css     # Tailwind styles
├── components/
│   ├── ChatMessage.tsx # Message display with verse references
│   ├── VerseCard.tsx   # Verse display card
│   └── ChapterModal.tsx # Full chapter modal
└── lib/
    └── api.ts          # API client functions
```

### Database Models

- **Book**: Bible books (Genesis, Matthew, etc.)
- **Chapter**: Chapters within books
- **Verse**: Individual verses with pgvector embeddings for semantic search
- **Passage**: Multi-verse passages (e.g., "The Lord's Prayer") with embeddings
- **Topic**: Categorization system (hierarchical, with embeddings)

All embeddings use the `embedding_dimensions` setting (default 768 for nomic-embed-text).

### Semantic Search Flow

1. User sends message → `ChatService.chat()`
2. Generate embedding for user message via `EmbeddingProvider.embed()`
3. Query database using pgvector cosine similarity (`ScriptureRepository.search_verses_semantic()`)
4. Filter results by similarity threshold (default 0.35)
5. Build context prompt with top verses/passages
6. Send to LLM with system prompt + scripture context
7. Return grounded response to user

## Configuration

### Environment Variables

Configure via `api/.env` file (copy from `api/.env.example`):

- `LLM_PROVIDER`: `ollama` (default), `claude`, or `openai` (not implemented)
- `LLM_MODEL`: Model name (e.g., `llama3:8b`, `claude-sonnet-4-20250514`)
- `OLLAMA_HOST`: Ollama server URL (default: `http://localhost:11434`)
- `ANTHROPIC_API_KEY`: Required for Claude provider
- `EMBEDDING_PROVIDER`: `ollama` (default) or `openai` (not implemented)
- `EMBEDDING_MODEL`: Embedding model (default: `nomic-embed-text`)
- `DATABASE_URL`: PostgreSQL connection string

### Switching LLM Providers

To switch from Ollama to Claude:

1. Set `LLM_PROVIDER=claude` in `api/.env`
2. Set `ANTHROPIC_API_KEY=your-key`
3. Set `LLM_MODEL=claude-sonnet-4-20250514` (or desired model)
4. Restart API service

The provider factory (`providers/factory.py`) handles instantiation based on config.

## Code Style and Quality

### Python (Backend)

- **Formatter**: Black (line length 100)
- **Linter**: Ruff (replaces flake8, isort, etc.)
- **Type Checker**: MyPy (with `--ignore-missing-imports`)
- **Security**: Bandit (severity level LL)
- Pre-commit hooks enforce all checks automatically

### TypeScript (Frontend)

- **Formatter**: Prettier
- **Linter**: ESLint (next/core-web-vitals)
- **Type Checker**: TypeScript strict mode

### Pre-commit Hooks

Pre-commit hooks run automatically on `git commit`. Install with `make setup-dev` or manually:

```bash
pip install pre-commit
pre-commit install
```

Hooks include: trailing-whitespace, Black, Ruff, MyPy, Bandit, ESLint, Prettier,
detect-secrets, markdownlint, yamllint, shellcheck.

## Known Technical Debt

See `docs/TECHNICAL_DEBT.md` for detailed tracking. Key items:

1. **SQLAlchemy Models (Medium Priority)**: Refactor from `Column()` syntax to
   SQLAlchemy 2.0 `Mapped[]` annotations for better type safety and to remove MyPy
   suppressions in `scripture.*` and `routes.*` modules.

2. **Frontend Testing (Medium Priority)**: Add Jest/Vitest for component tests,
   React Testing Library for integration tests, Playwright/Cypress for E2E.

3. **Mock Ollama in Tests (Low Priority)**: Currently tests use real Ollama. Mock LLM
   providers to speed up tests and remove external dependency.

## API Endpoints

### Chat

- `POST /api/v1/chat` - Send message, receive Bible-grounded response
- `POST /api/v1/chat/stream` - Streaming response (SSE)

### Scripture

- `GET /api/v1/scripture/search?q={query}` - Semantic search
- `GET /api/v1/scripture/verse/{book}/{chapter}/{verse}` - Get specific verse
- `GET /api/v1/scripture/chapter/{book}/{chapter}` - Get chapter

### Health

- `GET /health` - Health check with provider status
- `GET /config` - Current configuration (non-sensitive)

## Common Development Tasks

### Adding a New LLM Provider

1. Create `api/providers/your_provider.py` implementing `LLMProvider` and optionally `EmbeddingProvider` from `base.py`
2. Add case to `create_llm_provider()` in `factory.py`
3. Update `config.py` to add new provider to `llm_provider` Literal type
4. Add provider-specific settings to `Settings` class
5. Update README.md configuration section

### Running Pre-commit Hooks on All Files

```bash
make pre-commit
# OR
pre-commit run --all-files
```

### Updating Secrets Baseline

If you add a new exception to secret detection:

```bash
make update-baseline
```

### Docker Permission Issues

If Docker creates files owned by root:

```bash
make fix-permissions
```
