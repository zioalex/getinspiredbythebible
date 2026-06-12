# turbovec Evaluation — Can It Improve Our Vector Search?

**Date:** 2026-06-07
**Verdict:** ❌ **Not a fit for Vox Quieta. Do not adopt.**
**Scope:** Reference doc backing the search/embeddings backlog
(`docs/EMBEDDINGS_IMPROVEMENT_STRATEGY.md`, `BITB-018`).

---

## What turbovec is

[turbovec](https://pypi.org/project/turbovec/) is a Rust in-process ANN index with
Python bindings implementing Google Research's **TurboQuant** scalar quantization
(ICLR 2026).

- **Headline value:** memory compression — 2–4 bits/dimension, ~16× reduction
  (e.g. a 31 GB float32 corpus → ~4 GB), no training phase.
- Hand-written NEON (ARM) / AVX-512 (x86) kernels; claims to beat FAISS
  `IndexPQFastScan` by 12–20% on ARM.
- Standalone **in-memory / file-persisted** index. **No PostgreSQL/pgvector
  integration, no SQL, no full-text search, no joins, no transactions.**
- Maturity: v0.7.0, **alpha** (Dev Status 3), MIT, single author, released 2026-05-30.

```python
from turbovec import TurboQuantIndex
index = TurboQuantIndex(dim=1536, bit_width=4)
index.add(vectors)
scores, indices = index.search(query, k=10)
```

## What we have

PostgreSQL + **pgvector** (HNSW, cosine), 1024-dim `mxbai-embed-large` via Ollama,
~31k verses/translation. Crucially, our search is **not pure ANN** — it leans on
Postgres for:

- **Hybrid search** (semantic + `tsvector` full-text) — `repository.py:search_verses_hybrid`
- **Topic boosting** via SQL joins on `verse_topics`
- **Translation filtering** and vectors co-located with verse metadata, transactionally

(See `api/scripture/repository.py`, `api/scripture/search.py`.)

## Why it's a mismatch

1. **Wrong problem.** turbovec's value kicks in at millions of vectors where RAM hurts.
   Our corpus (~370k vectors × 4 KB ≈ 1.5 GB) fits comfortably; memory and ANN latency
   are not the bottleneck. We already moved to HNSW (PR #182) for 40–200× faster search.
2. **Our pain is relevance, not speed.** The open work (query expansion, hybrid, topic
   boosting, reranking) is about *what* gets retrieved. turbovec addresses none of it and,
   being lossy quantization, would slightly *reduce* recall vs. full-precision pgvector.
3. **Architectural regression.** Adopting it means pulling vectors out of Postgres and
   re-implementing hybrid scoring, topic boosts, and filtering in application code —
   losing the SQL features that make our search good.
4. **Maturity risk.** Alpha, v0.x, single maintainer — not suitable for a production
   retrieval core.

## When it *would* matter (not our trajectory)

Only if we simultaneously: hit **5–10M+ vectors**, need pure-ANN at minimal RAM, and are
willing to drop the SQL-side hybrid/boost/filter features. We are nowhere near that.

## Recommendation

Stay on pgvector. Invest in **retrieval relevance** instead — i.e. validate and enable
the already-built Phase-1 improvements (`BITB-018`), then consider reranking / enriched
embeddings (Phases 2–3 of `EMBEDDINGS_IMPROVEMENT_STRATEGY.md`).

## Sources

- <https://pypi.org/project/turbovec/>
- <https://github.com/RyanCodrai/turbovec>
- <https://www.marktechpost.com/2026/05/20/meet-turbovec-a-rust-vector-index-with-python-bindings-and-built-on-googles-turboquant-algorithm/>
