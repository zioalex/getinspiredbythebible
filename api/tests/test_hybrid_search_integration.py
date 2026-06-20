"""
Integration tests that execute the real scripture-search SQL against a live
Postgres + pgvector, instead of mocking ``session.execute``.

Why this file exists
--------------------
Two production-breaking SQL bugs shipped because every other test mocks
``session.execute`` — the SQL was never run against a database:

* PR #764: a stray ``#`` made every query start with a Python comment
  (``syntax error at or near "#"``).
* The ``:embedding::vector`` cast that SQLAlchemy's ``text()`` could not bind, so
  asyncpg received a literal ``:`` (``syntax error at or near ":"``) and the
  embedding was never bound.

These tests run all four raw-SQL builders against a real pgvector database with a
couple of seeded rows, so an execution-level regression fails *before merge*.

Skips automatically when no Postgres is reachable (e.g. local runs without a DB).
CI's ``backend-tests`` job provides a ``pgvector/pgvector`` service container with
``DATABASE_URL`` set, so these run on every PR.

The embedding dimension is taken from ``settings.embedding_dimensions`` (1024 for
the local Ollama model, 1536 for Azure ``text-embedding-3-small`` in production),
so the seeded vectors always match the schema column regardless of environment.
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from config import settings
from scripture.database import get_async_database_url
from scripture.models import Base, Book, Chapter, Passage, Translation, Verse
from scripture.repository import ScriptureRepository

# Sentinel identifiers so the rolled-back seed never collides with real data.
_TRANSLATION = "zzint"
_BOOK_NAME = "ZZ Integration Book"
_VERSE_TEXT = "For God so loved the world that he gave his only Son."


def _seed_vector() -> list[float]:
    """Non-zero vector of the configured dimension. The query reuses this exact
    vector, so cosine similarity is 1.0 and the verse clears every threshold."""
    vec = [0.0] * settings.embedding_dimensions
    vec[0] = 1.0
    return vec


@pytest_asyncio.fixture
async def seeded_repo():
    """A ``ScriptureRepository`` backed by a real session with one seeded verse and
    passage. All writes happen inside a transaction that is rolled back, so the
    database is left untouched. Skips when Postgres/pgvector is not reachable."""
    url, connect_args = get_async_database_url()
    engine = create_async_engine(url, poolclass=NullPool, connect_args=connect_args)

    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            # verse_topics is a raw-migration junction table (migration 004), not an
            # ORM model, so create_all does not make it. The boosted builders LEFT
            # JOIN it, so it must exist for them to run.
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS verse_topics ("
                    "verse_id INTEGER REFERENCES verses(id) ON DELETE CASCADE, "
                    "topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE, "
                    "PRIMARY KEY (verse_id, topic_id))"
                )
            )
    except Exception as exc:  # connection refused, auth failure, etc.
        await engine.dispose()
        pytest.skip(f"Postgres+pgvector not reachable: {exc}")

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    await session.begin()
    try:
        vec = _seed_vector()
        book = Book(name=_BOOK_NAME, abbreviation="ZZ", testament="new", position=999)
        chapter = Chapter(number=3, book=book)
        verse = Verse(
            book=book,
            chapter=chapter,
            chapter_number=3,
            verse_number=16,
            text=_VERSE_TEXT,
            translation=_TRANSLATION,
            embedding=vec,
        )
        session.add_all(
            [
                Translation(
                    code=_TRANSLATION,
                    name="Integration",
                    language="English",
                    language_code="en",
                ),
                book,
                chapter,
                verse,
            ]
        )
        await session.flush()  # assigns book.id / verse.id for the passage + reads
        session.add(
            Passage(
                title="ZZ Integration Passage",
                start_book_id=book.id,
                start_chapter=3,
                start_verse=16,
                end_chapter=3,
                end_verse=18,
                text=_VERSE_TEXT,
                embedding=vec,
            )
        )
        await session.flush()
        yield ScriptureRepository(session)
    finally:
        await session.rollback()
        await session.close()
        await engine.dispose()


async def test_search_verses_hybrid_executes_against_real_db(seeded_repo):
    """The production-critical path: real hybrid SQL must run and return the verse.

    Fails with PostgresSyntaxError on the ``:embedding::vector`` regression."""
    rows = await seeded_repo.search_verses_hybrid(
        query_text="loved the world",
        query_embedding=_seed_vector(),
        translation=_TRANSLATION,
    )
    assert rows, "hybrid search returned no rows from the real DB"
    verse, score = rows[0]
    assert verse.text == _VERSE_TEXT
    assert score > 0


async def test_search_verses_semantic_boosted_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_verses_semantic_boosted(
        query_embedding=_seed_vector(),
        boost_topics=["faith"],  # no matching topics → verse returned via base score
        translation=_TRANSLATION,
    )
    assert rows, "semantic-boosted search returned no rows from the real DB"
    assert rows[0][0].text == _VERSE_TEXT


async def test_search_verses_hybrid_boosted_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_verses_hybrid_boosted(
        query_text="loved the world",
        query_embedding=_seed_vector(),
        boost_topics=["faith"],
        translation=_TRANSLATION,
    )
    assert rows, "hybrid-boosted search returned no rows from the real DB"
    assert rows[0][0].text == _VERSE_TEXT


async def test_search_passages_hybrid_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_passages_hybrid(
        query_text="loved the world",
        query_embedding=_seed_vector(),
    )
    assert rows, "passage hybrid search returned no rows from the real DB"
    assert rows[0][0].text == _VERSE_TEXT
