# Embeddings & Question Understanding Improvement Strategy

This document outlines a strategy to improve the relevance of Bible verse retrieval
by enhancing both question understanding and embedding quality.

## Current State

### What We Have

- **Embedding Model**: `mxbai-embed-large` (1024 dimensions, multilingual)
- **Search Method**: Pure semantic search using pgvector cosine similarity
- **Similarity Threshold**: 0.35
- **Max Context Verses**: 5-10 verses per query

### Current Limitations

1. **Literal Matching**: Semantic search may miss thematically relevant verses that
   don't share vocabulary with the query
2. **Context Loss**: User questions often need interpretation (e.g., "I'm stressed"
   → peace, anxiety, trust themes)
3. **No Query Expansion**: We search with the raw user query without reformulation
4. **Single Embedding Space**: All verses use the same embedding without topic/theme
   enrichment

---

## Phase 1: Quick Wins (Low Effort, High Impact)

### 1.1 Query Preprocessing & Expansion

**Goal**: Transform user queries into better search terms before embedding.

```text
User: "I'm feeling anxious about my job interview tomorrow"
↓
Expanded: "anxiety worry fear about future, trust in God, peace in difficult times,
          courage strength confidence"
```

**Implementation**:

- [ ] Create a keyword → theme mapping (e.g., "anxious" → ["peace", "trust", "fear not"])
- [ ] Use LLM to generate expanded search queries before embedding
- [ ] Search with both original and expanded queries, merge results

**Files to modify**:

- `api/chat/service.py` - Add query expansion before search
- `api/scripture/search.py` - Support multiple query embeddings

### 1.2 Hybrid Search (Semantic + Keyword)

**Goal**: Combine semantic similarity with traditional keyword matching.

**Implementation**:

- [ ] Add PostgreSQL full-text search index on verse text
- [ ] Score = (semantic_score *0.7) + (keyword_score* 0.3)
- [ ] Boost exact phrase matches

**Files to modify**:

- `api/scripture/repository.py` - Add full-text search query
- `scripts/migrations/` - Add GIN index for full-text search

### 1.3 Topic-Based Boosting

**Goal**: Boost verses that match detected topics in the user's question.

**Current Topics Table**: We already have a `topics` table with hierarchical categories.

**Implementation**:

- [ ] Detect topics/themes in user query (LLM or keyword-based)
- [ ] Boost verses tagged with matching topics
- [ ] Consider parent topics for broader matching

---

## Phase 2: Enhanced Embeddings (Medium Effort)

### 2.1 Enriched Verse Embeddings

**Goal**: Embed verses with additional context for better semantic matching.

**Current**: We embed just the verse text.

```text
"For God so loved the world..."
```

**Proposed**: Embed verse + context + themes.

```text
"Gospel of John chapter 3 verse 16. Theme: salvation, God's love, eternal life,
 belief, faith. For God so loved the world that he gave his one and only Son..."
```

**Implementation**:

- [ ] Create enriched text generator for verses
- [ ] Include: book context, chapter summary, themes, cross-references
- [ ] Re-generate embeddings with enriched text
- [ ] Store enriched embeddings alongside original

### 2.2 Passage-Level Embeddings

**Goal**: Some concepts span multiple verses; embed logical passages.

**Examples**:

- The Lord's Prayer (Matthew 6:9-13)
- Beatitudes (Matthew 5:3-12)
- Fruit of the Spirit (Galatians 5:22-23)
- Armor of God (Ephesians 6:10-18)

**Implementation**:

- [ ] Curate list of significant passages
- [ ] Generate passage-level embeddings
- [ ] Search both verses and passages, deduplicate results

### 2.3 Multi-Vector Embeddings

**Goal**: Each verse gets multiple embeddings for different aspects.

**Vectors per verse**:

1. **Literal** - The text itself
2. **Thematic** - Main themes/topics
3. **Emotional** - Emotional context (comfort, warning, joy, etc.)
4. **Application** - Life situations it applies to

**Implementation**:

- [ ] Generate 4 embeddings per verse
- [ ] Query matches against all vectors
- [ ] Weight by query type (emotional query → weight emotional vector higher)

---

## Phase 3: Advanced Retrieval (Higher Effort)

### 3.1 Re-Ranking with Cross-Encoder

**Goal**: Use a cross-encoder to re-rank top candidates for better precision.

**Flow**:

```text
Query → Semantic Search (top 50) → Cross-Encoder Re-rank → Top 5
```

**Implementation**:

- [ ] Add cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
- [ ] Re-rank top N candidates from initial retrieval
- [ ] Consider using LLM as reranker for highest quality

### 3.2 Query Intent Classification

**Goal**: Understand what type of answer the user needs.

**Intent Types**:

| Intent | Example | Search Strategy |
|--------|---------|-----------------|
| **Comfort** | "I'm grieving" | Psalms, promises, hope verses |
| **Guidance** | "Should I forgive him?" | Wisdom, commands, examples |
| **Understanding** | "What does grace mean?" | Doctrinal, definitions |
| **Verse Lookup** | "John 3:16" | Direct lookup, no search |
| **Topic Exploration** | "Tell me about faith" | Broad thematic search |

**Implementation**:

- [ ] Train/use classifier for intent detection
- [ ] Route to different search strategies per intent
- [ ] Adjust prompts based on intent

### 3.3 Conversational Context

**Goal**: Use conversation history to improve retrieval.

**Example**:

```text
User: "What about forgiveness?"
(Previous context: discussing marriage problems)
→ Search: forgiveness in marriage, reconciliation, love
```

**Implementation**:

- [ ] Summarize conversation context
- [ ] Include context in query expansion
- [ ] Track themes across conversation

---

## Phase 4: Fine-Tuned Models (Highest Effort)

### 4.1 Fine-Tune Embedding Model

**Goal**: Train embeddings specifically for Bible Q&A retrieval.

**Training Data**:

- Questions paired with relevant verses (from logs, curated)
- Theological Q&A datasets
- Cross-references as positive pairs

**Approaches**:

- [ ] Contrastive learning on question-verse pairs
- [ ] Use existing Bible study resources for training data
- [ ] Consider domain-adaptive pretraining

### 4.2 Bible-Specific LLM Fine-Tuning

**Goal**: Fine-tune the chat LLM for better Bible knowledge.

**Training Data**:

- Commentaries and study notes
- Sermon transcripts
- Biblical counseling resources

---

## Evaluation & Metrics

### Retrieval Quality Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Precision@5** | % of top 5 verses that are relevant | > 80% |
| **Recall@10** | % of relevant verses found in top 10 | > 70% |
| **MRR** | Mean Reciprocal Rank of first relevant result | > 0.7 |
| **User Satisfaction** | Thumbs up rate on responses | > 85% |

### Evaluation Dataset

- [ ] Create gold standard: 100+ questions with annotated relevant verses
- [ ] Include diverse query types (comfort, guidance, understanding)
- [ ] Include different languages (leverage multilingual embeddings)

---

## Recommended Implementation Order

```text
Phase 1 (Weeks 1-2): Quick Wins
├── 1.1 Query Expansion with LLM
├── 1.2 Hybrid Search (semantic + keyword)
└── 1.3 Topic-Based Boosting

Phase 2 (Weeks 3-4): Enhanced Embeddings
├── 2.1 Enriched Verse Embeddings
└── 2.2 Passage-Level Embeddings

Phase 3 (Weeks 5-6): Advanced Retrieval
├── 3.1 Re-Ranking with Cross-Encoder
└── 3.2 Query Intent Classification

Phase 4 (Future): Fine-Tuning
└── Only if Phase 1-3 don't achieve targets
```

---

## Technical Considerations

### Database Changes

```sql
-- Full-text search index
CREATE INDEX idx_verses_fts ON verses USING GIN (to_tsvector('english', text));

-- Enriched embeddings column
ALTER TABLE verses ADD COLUMN enriched_embedding vector(1024);

-- Topic tags
ALTER TABLE verses ADD COLUMN topic_ids INTEGER[];
```

### API Changes

```python
# New search options
class SearchOptions(BaseModel):
    use_query_expansion: bool = True
    use_hybrid_search: bool = True
    rerank_results: bool = False
    max_candidates: int = 50
    final_results: int = 5
```

### Cost Considerations

| Approach | Additional Cost |
|----------|-----------------|
| Query Expansion (LLM) | ~$0.001 per query |
| Cross-Encoder Reranking | Minimal (local model) |
| Fine-tuned Embeddings | One-time compute + storage |
| Multiple Vectors | 4x embedding storage |

---

## Success Criteria

**Phase 1 Complete When**:

- [ ] Query expansion improves relevance in A/B test
- [ ] Hybrid search catches keyword matches semantic misses
- [ ] Thumbs-up rate increases by 10%

**Phase 2 Complete When**:

- [ ] Enriched embeddings show improved Precision@5
- [ ] Passages return appropriate for multi-verse concepts

**Phase 3 Complete When**:

- [ ] Reranking improves top-1 accuracy
- [ ] Intent classification routes queries appropriately

---

## References

- [Sentence Transformers](https://www.sbert.net/) - Embedding models
- [ColBERT](https://github.com/stanford-futuredata/ColBERT) - Late interaction retrieval
- [Hypothetical Document Embeddings (HyDE)](https://arxiv.org/abs/2212.10496) - Query expansion
- [RAG Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/retrieval-augmented-generation)
