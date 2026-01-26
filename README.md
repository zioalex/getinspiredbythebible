# Bible Inspiration Chat

A conversational AI that helps people find spiritual encouragement and relevant scripture
based on their life situations. Built with a modular architecture that supports multiple
LLM backends.

## 🌟 Features

- **AI-Powered Conversations**: Natural dialogue grounded in Biblical text
- **Semantic Scripture Search**: Find relevant verses based on meaning, not just keywords
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

### Prerequisites

- Docker & Docker Compose
- 8GB+ GPU (recommended) or CPU with 16GB+ RAM for Ollama

### 1. Clone and Setup

```bash
cd bible-chat
cp api/.env.example api/.env  # Create env file (optional)
```

### 2. Start Services

> **Note**: On first startup, Ollama will automatically pull the required models
> (`llama3:8b` and `mxbai-embed-large`). This may take 5-10 minutes depending on your
> internet connection.

```bash
# Start all services
docker-compose up -d

# Watch logs
docker-compose logs -f
```

### 3. Load Bible Data

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
cd scripts
pip install httpx asyncpg sqlalchemy

# Load Bible into database
python load_bible.py

# Generate embeddings (takes ~30-60 minutes)
python create_embeddings.py
```

### 4. Access the App

- **Web App**: <http://localhost:3000>
- **API Docs**: <http://localhost:8000/docs>
- **Health Check**: <http://localhost:8000/health>

## 📁 Project Structure

```text
bible-chat/
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
| `LLM_MODEL` | `llama3:8b` | Model name |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `mxbai-embed-large` | Embedding model (multilingual, 1024 dims) |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | - | For Claude provider |
| `OPENROUTER_API_KEY` | - | For OpenRouter provider |

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
- [ ] Community features (shared verses)

### Technical Improvements

- [ ] Refactor SQLAlchemy models to use `Mapped[]` type annotations (see [docs/TECHNICAL_DEBT.md](docs/TECHNICAL_DEBT.md))
- [ ] Add Jest/Vitest for frontend unit tests
- [ ] Add Playwright/Cypress for E2E tests
- [ ] Add code coverage reporting
- [ ] Mock Ollama in tests for faster execution

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

*"Your word is a lamp for my feet, a light on my path."* - Psalm 119:105
