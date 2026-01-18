# Bible Inspiration Chat - Architecture Design Document

**Version:** 1.0.0  
**Last Updated:** January 2026  
**Status:** Active Development

---

## Table of Contents

1. [Overview](#1-overview)
2. [System Architecture](#2-system-architecture)
3. [Component Design](#3-component-design)
4. [Data Architecture](#4-data-architecture)
5. [API Design](#5-api-design)
6. [Provider Abstraction Layer](#6-provider-abstraction-layer)
7. [Frontend Architecture](#7-frontend-architecture)
8. [Data Flow](#8-data-flow)
9. [Deployment Architecture](#9-deployment-architecture)
10. [Security Considerations](#10-security-considerations)
11. [Performance Considerations](#11-performance-considerations)
12. [Extension Points](#12-extension-points)
13. [Development Guidelines](#13-development-guidelines)

---

## 1. Overview

### 1.1 Purpose

Bible Inspiration Chat is a conversational AI application that helps users find spiritual encouragement and relevant scripture based on their life situations. The system combines semantic search capabilities with large language model (LLM) generation to provide Bible-grounded responses.

### 1.2 Key Design Principles

| Principle | Description |
|-----------|-------------|
| **Modularity** | Components are loosely coupled with clear interfaces |
| **Provider Agnostic** | LLM and embedding providers can be swapped without code changes |
| **Semantic-First** | Scripture discovery based on meaning, not just keywords |
| **Grounded Responses** | All AI responses are anchored in actual Biblical text |
| **Scalability** | Architecture supports horizontal scaling |
| **Developer Experience** | Clear structure, type safety, and comprehensive documentation |

### 1.3 Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 14, React, TypeScript, Tailwind CSS | Modern web interface |
| **Backend API** | FastAPI, Python 3.12, Pydantic | REST API server |
| **Database** | PostgreSQL 16 + pgvector | Data storage & vector search |
| **LLM (Default)** | Ollama (llama3:8b) | Local language model |
| **Embeddings** | Ollama (nomic-embed-text) | Text-to-vector conversion |
| **Orchestration** | Docker Compose | Container management |

---

## 2. System Architecture

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Next.js Frontend (Port 3000)                    │    │
│  │   ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────────┐    │    │
│  │   │   Chat    │  │  Verse    │  │   API     │  │    State      │    │    │
│  │   │   View    │  │  Cards    │  │  Client   │  │  Management   │    │    │
│  │   └───────────┘  └───────────┘  └───────────┘  └───────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ HTTP/SSE
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   FastAPI Backend (Port 8000)                       │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │                        ROUTES                                │   │    │
│  │  │   /api/v1/chat          POST, POST /stream                   │   │    │
│  │  │   /api/v1/scripture     GET /search, /verse, /chapter        │   │    │
│  │  │   /health, /config      System endpoints                     │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                │                                    │    │
│  │  ┌─────────────────────────────┼────────────────────────────────┐   │    │
│  │  │                      SERVICES                                │   │    │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │   │    │
│  │  │  │ ChatService  │  │SearchService │  │ ScriptureRepo      │  │   │    │
│  │  │  │              │  │              │  │                    │  │   │    │
│  │  │  │ - chat()     │  │ - search()   │  │ - get_verse()      │  │   │    │
│  │  │  │ - stream()   │  │ - get_verse()│  │ - get_chapter()    │  │   │    │
│  │  │  └──────┬───────┘  └──────┬───────┘  │ - semantic_search()│  │   │    │
│  │  │         │                 │          └─────────┬──────────┘  │   │    │
│  │  └─────────┼─────────────────┼────────────────────┼─────────────┘   │    │
│  │            │                 │                    │                 │    │
│  │  ┌─────────┼─────────────────┼────────────────────┼─────────────┐   │    │
│  │  │         ▼    PROVIDER ABSTRACTION LAYER        ▼             │   │    │
│  │  │  ┌──────────────┐              ┌──────────────────────────┐  │   │    │
│  │  │  │ LLMProvider  │              │  EmbeddingProvider       │  │   │    │
│  │  │  │  (Abstract)  │              │     (Abstract)           │  │   │    │
│  │  │  └──────┬───────┘              └────────────┬─────────────┘  │   │    │
│  │  │         │                                   │                │   │    │
│  │  │    ┌────┴────┬────────┐              ┌─────┴─────┐           │   │    │
│  │  │    ▼         ▼        ▼              ▼           ▼           │   │    │
│  │  │ ┌──────┐ ┌───────┐ ┌──────┐   ┌──────────┐ ┌──────────┐      │   │    │
│  │  │ │Ollama│ │Claude │ │OpenAI│   │  Ollama  │ │  OpenAI  │      │   │    │
│  │  │ └──────┘ └───────┘ └──────┘   │ Embedder │ │ Embedder │      │   │    │
│  │  │                               └──────────┘ └──────────┘      │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────┬──────────────────────┬──────────────────┘
                                    │                      │
                                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA & INFERENCE LAYER                            │
│                                                                             │
│  ┌──────────────────────────────┐    ┌──────────────────────────────────┐   │
│  │    PostgreSQL + pgvector     │    │           Ollama                 │   │
│  │        (Port 5432)           │    │        (Port 11434)              │   │
│  │                              │    │                                  │   │
│  │  ┌────────┐ ┌────────┐       │    │  ┌─────────────┐ ┌─────────────┐ │   │
│  │  │ books  │ │chapters│       │    │  │  llama3:8b  │ │nomic-embed- │ │   │
│  │  └────────┘ └────────┘       │    │  │    (LLM)    │ │    text     │ │   │
│  │  ┌────────┐ ┌────────┐       │    │  │             │ │ (Embedding) │ │   │
│  │  │ verses │ │passages│       │    │  └─────────────┘ └─────────────┘ │   │
│  │  │(+embed)│ │(+embed)│       │    │                                  │   │
│  │  └────────┘ └────────┘       │    │                                  │   │
│  └──────────────────────────────┘    └──────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Flow

```
User Message → Frontend → API Router → ChatService
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    ▼                      │                      ▼
            ScriptureSearch          (parallel)            LLM Provider
                    │                      │                      │
                    ▼                      │                      │
            Embedding Provider             │                      │
                    │                      │                      │
                    ▼                      │                      │
            pgvector Search                │                      │
                    │                      │                      │
                    └──────────────────────┼──────────────────────┘
                                           ▼
                                    Context Assembly
                                           │
                                           ▼
                                    LLM Generation
                                           │
                                           ▼
                                    Response → User
```

---

## 3. Component Design

### 3.1 Backend Components

#### 3.1.1 Application Entry Point (`main.py`)

**Responsibilities:**
- FastAPI application initialization
- Middleware configuration (CORS)
- Route registration
- Lifespan management (startup/shutdown)
- Health check endpoints

**Key Features:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup (DB init) and shutdown (cleanup)."""
    await init_db()
    yield
    await close_db()
```

#### 3.1.2 Configuration (`config.py`)

**Pattern:** Singleton Settings with Pydantic

```python
class Settings(BaseSettings):
    # LLM Configuration
    llm_provider: Literal["ollama", "claude", "openai"]
    llm_model: str
    
    # Embedding Configuration
    embedding_provider: Literal["ollama", "openai"]
    embedding_model: str
    
    # Database
    database_url: str
```

**Environment Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | Backend for chat generation |
| `LLM_MODEL` | `llama3:8b` | Model identifier |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Model for vector generation |
| `EMBEDDING_DIMENSIONS` | `768` | Vector size (must match model) |
| `DATABASE_URL` | PostgreSQL connection string | Database connection |
| `ANTHROPIC_API_KEY` | None | For Claude provider |

#### 3.1.3 Chat Service (`chat/service.py`)

**Responsibilities:**
- Orchestrate scripture search and LLM generation
- Manage conversation context
- Build prompts with scripture grounding

**Core Method Flow:**
```
chat(request) →
    1. search_scripture(user_message)
    2. build_context_prompt(search_results)
    3. build_messages(history + context + user_message)
    4. llm.chat(messages)
    5. return ChatResponse
```

#### 3.1.4 Scripture Search Service (`scripture/search.py`)

**Responsibilities:**
- Combine embedding generation with database queries
- Semantic similarity search
- Result formatting

**Search Algorithm:**
1. Convert query text → embedding vector via `EmbeddingProvider`
2. Execute cosine similarity search in pgvector
3. Filter by similarity threshold (default: 0.4)
4. Return ranked results with similarity scores

#### 3.1.5 Scripture Repository (`scripture/repository.py`)

**Pattern:** Repository Pattern with async SQLAlchemy

**Key Operations:**
| Method | Description |
|--------|-------------|
| `get_verse()` | Single verse by reference |
| `get_chapter_verses()` | All verses in a chapter |
| `search_verses_text()` | Full-text search (ILIKE) |
| `search_verses_semantic()` | Vector similarity search |
| `search_passages_semantic()` | Passage similarity search |

### 3.2 Provider System

#### 3.2.1 Provider Interfaces (`providers/base.py`)

**LLMProvider Interface:**
```python
class LLMProvider(ABC):
    @abstractmethod
    async def chat(messages, temperature, max_tokens) -> LLMResponse
    
    @abstractmethod
    async def chat_stream(messages, temperature, max_tokens) -> AsyncIterator[str]
    
    @abstractmethod
    async def health_check() -> bool
```

**EmbeddingProvider Interface:**
```python
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(text: str) -> EmbeddingResponse
    
    @abstractmethod
    async def embed_batch(texts: list[str]) -> list[EmbeddingResponse]
```

#### 3.2.2 Provider Factory (`providers/factory.py`)

**Pattern:** Factory Pattern with Dependency Injection

```python
def create_llm_provider(config: Settings) -> LLMProvider:
    match config.llm_provider:
        case "ollama": return OllamaProvider(...)
        case "claude": return ClaudeProvider(...)
        case "openai": raise NotImplementedError()
```

**FastAPI Dependency Injection:**
```python
# In routes
async def chat(
    llm: LLMProviderDep,           # Injected
    embedding: EmbeddingProviderDep # Injected
):
```

### 3.3 Prompt Engineering (`chat/prompts.py`)

**System Prompt Design:**
```
┌─────────────────────────────────────────────────────────────────┐
│                      SYSTEM PROMPT                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ROLE DEFINITION                                         │    │
│  │ "You are a compassionate spiritual companion..."        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ GUIDELINES                                              │    │
│  │ - Grounding in Scripture (cite verses)                  │    │
│  │ - Tone and Approach (warm, non-judgmental)              │    │
│  │ - Boundaries (not a replacement for counseling)         │    │
│  │ - Response Structure (acknowledge → scripture → reflect)│    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ SCRIPTURE CONTEXT (Dynamic)                             │    │
│  │ ## Relevant Verses Found                                │    │
│  │ **John 3:16**: "For God so loved..."                    │    │
│  │ **Psalm 23:4**: "Even though I walk..."                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Architecture

### 4.1 Database Schema

```sql
┌─────────────────────────────────────────────────────────────────┐
│                         DATABASE SCHEMA                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐  │
│  │   books     │        │  chapters   │        │   verses    │  │
│  ├─────────────┤        ├─────────────┤        ├─────────────┤  │
│  │ id (PK)     │───┐    │ id (PK)     │───┐    │ id (PK)     │  │
│  │ name        │   │    │ book_id(FK) │◄──┤    │ book_id(FK) │◄─┤
│  │ abbreviation│   │    │ number      │   │    │ chapter_id  │◄─┘
│  │ testament   │   │    └─────────────┘   │    │ chapter_num │  │
│  │ position    │   │                      │    │ verse_num   │  │
│  └─────────────┘   │                      │    │ text        │  │
│                    │                      │    │ embedding   │  │
│                    │                      │    │  (vector)   │  │
│                    └──────────────────────┼────└─────────────┘  │
│                                           │                     │
│  ┌─────────────┐        ┌─────────────┐   │                     │
│  │  passages   │        │   topics    │   │                     │
│  ├─────────────┤        ├─────────────┤   │                     │
│  │ id (PK)     │        │ id (PK)     │   │                     │
│  │ title       │◄─────► │ name        │   │                     │
│  │ reference   │ M:N    │ description │   │                     │
│  │ text        │        └─────────────┘   │                     │
│  │ embedding   │                          │                     │
│  └─────────────┘                          │                     │
│                                           │                     │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 SQLAlchemy Models

**Verse Model with Vector:**
```python
class Verse(Base):
    __tablename__ = "verses"
    
    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"))
    chapter_number = Column(Integer)
    verse_number = Column(Integer)
    text = Column(Text)
    embedding = Column(Vector(768))  # pgvector type
```

### 4.3 Vector Search

**Similarity Calculation:**
```python
# Cosine similarity using pgvector
similarity = 1 - Verse.embedding.cosine_distance(query_embedding)
```

**Index Configuration:**
```sql
CREATE INDEX idx_verse_embedding_cosine 
ON verses 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 4.4 Data Statistics

| Entity | Count | Notes |
|--------|-------|-------|
| Books | 66 | Old Testament (39) + New Testament (27) |
| Chapters | ~1,189 | Varies by book |
| Verses | ~31,102 | KJV translation |
| Embedding Dimensions | 768 | nomic-embed-text model |

---

## 5. API Design

### 5.1 REST Endpoints

#### Chat Endpoints (`/api/v1/chat`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Synchronous chat response |
| POST | `/api/v1/chat/stream` | Streaming chat (SSE) |
| GET | `/api/v1/chat/verse/{book}/{chapter}/{verse}` | Verse with context |

**Chat Request:**
```json
{
  "message": "I'm feeling anxious about my future",
  "conversation_history": [
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi, how can I help?"}
  ],
  "include_search": true
}
```

**Chat Response:**
```json
{
  "message": "I understand that feeling anxious...",
  "scripture_context": {
    "query": "I'm feeling anxious about my future",
    "verses": [
      {
        "reference": "Matthew 6:34",
        "text": "Therefore do not worry about tomorrow...",
        "book": "Matthew",
        "chapter": 6,
        "verse": 34,
        "similarity": 0.823
      }
    ],
    "passages": []
  },
  "provider": "ollama",
  "model": "llama3:8b"
}
```

#### Scripture Endpoints (`/api/v1/scripture`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/scripture/books` | List all Bible books |
| GET | `/scripture/verse/{book}/{chapter}/{verse}` | Single verse |
| GET | `/scripture/chapter/{book}/{chapter}` | All verses in chapter |
| GET | `/scripture/range/{book}/{chapter}/{start}/{end}` | Verse range |
| GET | `/scripture/search?q={query}` | Semantic search |

#### System Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check with provider status |
| GET | `/config` | Current configuration (non-sensitive) |
| GET | `/docs` | OpenAPI documentation |

### 5.2 Streaming Protocol

**Server-Sent Events (SSE) Format:**
```
data: {"content": "I understand "}

data: {"content": "that feeling "}

data: {"content": "anxious..."}

data: [DONE]
```

### 5.3 Error Responses

```json
{
  "error": "LLM Provider Error",
  "detail": "Failed to connect to Ollama",
  "hint": "Check if Ollama is running: ollama serve"
}
```

---

## 6. Provider Abstraction Layer

### 6.1 Class Hierarchy

```
┌──────────────────────────────────────────────────────────────────┐
│                     PROVIDER ABSTRACTION                         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐       ┌─────────────────────┐           │
│  │   LLMProvider       │       │  EmbeddingProvider  │           │
│  │     (Abstract)      │       │      (Abstract)     │           │
│  ├─────────────────────┤       ├─────────────────────┤           │
│  │ + provider_name     │       │ + provider_name     │           │
│  │ + chat()            │       │ + embed()           │           │
│  │ + chat_stream()     │       │ + embed_batch()     │           │
│  │ + health_check()    │       │ + health_check()    │           │
│  └──────────┬──────────┘       └──────────┬──────────┘           │
│             │                             │                      │
│     ┌───────┼───────┐             ┌───────┼───────┐              │
│     │       │       │             │       │       │              │
│     ▼       ▼       ▼             ▼       ▼       ▼              │
│  ┌──────┐┌──────┐┌──────┐    ┌──────┐ ┌──────┐ ┌──────┐          │
│  │Ollama││Claude││OpenAI│    │Ollama│ │OpenAI│ │Future│          │
│  └──────┘└──────┘└──────┘    └──────┘ └──────┘ └──────┘          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 6.2 Adding a New Provider

**Step 1:** Create provider class implementing the interface:
```python
# providers/newprovider.py
class NewProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "newprovider"
    
    async def chat(self, messages, temperature, max_tokens) -> LLMResponse:
        # Implementation
        
    async def chat_stream(self, messages, ...) -> AsyncIterator[str]:
        # Implementation
        
    async def health_check(self) -> bool:
        # Implementation
```

**Step 2:** Register in factory:
```python
# providers/factory.py
def create_llm_provider(config: Settings) -> LLMProvider:
    match config.llm_provider:
        case "newprovider":
            return NewProvider(api_key=config.new_api_key)
```

**Step 3:** Add configuration:
```python
# config.py
class Settings(BaseSettings):
    llm_provider: Literal["ollama", "claude", "openai", "newprovider"]
    new_api_key: str | None = None
```

### 6.3 Provider Comparison

| Feature | Ollama | Claude | OpenAI |
|---------|--------|--------|--------|
| Cost | Free (local) | Per-token | Per-token |
| Latency | Low (local) | Network | Network |
| Privacy | Complete | API-dependent | API-dependent |
| Quality | Good | Excellent | Excellent |
| Streaming | ✓ | ✓ | ✓ |
| Setup | Complex | Simple | Simple |

---

## 7. Frontend Architecture

### 7.1 Component Structure

```
frontend/src/
├── app/
│   ├── layout.tsx      # Root layout with metadata
│   ├── page.tsx        # Main chat page
│   └── globals.css     # Global styles
├── components/
│   ├── ChatMessage.tsx # Message bubble component
│   └── VerseCard.tsx   # Scripture display card
└── lib/
    └── api.ts          # API client functions
```

### 7.2 State Management

**Local State (useState):**
- `messages`: Conversation history
- `input`: Current input text
- `isLoading`: Loading state
- `relevantVerses`: Found scripture

### 7.3 API Client (`lib/api.ts`)

**Functions:**
| Function | Description |
|----------|-------------|
| `sendMessage()` | POST to `/api/v1/chat` |
| `streamMessage()` | Stream from `/api/v1/chat/stream` |
| `searchScripture()` | GET `/api/v1/scripture/search` |
| `getVerse()` | GET specific verse |
| `checkHealth()` | GET `/health` |

### 7.4 Styling

**Tailwind Configuration:**
- Custom `primary` color palette (spiritual blue theme)
- Custom `scripture-text` class for verse styling
- Responsive design breakpoints
- Dark mode support (planned)

---

## 8. Data Flow

### 8.1 Chat Request Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                      CHAT REQUEST FLOW                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User Input: "I'm struggling with forgiveness"                   │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ 1. FRONTEND                                             │     │
│  │    - Capture user message                               │     │
│  │    - Add to local message history                       │     │
│  │    - POST to /api/v1/chat                               │     │
│  └─────────────────────────────────────────────────────────┘     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ 2. API ROUTE (chat.py)                                  │     │
│  │    - Validate request                                   │     │
│  │    - Inject dependencies (DB, LLM, Embedding)           │     │
│  │    - Create ChatService                                 │     │
│  └─────────────────────────────────────────────────────────┘     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ 3. CHAT SERVICE (service.py)                            │     │
│  │    a. Scripture Search                                  │     │
│  │       - Query → Embedding Provider → 768-dim vector     │     │
│  │       - Vector → pgvector cosine search                 │     │
│  │       - Return top 10 verses with similarity > 0.35     │     │
│  │                                                         │     │
│  │    b. Context Building                                  │     │
│  │       - Format found verses into prompt context         │     │
│  │       - Prepend to system prompt                        │     │
│  │                                                         │     │
│  │    c. Message Assembly                                  │     │
│  │       [System + Context, History..., User Message]      │     │
│  │                                                         │     │
│  │    d. LLM Generation                                    │     │
│  │       - Send messages to LLM Provider                   │     │
│  │       - Receive response                                │     │
│  └─────────────────────────────────────────────────────────┘     │
│       │                                                          │
│       ▼                                                          │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ 4. RESPONSE                                             │     │
│  │    {                                                    │     │
│  │      "message": "Forgiveness can be challenging...",    │     │
│  │      "scripture_context": {                             │     │
│  │        "verses": [                                      │     │
│  │          {"reference": "Matthew 6:14", ...},            │     │
│  │          {"reference": "Colossians 3:13", ...}          │     │
│  │        ]                                                │     │
│  │      },                                                 │     │
│  │      "provider": "ollama",                              │     │
│  │      "model": "llama3:8b"                               │     │
│  │    }                                                    │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 Embedding Generation Flow

```
User Query: "anxiety about future"
        │
        ▼
┌───────────────────────────┐
│ OllamaEmbeddingProvider   │
│ POST /api/embeddings      │
│ model: nomic-embed-text   │
└───────────────────────────┘
        │
        ▼
768-dimensional vector
[0.234, -0.521, 0.089, ...]
        │
        ▼
┌───────────────────────────┐
│ pgvector Cosine Search    │
│ SELECT *, 1 - cosine_     │
│ distance(embedding, $1)   │
│ ORDER BY distance         │
│ LIMIT 5                   │
└───────────────────────────┘
        │
        ▼
Ranked Verses by Similarity
```

---

## 9. Deployment Architecture

### 9.1 Docker Compose Services

```yaml
services:
  api:        # FastAPI backend
  ollama:     # LLM & Embedding server
  postgres:   # Database with pgvector
  frontend:   # Next.js web app
```

### 9.2 Container Network

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Network (bible-chat)                  │
│                                                                 │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────────┐  │
│  │ frontend │────▶│   api    │────▶│ postgres │     │ ollama │  │
│  │  :3000   │     │  :8000   │────▶│  :5432   │     │ :11434 │  │
│  └──────────┘     └────┬─────┘     └──────────┘     └────────┘  │
│                        │                                  ▲     │
│                        └──────────────────────────────────┘     │
│                                                                 │
│  External Ports:                                                │
│  - 3000 (Frontend)                                              │
│  - 8000 (API)                                                   │
│  - 11434 (Ollama - optional)                                    │
│  - 5432 (PostgreSQL - optional)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Volume Persistence

| Volume | Purpose | Size Estimate |
|--------|---------|---------------|
| `postgres_data` | Bible data + embeddings | ~500MB |
| `ollama_data` | Model weights | ~5-10GB per model |

### 9.4 Resource Requirements

**Minimum (CPU only):**
- CPU: 4 cores
- RAM: 16GB
- Storage: 20GB

**Recommended (GPU):**
- CPU: 4+ cores
- RAM: 16GB
- GPU: NVIDIA 8GB+ VRAM
- Storage: 30GB

---

## 10. Security Considerations

### 10.1 API Security

| Measure | Status | Notes |
|---------|--------|-------|
| CORS | ✓ | Configured for localhost |
| Rate Limiting | Planned | Add with `slowapi` |
| Authentication | Planned | JWT or API keys |
| Input Validation | ✓ | Pydantic models |
| SQL Injection | ✓ | SQLAlchemy parameterized queries |

### 10.2 Data Security

- **No user data storage** (stateless conversations)
- **Local LLM** option for complete privacy
- **API keys** stored as environment variables
- **Database credentials** configurable via env

### 10.3 Production Checklist

- [ ] Enable HTTPS
- [ ] Configure production CORS origins
- [ ] Add rate limiting
- [ ] Implement authentication
- [ ] Set `DEBUG=false`
- [ ] Use secrets management
- [ ] Configure logging
- [ ] Set up monitoring

---

## 11. Performance Considerations

### 11.1 Bottlenecks & Optimizations

| Component | Bottleneck | Optimization |
|-----------|------------|--------------|
| LLM Inference | Slow on CPU | Use GPU acceleration |
| Embedding | Per-request latency | Batch processing, caching |
| Vector Search | Large dataset | IVFFlat index, limit results |
| Database | Connection overhead | Connection pooling |

### 11.2 Caching Strategy (Planned)

```
┌─────────────────────────────────────────────────────────────────┐
│                      CACHING LAYERS                             │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ Embedding Cache  │  hash(query) → embedding vector           │
│  │ (Redis/Memory)   │  TTL: 1 hour                              │
│  └──────────────────┘                                           │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ Search Cache     │  hash(query) → search results             │
│  │ (Redis/Memory)   │  TTL: 15 minutes                          │
│  └──────────────────┘                                           │
│                                                                 │
│  ┌──────────────────┐                                           │
│  │ Verse Cache      │  reference → verse data                   │
│  │ (Application)    │  TTL: Permanent (static data)             │
│  └──────────────────┘                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.3 Scaling Strategy

**Horizontal Scaling:**
```
Load Balancer
      │
      ├──▶ API Instance 1
      ├──▶ API Instance 2
      └──▶ API Instance 3
              │
              ▼
      Shared PostgreSQL
      Shared Ollama (or multiple)
```

---

## 12. Extension Points

### 12.1 Planned Features

| Feature | Priority | Complexity |
|---------|----------|------------|
| User accounts | High | Medium |
| Conversation persistence | High | Low |
| Multiple translations | Medium | Medium |
| Audio Bible | Medium | High |
| Mobile app (React Native) | High | High |
| Reading plans | Low | Medium |
| Community features | Low | High |

### 12.2 Adding a New Bible Translation

1. Obtain translation data (ensure license compatibility)
2. Add `translation` column to `verses` table
3. Modify `load_bible.py` script
4. Add translation selector to API and frontend

### 12.3 Adding New Features

**Example: Daily Verse Feature**

```python
# routes/daily.py
@router.get("/daily")
async def get_daily_verse(db: DbSession):
    """Get a curated verse for today."""
    # Use date-based selection or curated list
    repo = ScriptureRepository(db)
    return await repo.get_daily_verse()
```

---

## 13. Development Guidelines

### 13.1 Code Organization

```
api/
├── main.py           # Entry point, routes registration
├── config.py         # Configuration singleton
├── providers/        # LLM/Embedding providers (one per file)
│   ├── base.py       # Abstract interfaces
│   ├── factory.py    # Provider creation
│   └── *.py          # Concrete implementations
├── scripture/        # Bible data layer
│   ├── models.py     # SQLAlchemy models
│   ├── database.py   # DB connection
│   ├── repository.py # Data access
│   └── search.py     # Search service
├── chat/             # Chat orchestration
│   ├── service.py    # Main service
│   └── prompts.py    # Prompt templates
└── routes/           # API endpoints
    ├── chat.py
    └── scripture.py
```

### 13.2 Coding Standards

- **Python:** PEP 8, type hints, docstrings
- **TypeScript:** ESLint, Prettier
- **Commits:** Conventional Commits
- **Testing:** pytest with async support

### 13.3 Testing Strategy

```
tests/
├── unit/
│   ├── test_providers.py
│   ├── test_repository.py
│   └── test_prompts.py
├── integration/
│   ├── test_chat_flow.py
│   └── test_search.py
└── e2e/
    └── test_api.py
```

### 13.4 Running Locally

**With Docker:**
```bash
docker-compose up -d
docker-compose logs -f
```

**Without Docker:**
```bash
# Terminal 1: Database
docker run -p 5432:5432 pgvector/pgvector:pg16

# Terminal 2: Ollama
ollama serve

# Terminal 3: API
cd api && uvicorn main:app --reload

# Terminal 4: Frontend
cd frontend && npm run dev
```

### 13.5 Environment Setup

```bash
# Clone repository
git clone <repo-url>
cd bible-chat

# Start services
docker-compose up -d

# Load Bible data
cd scripts
python -m venv .venv
source .venv/bin/activate
pip install httpx asyncpg sqlalchemy
python load_bible.py
python create_embeddings.py  # ~30-60 min
```

---

## Appendix A: API Response Schemas

### ChatResponse
```typescript
interface ChatResponse {
  message: string;
  scripture_context?: {
    query: string;
    verses: VerseResult[];
    passages: PassageResult[];
  };
  provider: string;
  model: string;
}
```

### VerseResult
```typescript
interface VerseResult {
  reference: string;  // "John 3:16"
  text: string;
  book: string;
  chapter: number;
  verse: number;
  similarity?: number;  // 0.0 - 1.0
}
```

---

## Appendix B: Database Indexes

```sql
-- Primary lookups
CREATE INDEX idx_book_name ON books(name);
CREATE INDEX idx_verse_reference ON verses(book_id, chapter_number, verse_number);

-- Vector search (IVFFlat for approximate nearest neighbor)
CREATE INDEX idx_verse_embedding_cosine 
ON verses USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Full-text search
CREATE INDEX idx_verse_text_trgm ON verses USING gin (text gin_trgm_ops);
```

---

## Appendix C: Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Cannot connect to Ollama" | Ollama not running | `docker-compose up ollama` or `ollama serve` |
| "Model not found" | Model not pulled | `docker-compose exec ollama ollama pull llama3:8b` |
| Slow responses | CPU inference | Use GPU or smaller model |
| Empty search results | Embeddings not generated | Run `create_embeddings.py` |
| Database connection error | PostgreSQL not ready | Check `docker-compose logs postgres` |

---

*Document maintained by the Bible Inspiration Chat development team.*
