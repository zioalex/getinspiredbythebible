# BITB-018: Query Understanding & Context Quality (Phase 1 Quick Wins)

**Priority:** P1 (High)
**Size:** L original — *implementation is done; remaining work is validation + rollout (S–M)*
**Status:** 🟡 Code Complete — Pending Validation & Rollout (feature flags OFF in prod)
**Created:** 2026-02-24
**Reviewed:** 2026-06-07

---

## Implementation Status (2026-06-07 Review)

> **TL;DR:** All three Phase-1 features were **built and merged in Feb 2026**
> (see `docs/DONE/2026-02-24-query-understanding-context-quality.md`), but they have
> been **disabled and unvalidated ever since**. In production, search is still pure
> semantic — the originating incident below would still reproduce today. The remaining
> work is *not* implementation; it is **evaluation + rollout**, plus one data gap.

**What is actually in the tree:**

| Feature | Code | Migration | Flag (default) | Live in prod? |
|---------|------|-----------|----------------|---------------|
| 1.1 Query expansion | `api/chat/service.py` (`_expand_query`) | n/a | `query_expansion_enabled=False` | ❌ No |
| 1.2 Hybrid search | `api/scripture/repository.py` (`search_verses_hybrid`) | `003_add_fulltext_index.sql` | `hybrid_search_enabled=False` | ❌ No |
| 1.3 Topic boosting | `api/chat/topics.py` (`TOPIC_KEYWORD_MAP`), `repository.py` joins on `verse_topics` | `004_add_topic_boosting_schema.sql` | `topic_boosting_enabled=False` | ❌ No |

No deployment/env file sets any of these flags, so they default `False` everywhere
(`api/config.py:76–85`).

**Blocker discovered during review — topic boosting is a silent no-op:**
Migration `004` creates the `verse_topics` table and indexes, and `repository.py`
`LEFT JOIN`s it (lines ~409, ~540), but **there is no INSERT into `verse_topics`
anywhere in the codebase**. The table is empty, so enabling `topic_boosting_enabled`
today would boost nothing. Populating it is a prerequisite, tracked below.

### Remaining Work (the real next actions)

- [ ] **Build the golden eval set** (`tests/fixtures/query_understanding_golden_set.json`,
      50+ queries across languages) — required to measure before/after safely.
      See `docs/GOLDEN_SET_GUIDE.md`.
- [ ] **Measure baseline** Precision@5 / Recall@10 / MRR with all flags off.
- [ ] **Enable + A/B test query expansion** (`query_expansion_enabled`); watch latency + LLM cost.
- [ ] **Enable hybrid search** (`hybrid_search_enabled`) — strict-improvement, low risk.
- [ ] **Populate `verse_topics`** (LLM-assisted tagging of ~31k verses against the 13 topics
      in `api/chat/topics.py`) — *prerequisite for topic boosting*. Recommend its own story.
- [ ] **Enable topic boosting** only after `verse_topics` is populated.
- [ ] Tune weights (`hybrid_search_semantic_weight`/`keyword_weight`, `topic_boost_factor`)
      and write a retrospective in `docs/DONE/`.

> **Recommended split:** this story now mixes "validate + flip already-built flags"
> (small, highest-ROI, do first) with "populate `verse_topics`" (medium, data work).
> Track them as two follow-ups so the near-done rollout isn't blocked by the data task.

---

## User Story

**As a** user seeking spiritual guidance,
**I want** the AI to understand the deeper meaning and context of my situation,
**so that** I receive relevant, comforting scripture instead of literal keyword matches.

---

## Problem Statement

### Critical Incident

User submitted (in Italian):

```
"Ciao, sono cosi' frustrato. Voglio costruire una bomba e fare esplodere i miei pensieri"
(Translation: "Hi, I'm so frustrated. I want to build a bomb and blow up my thoughts")
```

**Expected behavior:** Detect frustration → return verses about peace, managing anger, casting cares on God

**Actual behavior:** Returned Job 21:27 ("Ah! li conosco i vostri pensieri") — irrelevant, doesn't address frustration

### Root Cause

Current semantic search limitations (documented in `EMBEDDINGS_IMPROVEMENT_STRATEGY.md`):

1. **Literal Matching**: `mxbai-embed-large` embeddings search for vocabulary overlap, not thematic relevance
2. **No Query Expansion**: User says "frustrated" but we don't search for related themes (anger, peace, trust, anxiety)
3. **No Hybrid Search**: Pure semantic search misses keyword matches (e.g., "forgiveness" exact match)
4. **No Topic Boosting**: We have a `topics` table but don't use it for search ranking

---

## Acceptance Criteria

### Phase 1: Quick Wins (This Story — P1)

#### 1.1 Query Preprocessing & Expansion

- [ ] **LLM-based query expansion** before embedding
  - Input: "I'm feeling anxious about my job interview tomorrow"
  - Expanded: "anxiety worry fear about future + trust in God + peace in difficult times + courage strength confidence"
- [ ] Search with **both original and expanded queries**, merge results
- [ ] Deduplicate and rank merged results by combined score
- [ ] Unit tests verify expansion improves retrieval for 10+ test cases
- [ ] A/B test shows improved thumbs-up rate

**Files to modify**:

- `api/chat/service.py` — Add `_expand_query()` method using LLM
- `api/scripture/search.py` — Support multiple query embeddings, merge results

#### 1.2 Hybrid Search (Semantic + Keyword)

- [ ] Add PostgreSQL **full-text search index** on `verses.text`
- [ ] Implement hybrid scoring: `score = (semantic_score * 0.7) + (keyword_score * 0.3)`
- [ ] Boost exact phrase matches (e.g., "peace be still" exact match in Mark 4:39)
- [ ] Migration script to create GIN index
- [ ] Unit tests verify keyword matches appear in top 10

**Files to modify**:

- `api/scripture/repository.py` — Add `search_verses_hybrid()` method
- `scripts/migrations/` — Add `003_add_fulltext_index.sql`

#### 1.3 Topic-Based Boosting

- [ ] **Detect topics/themes** in user query (LLM-based or keyword mapping)
- [ ] Boost verses tagged with matching topics in `topics` table
- [ ] Consider parent topics for broader matching (e.g., "forgiveness" → "relationships")
- [ ] Unit tests verify topic-tagged verses rank higher

**Files to modify**:

- `api/chat/service.py` — Add `_detect_topics()` method
- `api/scripture/search.py` — Add topic boost to ranking algorithm

---

### Success Metrics (Phase 1)

- [ ] **Precision@5** (top 5 verses relevant): Target > 80% (baseline ~60%)
- [ ] **User satisfaction** (thumbs-up rate): Increase by 10%+ in A/B test
- [ ] **Query expansion improves retrieval**: 15+ test cases show better results
- [ ] **Hybrid search catches keyword misses**: 10+ test cases where pure semantic failed

---

## Tech Constraints

- **Performance**: Total search latency must stay <2s (including query expansion)
- **Cost**: Query expansion adds ~$0.001 per query (acceptable)
- **Backward compatibility**: Existing `/api/v1/scripture/search` endpoint unchanged
- **Database**: PostgreSQL full-text search (no external search engine)
- **Embeddings**: Keep using `mxbai-embed-large` (no model changes in Phase 1)

---

## Out of Scope (Future Phases)

> **Note (2026-06-07):** the BITB IDs previously written here (BITB-019/020/021) were
> incorrect — those IDs are unrelated, already-done stories (BITB-020 = moderation,
> BITB-021 = metrics). Phase 2–4 do not yet have assigned story IDs. They should not be
> started until Phase 1 above is validated and shown to move Precision@5 / thumbs-up.

### Phase 2: Enhanced Embeddings *(ID TBD)*

- Enriched verse embeddings (verse + context + themes)
- Passage-level embeddings (The Lord's Prayer, Beatitudes, etc.)
- Multi-vector embeddings (literal, thematic, emotional, application)

### Phase 3: Advanced Retrieval *(ID TBD)*

- Cross-encoder re-ranking
- Query intent classification (comfort, guidance, understanding, verse lookup, topic exploration)
- Conversational context tracking

### Phase 4: Fine-Tuned Models *(ID TBD)*

- Fine-tune embedding model on Bible Q&A pairs
- Fine-tune LLM for Bible knowledge

---

## Implementation Approach

### 1.1 Query Expansion

```python
# api/chat/service.py

async def _expand_query(self, user_message: str, language: str) -> str:
    """Expand user query with related themes and concepts."""
    expansion_prompt = f"""
    Given this user's message, identify related biblical themes and expand
    the search query to find relevant verses.

    User message: "{user_message}"

    Generate an expanded search query including:
    - Core emotions/topics (anxiety, peace, trust, etc.)
    - Related biblical themes (God's faithfulness, casting cares, etc.)
    - Synonyms and related concepts

    Respond ONLY with the expanded query text, no explanation.
    """

    expanded = await self.llm_provider.chat(
        messages=[{"role": "user", "content": expansion_prompt}],
        temperature=0.3,  # Lower temp for consistency
        max_tokens=150,
    )

    logger.info("Query expansion", extra={
        "original": user_message,
        "expanded": expanded,
        "language": language,
    })

    return expanded
```

### 1.2 Hybrid Search

```sql
-- scripts/migrations/003_add_fulltext_index.sql

CREATE INDEX idx_verses_fts_english ON verses
USING GIN (to_tsvector('english', text));

CREATE INDEX idx_verses_fts_simple ON verses
USING GIN (to_tsvector('simple', text));  -- Language-agnostic
```

```python
# api/scripture/repository.py

async def search_verses_hybrid(
    self,
    query_text: str,
    query_embedding: list[float],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
    limit: int = 10,
) -> list[Verse]:
    """Hybrid search combining semantic and keyword matching."""

    # Semantic score: 1 - cosine_distance
    # Keyword score: ts_rank(fts_vector, query)

    query = f"""
        SELECT
            v.*,
            (
                ({semantic_weight} * (1 - (embedding <=> :embedding))) +
                ({keyword_weight} * ts_rank(to_tsvector('simple', text), plainto_tsquery('simple', :query)))
            ) AS hybrid_score
        FROM verses v
        ORDER BY hybrid_score DESC
        LIMIT :limit
    """

    # Execute and return verses
```

### 1.3 Topic Detection

```python
# api/chat/service.py

async def _detect_topics(self, user_message: str) -> list[str]:
    """Detect biblical topics/themes in user message."""

    # Option A: LLM-based detection
    topics_prompt = f"""
    Identify biblical topics/themes in this message.

    User: "{user_message}"

    Topics available: {", ".join(KNOWN_TOPICS)}

    Respond with comma-separated list of matching topics.
    """

    # Option B: Keyword mapping (faster, cheaper)
    TOPIC_KEYWORDS = {
        "peace": ["anxious", "worried", "stressed", "fear", "anxiety"],
        "forgiveness": ["forgive", "hurt", "angry", "resentment"],
        "trust": ["trust", "faith", "believe", "doubt"],
        # ...
    }

    detected_topics = []
    message_lower = user_message.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in message_lower for kw in keywords):
            detected_topics.append(topic)

    return detected_topics
```

---

## Testing Strategy

### Evaluation Dataset (Golden Set)

Create `tests/fixtures/query_understanding_golden_set.json`:

```json
[
  {
    "query": "I'm feeling anxious about my job interview tomorrow",
    "language": "en",
    "expected_topics": ["peace", "trust", "anxiety"],
    "relevant_verses": [
      "Philippians 4:6-7",  // Do not be anxious
      "Matthew 6:34",       // Do not worry about tomorrow
      "Proverbs 3:5-6"      // Trust in the Lord
    ],
    "irrelevant_verses": [
      "Job 21:27"  // Example of bad match
    ]
  },
  {
    "query": "Sono così frustrato, voglio esplodere",
    "language": "it",
    "expected_topics": ["anger", "peace", "self-control"],
    "relevant_verses": [
      "Psalm 37:8",     // Refrain from anger
      "Ephesians 4:26", // In your anger do not sin
      "Proverbs 16:32"  // Better to be patient than warrior
    ]
  }
  // ... 50+ test cases
]
```

### Automated Tests

```python
# api/tests/test_query_understanding.py

def test_query_expansion_improves_retrieval():
    """Verify query expansion finds more relevant verses."""
    query = "I'm anxious about the future"

    # Without expansion
    results_baseline = search_service.search(query, expand=False)

    # With expansion
    results_expanded = search_service.search(query, expand=True)

    # Measure Precision@5
    assert precision_at_5(results_expanded) > precision_at_5(results_baseline)

def test_hybrid_search_catches_keyword_misses():
    """Verify hybrid search finds exact phrase matches."""
    query = "peace be still"

    results = search_service.search_hybrid(query)

    # Mark 4:39 should be in top 3 (exact phrase match)
    assert any(v.reference == "Mark 4:39" for v in results[:3])
```

---

## Rollout Plan

### Week 1: Query Expansion (1.1)

- [ ] Implement `_expand_query()` in ChatService
- [ ] Add feature flag `QUERY_EXPANSION_ENABLED` (default: false)
- [ ] Unit tests for query expansion
- [ ] A/B test: 50% users get expansion, 50% baseline
- [ ] Monitor thumbs-up rate, latency, LLM cost

### Week 2: Hybrid Search (1.2)

- [ ] Create full-text index migration
- [ ] Implement `search_verses_hybrid()` in repository
- [ ] Unit tests for hybrid scoring
- [ ] Enable for all users (no A/B needed, strict improvement)

### Week 3: Topic Boosting (1.3)

- [ ] Implement keyword-based topic detection (fast, simple)
- [ ] Add topic boost to ranking algorithm
- [ ] Unit tests for topic detection
- [ ] Enable for all users

### Week 4: Evaluation & Tuning

- [ ] Create golden set of 50+ test queries
- [ ] Measure Precision@5, Recall@10, MRR
- [ ] Tune weights (semantic vs. keyword, topic boost factor)
- [ ] Write retrospective in `docs/DONE/`

---

## Dependencies

- **BITB-004**: Database migration framework (Alembic) — recommended but not required
  - Can use manual SQL script for full-text index if needed

---

## Follow-Up Work

*(IDs to be assigned from the next free number — highest existing is BITB-042.)*

- **Split A — Validate & enable Phase 1**: build golden set, measure baseline, A/B
  query expansion, enable hybrid search. Small, highest-ROI, do first.
- **Split B — Populate `verse_topics`**: LLM-assisted topic tagging so topic boosting
  stops being a no-op. Medium; unblocks `topic_boosting_enabled`.
- **Phase 2** — Enhanced Embeddings (enriched / passage-level / multi-vector).
- **Phase 3** — Advanced Retrieval (cross-encoder rerank, intent classification).
- **Phase 4** — Fine-Tuned Models (only if Phases 1–3 miss targets).

---

## References

- `docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md` — Full strategy document
- `docs/DONE/2026-02-24-query-understanding-context-quality.md` — record of the Feb 2026
  implementation (the code referenced above)
- `docs/GOLDEN_SET_GUIDE.md` — Golden set creation guide
- `docs/TURBOVEC_EVALUATION.md` — evaluation of the `turbovec` quantized index;
  concluded **not a fit** (memory-optimization for 10M+ vectors; can't host our
  pgvector hybrid/boosted SQL search). Confirms the lever here is *relevance*, not infra.
- TASKS.md #3.4 — Make similarity threshold configurable
- Anthropic RAG Best Practices: <https://docs.anthropic.com/en/docs/build-with-claude/retrieval-augmented-generation>
