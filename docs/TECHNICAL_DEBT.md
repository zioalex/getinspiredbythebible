# Technical Debt

This document tracks known technical debt and planned refactoring work.

## High Priority

### Refactor SQLAlchemy Models to Use `Mapped[]` Type Annotations

**Status:** ✅ Done (BITB-009, PR #984)
**Priority:** Medium
**Impact:** Improved type safety, removes mypy suppressions

#### Resolution

All models in `scripture/models.py` and `feedback/models.py` already use SQLAlchemy 2.0's
`Mapped[]` / `mapped_column()` syntax (landed in an earlier, undocumented PR — this entry
was stale). No `Column()`-style declarations remain in the ORM layer, and the
`[[tool.mypy.overrides]]` suppressions described below are no longer present in
`api/pyproject.toml`.

Current shape, e.g. `scripture/models.py`:

```python
class Verse(Base):
    __tablename__ = "verses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    text: Mapped[str] = mapped_column(Text)
    translation: Mapped[str] = mapped_column(
        String(20), ForeignKey("translations.code", ondelete="CASCADE"), default="kjv"
    )
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )
```

The only remaining `# type: ignore` suppressions in `scripture/*` and `routes/*` were four
lines in `routes/scripture.py` (`search_scripture`, `search_text`), and they were unrelated
to model typing — they suppressed a FastAPI parameter-ordering issue (`Depends`-based
params defaulted to `None` after `Query(...)`-defaulted params). BITB-009 closed those out
by reordering the dependency-injection params first, matching the existing pattern in
`get_verse` / `get_verse_range`.

#### Historical context (superseded)

The section below described the original problem before the `Mapped[]` conversion landed;
kept for reference.

<details>
<summary>Original problem writeup</summary>

Models previously used SQLAlchemy 1.x-style `Column()` declarations, which mypy saw as
`Column[str]` rather than the runtime `str` value, requiring `arg-type` suppressions in
`scripture.*` and `routes.*`. The fix was to convert to `Mapped[type] = mapped_column(...)`
so mypy understands `book.name` is `str`, not `Column[str]`.

</details>

#### References

- [SQLAlchemy 2.0 Documentation - Mapped Column Declarations](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html#orm-declarative-mapped-column)
- [SQLAlchemy 2.0 Migration Guide](https://docs.sqlalchemy.org/en/20/changelog/migration_20.html)
- [Mypy and SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/mypy.html)

---

## Medium Priority

### Migrate to ESLint 9 and Flat Config

**Status:** Planned
**Priority:** Medium
**Effort:** 2-4 hours
**Impact:** Removes deprecation warnings, enables latest lint rules

#### Current State

The project uses ESLint 8.x which is now deprecated. ESLint 9.x is the current
supported version and uses a new "flat config" format.

Current setup:

- `eslint`: `~8.56.0` (deprecated)
- `eslint-config-next`: `14.x` (requires ESLint 8.x)

#### Why We Can't Just Upgrade

ESLint 9.x introduced breaking changes:

1. New flat config format (`eslint.config.js` instead of `.eslintrc.json`)
2. `eslint-config-next` 16.x requires ESLint 9.x
3. Many ESLint plugins need updates for flat config compatibility

#### Upgrade Path

1. Upgrade `eslint` to `^9.0.0`
2. Upgrade `eslint-config-next` to `16.x`
3. Convert `.eslintrc.json` to `eslint.config.js` (flat config)
4. Update any custom ESLint rules for flat config compatibility
5. Test thoroughly - new rules may flag new issues

#### Useful Links

- [ESLint 9.0.0 Migration Guide](https://eslint.org/docs/latest/use/migrate-to-9.0.0)
- [ESLint Flat Config](https://eslint.org/docs/latest/use/configure/configuration-files-new)
- [Next.js ESLint Config](https://nextjs.org/docs/app/building-your-application/configuring/eslint)

---

### Claude API Type Hints

**Status:** Documented
**Priority:** Low
**Effort:** 30 minutes

#### Problem Description

Claude SDK uses strict type signatures expecting specific parameter structures.
Our dynamic dict approach requires suppressing `call-overload` errors:

```python
request_params = {
    "model": self.model,
    "max_tokens": max_tokens,
    "messages": converted_messages,
}
response = await self._client.messages.create(**request_params)  # type: ignore[call-overload]
```

#### Root Cause Analysis

The Anthropic SDK defines multiple overload signatures and doesn't accept generic
`**kwargs` unpacking from a dict. The type checker can't verify the dict contains
the right keys.

#### Current Workaround Strategy

Inline `# type: ignore[call-overload]` comments in:

- `providers/claude.py` line 73 (create)
- `providers/claude.py` line 109 (stream)

#### Proposed Solution Approach

Either:

1. Accept the type ignores as reasonable (runtime works fine)
2. Unpack parameters explicitly:

   ```python
   response = await self._client.messages.create(
       model=self.model,
       max_tokens=max_tokens,
       messages=converted_messages,
       temperature=temperature,
       system=system_prompt if system_prompt else NOT_GIVEN,
   )
   ```

Decision: Keep current approach. Type ignores are acceptable for SDK compatibility issues where runtime behavior is correct.

---

## Low Priority

### Frontend Testing

**Status:** Vitest + RTL Complete, E2E Pending
**Priority:** Medium (E2E remaining)
**Effort:** 4-6 hours (E2E only)

#### Completed (February 2026)

- ✅ Added Vitest for component unit tests
- ✅ Added React Testing Library for integration tests
- ✅ Configured Vitest with jsdom environment
- ✅ Set up test utilities and global test setup
- ✅ Comprehensive component test coverage (100 tests):
  - `ChatMessage.test.tsx` - Message rendering with responsive styles
  - `ChapterModal.test.tsx` - Modal behavior and responsive layout
  - `ChurchFinderModal.test.tsx` - Church finder modal tests
  - `ChurchFinderBanner.test.tsx` - Banner component tests
  - `page.test.tsx` - Main page component with responsive behavior
  - `api.test.ts` - API client functions with mocked fetch
  - `verseExtraction.test.ts` - Verse reference extraction logic

#### Remaining Work

- Add Playwright or Cypress for E2E tests

### Code Coverage

**Status:** Not implemented
**Priority:** Low
**Effort:** 1-2 hours

- Add pytest-cov for backend coverage
- Add istanbul/nyc for frontend coverage
- Integrate coverage reports into CI/CD

### Mock Ollama in Tests

**Status:** Tests use real Ollama settings
**Priority:** Low
**Effort:** 2-3 hours

- Mock LLM provider calls in unit tests
- Reduce test execution time
- Remove dependency on Ollama being available

---

## Resolved

### Dependency Management and CI Reliability (January 2026)

**PRs:** #7, #8, #9, #10

#### Problems Addressed

1. **Dependabot proposed breaking updates** - PR #3 attempted to upgrade
   `eslint-config-next` from 14.x to 16.x, which requires ESLint 9.x (not compatible)
2. **Version mismatch** - `next` was 14.2.35 but `eslint-config-next` was 14.1.0
3. **CI masked failures** - `continue-on-error: true` on lint/test steps hid real issues
4. **Loose version ranges** - Caret (`^`) ranges allowed potentially breaking minor updates

#### Solutions Implemented

| PR | Change | Impact |
|----|--------|--------|
| #7 | Added `.github/dependabot.yml` | Prevents major version bumps, groups related deps |
| #8 | Synced `eslint-config-next` to 14.2.35 | Matches `next` version |
| #9 | Removed `continue-on-error` from CI | Failures now properly fail the build |
| #9 | Added `needs` to integration-tests | Skips integration tests if unit tests fail |
| #10 | Changed eslint/typescript to tilde (`~`) | Only patch updates allowed |

#### Configuration Files Added/Modified

- `.github/dependabot.yml` (new) - Controls automatic dependency updates
- `.github/workflows/test_update.yml` - Improved reliability
- `frontend/package.json` - Stricter version pinning

---

## Document Metadata

**Last Updated:** January 21, 2026
