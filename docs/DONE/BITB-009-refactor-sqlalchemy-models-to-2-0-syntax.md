---
id: BITB-009
status: done
priority: P2
size: L
rank: 1000
prs: [984]
---

# BITB-009: Refactor SQLAlchemy Models to 2.0 Syntax

**Migration note (2026-11-13, status):** `api/scripture/models.py` and `api/feedback/models.py` are fully `Mapped[]`/`DeclarativeBase`; zero `= Column(...)` usages remain repo-wide, and PR #984 removed the remaining `scripture/*`/`routes/*` mypy suppressions to close this stale story.
**Migration note (2026-11-13, size):** (found already ~90% done by an earlier, undocumented PR; PR #984 closed the remainder)

**As a** developer,
**I want** SQLAlchemy models to use `Mapped[]` annotations,
**so that** MyPy can type-check database code and we remove `# type: ignore` comments.

**Acceptance Criteria:**

- [x] All models in `api/scripture/models.py` use `Mapped[]` syntax (already done pre-PR)
- [x] MyPy suppressions removed from `scripture/*` and `routes/*` (4 lines in `routes/scripture.py`, unrelated to model typing — see below)
- [x] All tests pass with no type errors
- [x] Database queries still work correctly
- [x] Documentation updated with new model syntax examples

**Resolution note:** `scripture/models.py` and `feedback/models.py` were already fully
`Mapped[]`/`mapped_column()` when this story was picked up, and the `pyproject.toml`
mypy overrides the story references no longer exist. The only remaining suppressions in
scope were `# type: ignore` on `db`/`embedding` params in `search_scripture` and
`search_text` (`routes/scripture.py`), caused by FastAPI dependency params being
defaulted to `None` after `Query(...)`-defaulted params — unrelated to model typing.
Fixed by reordering params (DI params first), matching `get_verse`/`get_verse_range`.

**Tech Constraints:**

- Must maintain compatibility with existing database schema
- Must work with AsyncPG
- Must not break existing queries in `repository.py`

**Out of Scope:**

- Migrating to SQLAlchemy 2.0 declarative base (can use hybrid syntax)
- Rewriting all queries to use new-style syntax

**Related:** TASKS.md #3.3, TECHNICAL_DEBT.md #1
