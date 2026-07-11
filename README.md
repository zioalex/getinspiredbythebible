# Vox Quieta

[![Prod Monitor](https://github.com/zioalex/getinspiredbythebible/actions/workflows/prod-monitor.yml/badge.svg)](https://github.com/zioalex/getinspiredbythebible/actions/workflows/prod-monitor.yml)

A conversational AI that helps people find spiritual encouragement and relevant scripture
based on their life situations. Built with a modular architecture that supports multiple
LLM backends.

## 🌟 Features

- **AI-Powered Conversations**: Natural dialogue grounded in Biblical text
- **Semantic Scripture Search**: Find relevant verses based on meaning, not just keywords
- **Multilingual Interface**: Available in English, Italian, and German with automatic browser language detection
- **Configurable LLM Backend**: Start with Ollama (local), switch to Claude, OpenRouter, or OpenAI later
- **REST API**: Ready for mobile app development
- **Modern Web Interface**: Clean, responsive chat UI

## 🏗️ Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    Backend API (FastAPI)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐   │
│  │ LLM Provider│  │ Scripture   │  │ Embedding          │   │
│  │ (Ollama/    │  │ Search      │  │ Provider           │   │
│  │  Claude/    │  │ Service     │  │                    │   │
│  │  OpenRouter)│  │             │  │                    │   │
│  └─────────────┘  └─────────────┘  └────────────────────┘   │
└───────┬─────────────────┬─────────────────┬─────────────────┘
        │                 │                 │
┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼───────┐
│    Ollama     │ │  PostgreSQL   │ │   pgvector    │
│ (Local LLM)   │ │ (Bible Data)  │ │ (Embeddings)  │
└───────────────┘ └───────────────┘ └───────────────┘
```

## 🚀 Quick Start

> Full guide with every run mode (local, side-by-side dev, local against the
> production DB + LLMs): **[docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md)**

### Prerequisites

- Docker & Docker Compose (v2, `docker compose`)
- 8GB+ GPU (recommended) or CPU with 16GB+ RAM for Ollama

### 1. Start the fully local stack

```bash
make docker-up        # CPU  (make docker-up-gpu for NVIDIA GPU)
```

On first run this automatically:

- creates `.env.local` from the committed `.env.local.example` template,
- pulls the Ollama models (`mistral:7b`, `mxbai-embed-large`, 5–10 min),
- loads the Bible and generates embeddings via the one-shot `db-init`
  container (`docker compose logs -f db-init` to follow progress).

```bash
docker compose logs -f   # watch all services
make docker-down         # stop
```

### 2. Access the App

- **Web App**: <http://localhost:3000>
- **API Docs**: <http://localhost:8000/docs>
- **Health Check**: <http://localhost:8000/health/live>

### Run locally against the production DB and LLMs

```bash
cp .env.production.example .env.production   # fill in secrets
make az-pg-add-ip                            # allow your IP on the Azure PG firewall
make docker-up-local-prod                    # local containers -> prod DB + OpenRouter/Azure OpenAI
```

See [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) for details, the
ACR-backend variant, and troubleshooting.

## 📁 Project Structure

```text
vox-quieta/
├── docker-compose.yml      # Container orchestration
├── api/                    # FastAPI backend
│   ├── main.py            # Application entry point
│   ├── config.py          # Configuration settings
│   ├── providers/         # LLM provider abstraction
│   │   ├── base.py       # Provider interface
│   │   ├── ollama.py     # Ollama implementation
│   │   ├── claude.py     # Claude implementation
│   │   ├── openrouter.py # OpenRouter implementation
│   │   └── factory.py    # Provider factory
│   ├── scripture/         # Bible data layer
│   │   ├── models.py     # Database models
│   │   ├── database.py   # DB connection
│   │   ├── repository.py # Data queries
│   │   └── search.py     # Semantic search
│   ├── chat/              # Chat logic
│   │   ├── service.py    # Chat orchestration
│   │   └── prompts.py    # System prompts
│   └── routes/            # API endpoints
├── frontend/              # Next.js web app
│   └── src/
│       ├── app/          # Pages
│       ├── components/   # UI components
│       └── lib/          # API client
├── scripts/               # Utility scripts
│   ├── load_bible.py     # Load Bible data
│   └── create_embeddings.py # Generate vectors
└── data/                  # Local data storage
```

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM backend: `ollama`, `claude`, `openrouter`, `openai` |
| `LLM_MODEL` | `llama3:8b` (compose default: `mistral:7b`) | Model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `mxbai-embed-large` | Embedding model (multilingual, 1024 dims) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | - | For Claude provider |
| `OPENAI_API_KEY` | - | For OpenAI provider and OpenAI Moderation (content safety `keyword_only`/`hybrid`) |
| `OPENROUTER_API_KEY` | - | For OpenRouter provider |

#### Frontend build-time variables

These are inlined into the Next.js bundle at build time (e.g.
`docker build --build-arg ...` or via the CI env).

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL. |
| `NEXT_PUBLIC_TURNSTILE_SITE_KEY` | _(unset)_ | Cloudflare Turnstile site key. See note below. |

**About `NEXT_PUBLIC_TURNSTILE_SITE_KEY`:** When set to a real site key,
the frontend skips the runtime `GET /config` round-trip and starts
loading the Turnstile widget on first paint — closing the brief window
in which a fast first message could race past Turnstile and get bounced
with `403 TURNSTILE_REQUIRED`. The site key is **public by design** and
visible to every browser that loads the widget; only the backend
**secret** key (used to call Cloudflare's `siteverify`) must stay
private. Leave the variable unset (or empty) to fall back to the
runtime `/config` path. To disable Turnstile entirely, set
`TURNSTILE_ENABLED=false` on the backend — `/config` will then report
that to the frontend, which will not gate any requests.

### Switching LLM Providers

#### Using Claude

```bash
# In docker-compose.yml or .env
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your-api-key-here
```

#### Using OpenRouter (Free Models Available)

OpenRouter provides access to various LLMs including free models. Get your API key at [openrouter.ai/keys](https://openrouter.ai/keys).

```bash
# In docker-compose.yml or .env
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free  # or google/gemma-2-9b-it:free
OPENROUTER_API_KEY=sk-or-v1-...
EMBEDDING_PROVIDER=ollama  # OpenRouter doesn't support embeddings
```

**Note**: OpenRouter doesn't support embedding generation, so keep `EMBEDDING_PROVIDER=ollama` for semantic search to work.

## 🚢 Deployment Options

### Important: Embedding Requirement

The semantic search feature requires **embeddings** to be generated for all Bible verses. Currently,
only Ollama supports embedding generation in this project. This means:

- **OpenRouter requires Ollama** - Even when using OpenRouter for chat, you still need Ollama
  running somewhere for embeddings
- **Not fully serverless** - Free hosting services (Railway free tier, Render free tier) typically
  lack resources to run Ollama
- **OpenAI embeddings** - Not yet implemented (would enable fully serverless deployment but costs money)

### Deployment Option A: OpenRouter + Hosted Ollama (Hybrid)

**Best for**: Production deployment with moderate budget

**Requirements**:

- Paid hosting service with GPU or 16GB+ RAM (Railway Pro, Render standard, AWS EC2, etc.)
- Separate Ollama instance running 24/7 for embeddings

**Setup**:

```bash
# Deploy API to serverless platform (Railway, Render, etc.)
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
EMBEDDING_PROVIDER=ollama
OLLAMA_HOST=https://your-ollama-instance.com  # Hosted Ollama endpoint

# Separate Ollama deployment (Railway Pro, EC2, etc.)
# Must run: mxbai-embed-large model (multilingual, 1024 dimensions)
```

**Pros**: Free LLM calls, fast response times
**Cons**: Still requires hosting Ollama (~$10-20/month minimum)

### Deployment Option B: Pre-Generated Embeddings (Advanced)

**Best for**: Fully static deployment, lowest ongoing cost

**Requirements**:

- One-time embedding generation (run locally or on temporary cloud instance)
- Database with pre-generated embeddings
- OpenRouter for LLM only

**Setup**:

1. Generate embeddings locally using Ollama:

   ```bash
   # Run once locally or on temp cloud instance
   docker compose up -d
   python scripts/load_bible.py
   python scripts/create_embeddings.py  # Takes 30-60 minutes
   ```

2. Export database with embeddings:

   ```bash
   pg_dump bibledb > bible_with_embeddings.sql
   ```

3. Deploy to cloud database (Neon, Supabase, etc.) and API platform:

   ```bash
   # Import embeddings to cloud database
   psql $DATABASE_URL < bible_with_embeddings.sql

   # Deploy API with OpenRouter
   LLM_PROVIDER=openrouter
   OPENROUTER_API_KEY=sk-or-v1-...
   EMBEDDING_PROVIDER=ollama  # Keep this for code compatibility
   OLLAMA_HOST=http://localhost:11434  # Won't be used for new embeddings
   ```

**Pros**: No ongoing Ollama hosting costs, fully serverless API
**Cons**: Complex setup, can't generate new embeddings without Ollama, requires re-deployment for Bible data updates

### Deployment Option C: Full Ollama Stack (Local/Self-Hosted)

**Best for**: Local development, self-hosting, privacy-focused deployments

**Requirements**:

- Server/computer with GPU or 16GB+ RAM
- Docker support

**Setup**:

```bash
# Use docker-compose.yml as-is
docker compose up -d

# All services run locally
LLM_PROVIDER=ollama  # or openrouter if you prefer
EMBEDDING_PROVIDER=ollama
```

**Pros**: Full control, privacy, no API costs, can regenerate embeddings anytime
**Cons**: Requires adequate hardware, higher resource usage

### Recommended Approach

- **Development**: Option C (full local Ollama)
- **Production (budget)**: Option B (pre-generated embeddings + OpenRouter)
- **Production (best UX)**: Option A (hosted Ollama + OpenRouter) or full Ollama on adequate hardware

## 🌍 Internationalization (i18n)

The frontend supports multiple languages using [next-intl](https://next-intl.dev).

**Supported Languages:**

| Code | Language | URL |
|------|----------|-----|
| `en` | English (default) | `/en` |
| `it` | Italian | `/it` |
| `de` | German | `/de` |

**How it works:**

- All routes are locale-prefixed (e.g., `/en/`, `/it/`, `/de/`)
- Visiting `/` automatically redirects to the best locale based on your browser's language settings
- Users can switch languages at any time using the language selector in the header
- Translation files are in `frontend/messages/` (one JSON file per locale)

### Adding a New Language

1. Copy `frontend/messages/en.json` to `frontend/messages/{locale}.json` and translate all values
2. Add the locale to `frontend/src/i18n/routing.ts`:

   ```ts
   locales: ["en", "it", "de", "fr"],  // add new locale
   ```

3. Add the locale label to `frontend/src/components/LanguageSwitcher.tsx`
4. Add `hreflang` in `frontend/src/app/[locale]/layout.tsx` `generateMetadata()`
5. Run `npx vitest run` — tests automatically verify key consistency across all locales

## 🔌 API Reference

### Chat Endpoints

#### POST `/api/v1/chat`

Send a message and receive a Bible-grounded response.

```json
{
  "message": "I'm feeling anxious about my future",
  "conversation_history": [],
  "include_search": true
}
```

#### POST `/api/v1/chat/stream`

Stream a response in real-time (Server-Sent Events).

### Scripture Endpoints

#### GET `/api/v1/scripture/search?q={query}`

Semantic search for relevant verses.

#### GET `/api/v1/scripture/verse/{book}/{chapter}/{verse}`

Get a specific verse.

#### GET `/api/v1/scripture/chapter/{book}/{chapter}`

Get all verses in a chapter.

### Admin Diagnostics (Internal)

These endpoints are operational diagnostics and are not part of the public API schema.
They require the `X-Monitor-Probe-Secret` header.

#### GET `/api/v1/admin/translation-coverage`

Returns per-translation verse and embedding counts plus unusable language mappings
(`unusable_languages`) for supported UI languages whose translation data has zero
verses or zero embeddings.

## 🧪 Development

### Running Without Docker

```bash
# Terminal 1: Start PostgreSQL and Ollama
ollama serve

# Terminal 2: Start API
cd api
pip install -r requirements.txt
uvicorn main:app --reload

# Terminal 3: Start Frontend
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
cd api
pytest
```

## 🗺️ Roadmap

### Features

- [ ] Mobile app (React Native)
- [ ] User accounts and saved conversations
- [ ] Reading plans integration
- [ ] Audio Bible support
- [ ] Multiple Bible translations
- [x] Multilingual UI (English, Italian, German)
- [ ] Community features (shared verses)

### Technical Improvements

- [ ] Refactor SQLAlchemy models to use `Mapped[]` type annotations (see [docs/TECHNICAL_DEBT.md](docs/TECHNICAL_DEBT.md))
- [x] Add Vitest for frontend unit tests (186 tests across 17 suites)
- [ ] Add Playwright/Cypress for E2E tests
- [ ] Add code coverage reporting
- [ ] Mock Ollama in tests for faster execution

## 📚 Documentation

Additional documentation is available in the `docs/` directory:

- **[Local Development](docs/LOCAL_DEVELOPMENT.md)** - Every local run mode (local stack, dev stack, local → prod DB/LLMs)
- **[Architecture](docs/ARCHITECTURE.md)** - System architecture and design patterns
- **[Testing](docs/TESTING.md)** - Testing strategy and guidelines
- **[Deployment](DEPLOYMENT.md)** - Deployment options and infrastructure
- **[How to Enable Content Safety](docs/HOW-TO-ENABLE-CONTENT-SAFETY.md)** - Step-by-step
  guide to enable multi-language content safety filter (deployed 2026-03-04, currently
  disabled)
- **[How to Read Chat Stage Timings](docs/HOW-TO-READ-CHAT-STAGE-TIMINGS.md)** - Find the
  per-stage latency breakdown (`chat_stage_timings` log + `chat.stage.duration_ms` metric)
  in container logs and Application Insights
- **[GitHub Actions Security](docs/GITHUB_ACTIONS_SECURITY.md)** - CI/CD security best practices
- **[Technical Debt](docs/TECHNICAL_DEBT.md)** - Known issues and improvement roadmap
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

This project is licensed under the MIT License, which means you're free to use, modify,
and distribute this software. Bible text uses the KJV (public domain).

## 🙏 Contributing

Contributions welcome! Please read our contributing guidelines first.

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Keep commits atomic and well-described
- Follow the existing code style
- Add tests for new features
- Update documentation as needed
- Files to exclude from commits are listed in `.gitignore`

## 📋 What's Not Committed

The following files and directories are excluded from version control (see `.gitignore`):

- Environment variables (`.env` files)
- Python virtual environments (`.venv`, `venv/`)
- Node modules (`node_modules/`)
- Build outputs (`dist/`, `build/`, `.next/`)
- Database files (`*.db`, `*.sqlite`)
- IDE settings (`.vscode/`, `.idea/`)
- Logs and cache files
- OS-specific files (`.DS_Store`, `Thumbs.db`)

---

_"Your word is a lamp for my feet, a light on my path."_ - Psalm 119:105
