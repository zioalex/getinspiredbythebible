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
from scripture.models import Base, Book, Chapter, Passage, Topic, Translation, Verse
from scripture.repository import ScriptureRepository

# Sentinel identifiers so the rolled-back seed never collides with real data.
_TRANSLATION = "zzint"
_BOOK_NAME = "ZZ Integration Book"
_VERSE_TEXT = "For God so loved the world that he gave his only Son."
_TOPIC_NAME = "ZZ Integration Topic"


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
            # `verse_tsv` itself is an ORM model, so create_all makes the table --
            # but the trigger that keeps it in sync lives only in Alembic r0004,
            # and create_all knows nothing about triggers. Without it the seeded
            # verse would have no tsvector row and every FTS assertion below
            # would pass or fail for the wrong reason. Kept character-identical
            # to r0004; `test_verse_tsv_trigger_matches_the_indexed_expression`
            # is what catches the two drifting apart.
            await conn.execute(
                text(
                    "CREATE OR REPLACE FUNCTION verse_tsv_sync() RETURNS trigger AS $$ "
                    "BEGIN "
                    "INSERT INTO verse_tsv (verse_id, text_tsv) "
                    "VALUES (NEW.id, to_tsvector('simple', NEW.text)) "
                    "ON CONFLICT (verse_id) DO UPDATE SET text_tsv = EXCLUDED.text_tsv; "
                    "RETURN NEW; "
                    "END; $$ LANGUAGE plpgsql"
                )
            )
            await conn.execute(text("DROP TRIGGER IF EXISTS verses_tsv_sync ON verses"))
            await conn.execute(
                text(
                    "CREATE TRIGGER verses_tsv_sync AFTER INSERT OR UPDATE OF text ON verses "
                    "FOR EACH ROW EXECUTE FUNCTION verse_tsv_sync()"
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
        session.add(Topic(name=_TOPIC_NAME, embedding=vec))
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


# ── BITB-055: guard the _resolve_cited_verses SQL paths ───────────────────
# _resolve_cited_verses calls get_verse (single lookup) and get_verses_in_range
# (range lookup). These tests run the real SQL against the seeded DB so a
# regression in either path fails before merge — the same class of silent bug
# that caused the 2-week verse-less outage (a stray # in the SQL string).


async def test_get_verse_executes_against_real_db(seeded_repo):
    """get_verse must return the seeded verse via real SQL.

    Guards the _resolve_cited_verses single-verse branch used by the chat
    pipeline. Fails on any SQL syntax regression (the stray-# class of bug)."""
    verse = await seeded_repo.get_verse(_BOOK_NAME, 3, 16, translation=_TRANSLATION)
    assert verse is not None, "get_verse returned None for the seeded verse"
    assert verse.text == _VERSE_TEXT
    assert verse.chapter_number == 3
    assert verse.verse_number == 16


async def test_get_verses_in_range_executes_against_real_db(seeded_repo):
    """get_verses_in_range must execute real SQL and return the seeded verse.

    Guards the _resolve_cited_verses range branch. Only verse 16 is seeded,
    so asking for 16-18 returns one row — enough to prove the SQL ran."""
    verses = await seeded_repo.get_verses_in_range(
        _BOOK_NAME, 3, start_verse=16, end_verse=18, translation=_TRANSLATION
    )
    assert verses, "get_verses_in_range returned empty for the seeded range"
    assert any(v.text == _VERSE_TEXT for v in verses)


# ── Plain (non-boosted/non-hybrid) semantic-search builders ───────────────
# These use pgvector's cosine_distance operator directly via the ORM but,
# unlike the raw-SQL builders above, were previously only ever asserted
# against a mock's canned return value -- never executed against real
# Postgres+pgvector.


async def test_search_verses_semantic_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_verses_semantic(
        query_embedding=_seed_vector(), translation=_TRANSLATION
    )
    assert rows, "semantic search returned no rows from the real DB"
    verse, similarity = rows[0]
    assert verse.text == _VERSE_TEXT
    # Identical vector -> cosine distance 0 -> similarity 1.0.
    assert similarity == pytest.approx(1.0)


async def test_search_passages_semantic_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_passages_semantic(query_embedding=_seed_vector())
    assert rows, "passage semantic search returned no rows from the real DB"
    passage, similarity = rows[0]
    assert passage.text == _VERSE_TEXT
    assert similarity == pytest.approx(1.0)


async def test_search_topics_semantic_executes_against_real_db(seeded_repo):
    rows = await seeded_repo.search_topics_semantic(query_embedding=_seed_vector())
    assert rows, "topic semantic search returned no rows from the real DB"
    topic, similarity = rows[0]
    assert topic.name == _TOPIC_NAME
    assert similarity == pytest.approx(1.0)


async def test_search_verses_text_executes_against_real_db(seeded_repo):
    verses = await seeded_repo.search_verses_text(query="loved the world")
    assert verses, "text search returned no rows from the real DB"
    assert any(v.text == _VERSE_TEXT for v in verses)


# ── BITB-096: the verse_tsv side table ────────────────────────────────────
# The persisted tsvector lives in `verse_tsv`, not in a `verses.text_tsv`
# generated column. The column form rewrites the whole table under ACCESS
# EXCLUSIVE, which took production down for ~45 minutes on 2026-08-17; see
# Alembic r0004. These guard the properties BITB-095's query switch depends
# on -- that the row exists, that a trigger keeps it current, and above all
# that it holds *exactly* the expression the queries and index use.


async def test_verse_tsv_row_is_populated_for_every_verse(seeded_repo):
    """The seeded verse must have a `verse_tsv` row. Nothing in the app writes
    one, so this passes only if the r0004 trigger fired on insert."""
    tsv_value = (
        await seeded_repo.session.execute(
            text(
                "SELECT t.text_tsv FROM verse_tsv t "
                "JOIN verses v ON v.id = t.verse_id "
                "WHERE v.translation = :translation"
            ).bindparams(translation=_TRANSLATION)
        )
    ).scalar_one()
    assert tsv_value is not None, "the trigger did not populate verse_tsv for the seeded verse"


async def test_verse_tsv_trigger_matches_the_indexed_expression(seeded_repo):
    """`verse_tsv.text_tsv` must equal `to_tsvector('simple', text)` exactly.

    This is the assertion the whole design rests on. BITB-095 replaces
    `to_tsvector('simple', v.text)` in three queries with a read of this
    column, and that is a plan change rather than a semantics change *only*
    while the two expressions are identical. If someone edits the trigger to
    use a different text search configuration, this fails.
    """
    agrees = (
        await seeded_repo.session.execute(
            text(
                "SELECT bool_and(t.text_tsv = to_tsvector('simple', v.text)) "
                "FROM verses v JOIN verse_tsv t ON t.verse_id = v.id"
            )
        )
    ).scalar_one()
    assert agrees is True, "verse_tsv drifted from to_tsvector('simple', text)"


async def test_verse_tsv_trigger_follows_text_updates(seeded_repo):
    """Updating `verses.text` must update the stored tsvector.

    A generated column got this for free; a side table only gets it from the
    trigger, so it has to be tested rather than assumed. `verses` takes no
    writes at runtime, but the seeding scripts do write it.
    """
    session = seeded_repo.session
    await session.execute(
        text("UPDATE verses SET text = :new_text WHERE translation = :translation").bindparams(
            new_text="Rejoice in hope, be patient in tribulation.",
            translation=_TRANSLATION,
        )
    )
    matched = (
        await session.execute(
            text(
                "SELECT t.text_tsv = to_tsvector('simple', v.text) "
                "FROM verses v JOIN verse_tsv t ON t.verse_id = v.id "
                "WHERE v.translation = :translation"
            ).bindparams(translation=_TRANSLATION)
        )
    ).scalar_one()
    assert matched is True, "verse_tsv did not follow the update to verses.text"


async def test_verse_tsv_has_its_gin_index_and_cascades(seeded_repo):
    """The GIN index is what makes the BITB-095 switch worth doing, and the
    cascade is what keeps `verse_tsv` from outliving its verses -- the side
    table's substitute for a column's automatic lifecycle."""
    session = seeded_repo.session
    index_def = (
        await session.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_verse_tsv_tsv'")
        )
    ).scalar_one_or_none()
    assert index_def is not None, "idx_verse_tsv_tsv is missing"
    assert "gin" in index_def.lower()

    delete_action = (
        await session.execute(
            text(
                "SELECT confdeltype FROM pg_constraint "
                "WHERE conrelid = 'verse_tsv'::regclass AND contype = 'f'"
            )
        )
    ).scalar_one()
    assert delete_action == "c", "verse_tsv.verse_id must be ON DELETE CASCADE"
