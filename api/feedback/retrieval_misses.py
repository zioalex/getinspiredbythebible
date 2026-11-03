"""
Privacy-safe capture of weak or failed scripture retrieval (BITB-256).

Records *which kind of question* retrieval struggled with, so embeddings, topic
curation and query expansion can be improved, without ever storing what the user
typed. Three miss reasons are detected per chat turn (several may apply):

- ``empty``: retrieval returned no verses/passages, or raised (incl. BITB-058).
- ``low_score``: the best similarity is below a per-embedding-model threshold.
- ``cited_outside_pool``: the reply cites verses that were not in the retrieved
  context (nor discussed earlier in the conversation).

Privacy boundary (what is and is NOT stored)
--------------------------------------------
Stored: reasons, intent label, language, translation, canonical topic ids
(from the keyword map, never free text), sanitized query-expansion terms,
top-5 verse references with scores, the threshold, refs the reply cited outside
the pool, retrieval mode, embedding provider/model, a one-way hash of the session
id, a signature hash, and a hit counter. **No column holds user or model text.**
The prompt and the expanded query sentence are never stored or logged.

The only free-form-derived field is ``expansion_terms``. Those come from an LLM
and can echo user words (a name, a place, an id), so ``sanitize_expansion_terms``
is the privacy boundary. It applies, in order:

1. Split the expansion on list separators (``, ; newline bullets`` and CJK
   ``、，；`` and `` - ``), strip quotes/whitespace, case-fold.
2. Drop any term containing a digit, ``@``, ``://`` or ``www.``.
3. Keep a term outright if it is in the fixed topic vocabulary
   (``TOPIC_KEYWORD_MAP`` values) or is a Bible book name in any language.
   A multi-word chunk that is not itself allow-listed is also scanned
   word-by-word, and only its allow-listed words are kept.
4. Otherwise drop a run of >= 5 consonants/symbols (ids, hashes), drop terms of
   more than 3 words, and drop any term that appears verbatim in the user's
   message (the "echo" rule: it may be the user's own wording or a name).
5. De-duplicate, cut each term to 40 characters, keep at most 10.

Retention: rows get a fixed ``expires_at`` (``retrieval_miss_retention_days``)
set on first insert and *not* refreshed by repeats, so "up to 90 days" is
literally true. Expired rows are purged at startup and by a daily loop.

All writes are best-effort and fire-and-forget; they never raise to, or delay,
the chat reply.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from config import settings
from utils.book_names import normalize_book_name
from utils.db_retry import run_with_disconnect_retry
from utils.logging_config import get_logger
from utils.metrics import chat_retrieval_miss_counter
from utils.verse_parser import ALL_BOOK_NAMES, extract_all_references

from .blocked_samples import _hash_session_id
from .models import RetrievalMissSample

logger = get_logger(__name__)

REASON_EMPTY = "empty"
REASON_LOW_SCORE = "low_score"
REASON_CITED_OUTSIDE_POOL = "cited_outside_pool"

MAX_TERMS = 10
MAX_TERM_CHARS = 40
MAX_TERM_WORDS = 3
MAX_TOP_REFS = 5
MAX_OUTSIDE_REFS = 10
MAX_POOL_KEYS = 200
DEFAULT_LOW_SCORE_THRESHOLD = 0.5

_SPLIT_RE = re.compile(r"[,;\n•·、，；]| - ")
_QUOTES = " \t\r\"'`“”‘’«»「」『』《》()[]（）"
# 5+ consecutive ASCII consonants/symbols inside one word (ids, hashes, keyboard
# mash). Apostrophes and hyphens do not count, so "wouldn't" is not a run.
_CONSONANT_RUN_RE = re.compile(r"[^aeiouy\s\u0080-\U0010ffff'’\-]{5,}")

_ALLOW_LIST: frozenset[str] | None = None


def _allow_list() -> frozenset[str]:
    """Topic vocabulary + book names (case-folded); built once."""
    global _ALLOW_LIST
    if _ALLOW_LIST is None:
        # Lazy: chat/__init__ imports chat.service, which imports this module.
        from chat.topics import TOPIC_KEYWORD_MAP

        words = {kw.casefold() for kws in TOPIC_KEYWORD_MAP.values() for kw in kws}
        words.update(name.casefold() for name in ALL_BOOK_NAMES)
        _ALLOW_LIST = frozenset(words)
    return _ALLOW_LIST


@dataclass
class RetrievalTrace:
    """What the retrieval stage did, collected for the miss hook (no user text)."""

    retrieval_mode: str = "none"
    expansion_text: str | None = None  # transient: sanitized, then discarded
    boost_topics: list[str] = field(default_factory=list)
    search_failed: bool = False
    passage_context_keys: set[tuple[str, int, int]] = field(default_factory=set)


# ---------------------------------------------------------------------------
# Sanitizing / topics
# ---------------------------------------------------------------------------


def _is_unsafe(term: str) -> bool:
    """Hard drops: digits, emails, URLs."""
    return any(ch.isdigit() for ch in term) or "@" in term or "://" in term or "www." in term


def _candidate_terms(term: str, allow: frozenset[str], message_folded: str) -> list[str]:
    """Terms to keep from one cleaned chunk (empty list = drop it)."""
    if term in allow:
        return [term]
    words = term.split()
    if len(words) > MAX_TERM_WORDS:
        # Free-form sentence: salvage only the individually allow-listed words.
        salvaged = (word.strip(_QUOTES + ".!?:") for word in words)
        return [word for word in salvaged if word in allow]
    if _CONSONANT_RUN_RE.search(term) or term in message_folded:
        return []
    return [term]


def sanitize_expansion_terms(expanded: str | None, user_message: str) -> list[str]:
    """Reduce an LLM query expansion to a short list of safe keywords. See module docstring."""
    if not expanded:
        return []
    allow = _allow_list()
    message_folded = (user_message or "").casefold()
    out: list[str] = []
    for chunk in _SPLIT_RE.split(expanded):
        term = chunk.strip(_QUOTES).strip(" .!?:").casefold()
        if not term or _is_unsafe(term):
            continue
        for candidate in _candidate_terms(term, allow, message_folded):
            candidate = candidate[:MAX_TERM_CHARS].strip()
            if candidate and candidate not in out and len(out) < MAX_TERMS:
                out.append(candidate)
    return out


def topics_for_record(message: str) -> list[str]:
    """Canonical English topic ids detected in ``message`` (never free text).

    Backed by ``chat.topics.detect_topics``, which only knows en/it/de/es/fr/pt/ar;
    ru/zh/hi/ko yield [] (tracked as BITB-259).
    """
    try:
        from chat.topics import detect_topics

        return sorted(detect_topics(message))
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Pool / classification
# ---------------------------------------------------------------------------


def _range_keys(book: str, chapter: int, start: int, end: int | None) -> set[tuple[str, int, int]]:
    last = end if end is not None and end >= start else start
    last = min(last, start + MAX_POOL_KEYS - 1)
    return {(book, chapter, v) for v in range(start, last + 1)}


def keys_from_reference_strings(references: list[str]) -> set[tuple[str, int, int]]:
    """Verse keys covered by reference strings (ranges expanded, capped)."""
    keys: set[tuple[str, int, int]] = set()
    for text in references:
        for ref in extract_all_references(text or ""):
            keys |= _range_keys(ref.book, ref.chapter, ref.verse_start, ref.verse_end)
            if len(keys) >= MAX_POOL_KEYS:
                return keys
    return keys


def pool_keys(
    ctx: Any, extra: set[tuple[str, int, int]] | None = None
) -> set[tuple[str, int, int]]:
    """Every (book, chapter, verse) the model was shown: verses, passages, surrounding context."""
    keys: set[tuple[str, int, int]] = set(extra or ())
    if ctx is None:
        return keys
    for v in getattr(ctx, "verses", None) or []:
        try:
            keys.add((normalize_book_name(v.book), int(v.chapter), int(v.verse)))
        except Exception:  # noqa: BLE001 - malformed row: skip, never raise
            continue
    passage_refs = [p.reference for p in (getattr(ctx, "passages", None) or [])]
    keys |= keys_from_reference_strings(passage_refs)
    return keys


def refs_outside_pool(
    cited: list[Any], pool: set[tuple[str, int, int]], history_refs: set[str]
) -> list[str]:
    """Cited refs with no verse in the pool and not cited earlier in the conversation."""
    outside: list[str] = []
    for ref in cited:
        text = str(ref)
        if text in history_refs or text in outside:
            continue
        if _range_keys(ref.book, ref.chapter, ref.verse_start, ref.verse_end) & pool:
            continue
        outside.append(text)
        if len(outside) >= MAX_OUTSIDE_REFS:
            break
    return outside


def _scores(ctx: Any) -> list[float]:
    items = [
        *(getattr(ctx, "verses", None) or []),
        *(getattr(ctx, "passages", None) or []),
    ]
    return [i.similarity for i in items if getattr(i, "similarity", None) is not None]


def best_score(ctx: Any) -> float | None:
    """Highest similarity among the retrieved verses/passages (None when there is none)."""
    scores = _scores(ctx)
    return round(max(scores), 4) if scores else None


def classify_miss(
    *,
    ctx: Any,
    trace: RetrievalTrace,
    intent: str,
    is_verse_lookup: bool,
    threshold: float,
    outside: list[str],
) -> list[str]:
    """Reasons this turn counts as a retrieval miss (empty list = not a miss)."""
    reasons: list[str] = []
    is_empty = (
        trace.search_failed
        or ctx is None
        or not (getattr(ctx, "verses", None) or getattr(ctx, "passages", None))
    )
    if is_empty:
        reasons.append(REASON_EMPTY)
    elif intent != "GENERAL" and not is_verse_lookup:
        scores = _scores(ctx)
        if scores and max(scores) < threshold:
            reasons.append(REASON_LOW_SCORE)
    if outside:
        reasons.append(REASON_CITED_OUTSIDE_POOL)
    return reasons


def resolve_low_score_threshold(mode: str | None = None) -> float:
    """Threshold: explicit setting, else per '{model}:{mode}', else '{model}', else 0.5."""
    if settings.retrieval_miss_low_score_threshold is not None:
        return float(settings.retrieval_miss_low_score_threshold)
    model = (
        settings.azure_embedding_deployment
        if settings.embedding_provider == "azure_openai"
        else settings.embedding_model
    )
    table = settings.retrieval_miss_low_score_thresholds or {}
    family = "hybrid" if (mode or "").startswith("hybrid") else "semantic"
    for key in (f"{model}:{family}", model):
        if key in table:
            return float(table[key])
    return DEFAULT_LOW_SCORE_THRESHOLD


def top_refs_for(ctx: Any) -> list[dict[str, Any]]:
    """Top-5 {ref, score, source}; source 'direct' when no similarity (exact lookup)."""
    if ctx is None:
        return []
    rows: list[tuple[float | None, str]] = []
    for v in getattr(ctx, "verses", None) or []:
        try:
            ref = f"{normalize_book_name(v.book)} {int(v.chapter)}:{int(v.verse)}"
        except Exception:  # noqa: BLE001
            continue
        rows.append((v.similarity, ref))
    for p in getattr(ctx, "passages", None) or []:
        rows.append((p.similarity, str(p.reference)[:60]))
    rows.sort(key=lambda r: (r[0] is None, -(r[0] or 0.0)))
    return [
        {
            "ref": ref,
            "score": None if score is None else round(float(score), 4),
            "source": "direct" if score is None else "search",
        }
        for score, ref in rows[:MAX_TOP_REFS]
    ]


def compute_signature(
    *,
    reasons: list[str],
    intent: str,
    language: str,
    translation: str,
    topics: list[str],
) -> str:
    """Dedup key: reasons + intent + language + translation + sorted topics (order-insensitive)."""
    parts = [
        ",".join(sorted(reasons)),
        intent,
        language,
        translation,
        ",".join(sorted(topics)),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def embedding_identity() -> tuple[str, str]:
    model = (
        settings.azure_embedding_deployment
        if settings.embedding_provider == "azure_openai"
        else settings.embedding_model
    )
    return settings.embedding_provider, model


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def make_row(**fields: Any) -> dict[str, Any]:
    """Complete DB row from the derived fields (adds signature + timestamps)."""
    now = datetime.now(UTC)
    row = dict(fields)
    row["signature_sha256"] = compute_signature(
        reasons=row["reasons"],
        intent=row["intent"],
        language=row["language"],
        translation=row["translation"],
        topics=row["topics"],
    )
    row["created_at"] = now
    row["last_seen_at"] = now
    row["expires_at"] = now + timedelta(days=settings.retrieval_miss_retention_days)
    row["hit_count"] = 1
    return row


def build_retrieval_miss_upsert(**row: Any):
    """Atomic upsert (separate so tests can compile it).

    On conflict only counters/last-seen and the latest diagnostic fields change;
    ``expires_at``, ``created_at`` and ``session_id_hash`` are left alone so the
    retention period is fixed from first sight.
    """
    stmt = insert(RetrievalMissSample).values(**row)
    return stmt.on_conflict_do_update(
        index_elements=[RetrievalMissSample.signature_sha256],
        set_={
            "hit_count": RetrievalMissSample.hit_count + 1,
            "last_seen_at": stmt.excluded.last_seen_at,
            "top_refs": stmt.excluded.top_refs,
            "top_score": stmt.excluded.top_score,
            "threshold": stmt.excluded.threshold,
            "cited_outside_pool": stmt.excluded.cited_outside_pool,
            "expansion_terms": stmt.excluded.expansion_terms,
        },
    )


async def record_retrieval_miss(**fields: Any) -> None:
    """Upsert one miss row. Best-effort: gated by the flag and never raises."""
    if not settings.retrieval_miss_capture_enabled:
        return
    try:
        from scripture.database import async_session_factory

        stmt = build_retrieval_miss_upsert(**make_row(**fields))

        async def _do_record() -> None:
            async with async_session_factory() as db:
                try:
                    await db.execute(stmt)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise

        await run_with_disconnect_retry(_do_record, op_name="record_retrieval_miss")
    except Exception as exc:  # noqa: BLE001 - capture must never affect the reply
        logger.warning("retrieval miss capture failed", extra={"error": type(exc).__name__})


def emit_retrieval_miss(fields: dict[str, Any]) -> None:
    """OTel counter per reason + one structured log event (no ``session_id_hash``)."""
    for reason in fields["reasons"]:
        chat_retrieval_miss_counter.add(
            1,
            {
                "reason": reason,
                "language": fields["language"],
                "translation": fields["translation"],
                "intent": fields["intent"],
            },
        )
    logger.info(
        "rag_retrieval_miss",
        extra={k: v for k, v in fields.items() if k != "session_id_hash"},
    )


_PENDING: set[asyncio.Task] = set()


def schedule_retrieval_miss(**fields: Any) -> None:
    """Emit telemetry now and persist in a background task. Never raises, never awaits."""
    try:
        emit_retrieval_miss(fields)
        task = asyncio.create_task(record_retrieval_miss(**fields))
        _PENDING.add(task)
        task.add_done_callback(_PENDING.discard)
    except Exception as exc:  # noqa: BLE001
        logger.debug("retrieval miss scheduling failed: %s", type(exc).__name__)


async def purge_expired_retrieval_misses() -> int:
    """Delete rows whose ``expires_at`` is in the past. Returns the rowcount."""
    try:
        from scripture.database import async_session_factory
    except Exception:
        return 0

    now = datetime.now(UTC)
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                delete(RetrievalMissSample).where(RetrievalMissSample.expires_at < now)
            )
            await db.commit()
            return int(getattr(result, "rowcount", 0) or 0)
        except Exception:
            await db.rollback()
            return 0


__all__ = [
    "RetrievalTrace",
    "_hash_session_id",
    "best_score",
    "build_retrieval_miss_upsert",
    "classify_miss",
    "compute_signature",
    "embedding_identity",
    "emit_retrieval_miss",
    "make_row",
    "pool_keys",
    "purge_expired_retrieval_misses",
    "record_retrieval_miss",
    "refs_outside_pool",
    "resolve_low_score_threshold",
    "sanitize_expansion_terms",
    "schedule_retrieval_miss",
    "top_refs_for",
    "topics_for_record",
]
