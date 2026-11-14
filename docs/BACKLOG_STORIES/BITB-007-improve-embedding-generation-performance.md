---
id: BITB-007
status: todo
priority: P2
size: M
rank: 980
---

# BITB-007: Improve Embedding Generation Performance

**As a** developer running `create_embeddings.py`,
**I want** embedding generation to be parallelized,
**so that** the 30-60 minute task completes in under 10 minutes.

**Acceptance Criteria:**

- [ ] `embed_batch()` uses `asyncio.gather()` with semaphore
- [ ] Configurable concurrency limit (default: 10)
- [ ] Partial results saved if batch fails mid-way
- [ ] Progress bar shows accurate completion estimate
- [ ] Documentation updated with new timing estimates

**Tech Constraints:**

- Must not overwhelm Ollama server (hence semaphore)
- Must work with existing Ollama provider
- Must handle failures gracefully (no silent data loss)

**Out of Scope:**

- Switching embedding providers
- Caching embeddings (separate story)

**Related:** TASKS.md #1.2
