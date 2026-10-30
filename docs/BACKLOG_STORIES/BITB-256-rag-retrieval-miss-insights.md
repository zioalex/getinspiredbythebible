# BITB-256: RAG Retrieval-Miss Insights — Privacy-Safe Logging of Weak or Failed Retrieval

**Status:** 🎯 Todo — spec awaiting owner confirmation (2026-10-28)
**Priority:** P1
**Size:** M
**Created:** 2026-10-28
**Prompted by:** owner request 2026-10-28: "Log RAG retrieval miss to have insights how to improve the
context and RAG."

## User story

**As** the maintainer tuning retrieval,
**I want** a record of every turn where retrieval came back empty, weak, or didn't contain what the
model ended up citing, described by topic, language and translation,
**so that** I can see which themes, languages and versions need better embeddings, topic curation or
query expansion, **without storing what users typed**.

## Problem (verified in code, 2026-10-28)

The only retrieval-quality signals today are aggregate counters:

- `chat_verseless_responses_counter` (BITB-055)
- `chat_scripture_unavailable_counter` (BITB-058)

They report *that* retrieval failed, but not *for what kind of question*.

The offline harness BITB-139 measures a golden set, not real traffic. The privacy policy
(`frontend/public/legal/privacy-policy.md`) promises that chat messages are not retained. Its only
carve-out is safety-blocked samples.

## Decisions (owner, 2026-10-28)

1. **What counts as a miss:**
   - `empty`: retrieval returned zero verses or passages, or raised (including the BITB-058
     fail-closed case).
   - `low_score`: the top result's similarity is below a configurable threshold.
   - `cited_outside_pool`: the reply cites refs that weren't in the retrieved context.
   - Thumbs-down feedback is **not** a miss signal in this story.
2. **Where:** a new DB table **plus** a structured log event and OTel counter.
3. **Privacy:** **derived signals only, never raw text.** Store only what the pipeline itself derives
   from the message: intent, extracted topics/themes, the query-expansion keywords, language,
   translation, scores and refs. Neither the prompt nor the expanded *sentence* is stored.

## Functional requirements

1. **Detection** in `ChatService`:
   - It runs in both `chat()` and `chat_stream()`, once the reply's cited refs are known, with
     `include_search=True`.
   - Skipped turns: off-topic, clarification and crisis/blocked turns, plus GENERAL intent for the
     `low_score` reason.
   - One turn may carry several reasons.
2. **Table `retrieval_miss_samples`:**
   - Modelled on `BlockedMessageSample` (`api/feedback/models.py`), with an Alembic migration.
   - Columns:
     - `created_at`, `expires_at` (TTL)
     - `reasons` (array)
     - `intent`, `language`, `translation`
     - `topics` (JSONB: extracted themes)
     - `expansion_terms` (JSONB: keyword list only, capped count and length)
     - `top_refs` (JSONB: top-k ref + score + source semantic/keyword/direct)
     - `top_score`, `threshold`
     - `cited_outside_pool` (JSONB refs)
     - `retrieval_mode` (hybrid/boosted/...)
     - `embedding_provider`/`model`
     - `session_id_hash`
     - `signature_sha256`, unique: a hash of reasons+intent+language+translation+sorted topics
     - `hit_count`
   - Rows are deduplicated by signature: a repeat increments `hit_count`.
   - **No column holds user text.**
3. **Sanitizing expansion terms.** Expansion terms come from the LLM and can echo user words, such
   as a name. Keep only terms that match a topic vocabulary or a book name, or that are at most 3
   words. Drop digits, emails and URLs. Cap at 10 terms of at most 40 characters each. Document this
   as the privacy boundary.
4. **Writes:**
   - Best-effort and fire-and-forget: they never block or fail the chat reply.
   - Gated by the settings `retrieval_miss_capture_enabled`, `retrieval_miss_low_score_threshold` and
   `retrieval_miss_retention_days` (default 90), added to `api/config.py` and
   `scripts/env-manifest.yaml`.
   - Expired rows are purged with the same mechanism as blocked samples.
5. **Telemetry:**
   - A structured log event `rag_retrieval_miss`, carrying the same fields minus `session_id_hash`.
   - An OTel counter `chat_retrieval_miss{reason, language, translation, intent}`.
   - No raw text in either.
6. **Reporting:**
   - A `scripts/` export (or a `tools/` report, per *Reproducible Repo Analyses*) aggregating misses
     by topic × language × reason.
   - Documented in a `docs/HOW-TO-EXPORT-RETRIEVAL-MISSES.md` modelled on
     `HOW-TO-EXPORT-BLOCKED-SAMPLES.md`.
7. **Privacy policy:**
   - Add one clarifying line in all 11 `privacy-policy*.md` files: anonymous retrieval-quality
     statistics (topics, language, scores; never message text) are kept for up to the retention
     period.
   - Bump the policy date.

## Non-functional requirements

- **Languages:** detection and topic extraction work for all 11 languages. Tests are parametrized
  over en, it, de, es, fr, pt, ar, ru, zh, hi, ko, and cover at least two translations (e.g. KJV vs
  WEB) to show that `translation` is recorded faithfully.
- **Performance:** zero added latency on the reply path, since the write is async after the
  response. Each write is a single upsert.
- **Privacy:** a test sends a message with a unique sentinel string and asserts that the sentinel
  appears nowhere in the stored row or the log record.
- **Backend only:** there is no frontend or Android change apart from the policy text.

## Acceptance criteria

- [ ] Each reason (`empty`, `low_score`, `cited_outside_pool`) is detected and recorded on both the
      `chat()` and `chat_stream()` paths, in integration tests through `chat()`/`chat_stream()` with a
      mocked `search_service`.
- [ ] Off-topic, clarification, crisis and blocked turns never record a miss.
- [ ] The sentinel privacy test passes: no user text in the DB row or the log.
- [ ] Expansion-term sanitizer has unit tests for names, digits, emails, URLs and length/count caps.
- [ ] Repeats of the same signature increment `hit_count`, rows expire per TTL, and the capture flag
      off means no writes.
- [ ] A DB error during capture does not affect the chat reply.
- [ ] The migration applies and rolls back in `test_run_migrations.py`.
- [ ] Env vars are in `scripts/env-manifest.yaml`. The export script is documented.
- [ ] The privacy-policy line is added in all 11 languages.
- [ ] Cross-language parametrized test covers all 11 languages, and a version-faithfulness test
      covers KJV vs WEB.

## Out of scope

- Thumbs-down feedback linkage. That could be a follow-up story, since feedback already stores text
  with consent.
- Automatic re-tuning of retrieval from the data.
- An admin UI or dashboard (App Insights workbook panels could be a follow-up).
- Storing raw or capped prompt text, or an opt-in to share it.

## Resolved questions (owner, 2026-10-29)

1. **Default `low_score` threshold.** Derived from the BITB-139 golden-set score distribution (e.g.
   the p10 of correct hits), and configurable per embedding model.
2. **Retention.** 90 days.
