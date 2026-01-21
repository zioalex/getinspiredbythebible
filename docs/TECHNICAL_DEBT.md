# Technical Debt

This document tracks known technical debt and planned refactoring work.

## High Priority

### Refactor SQLAlchemy Models to Use `Mapped[]` Type Annotations

**Status:** Planned
**Priority:** Medium
**Effort:** 2-3 hours
**Impact:** Improved type safety, removes mypy suppressions

#### Problem

Current models use SQLAlchemy 1.x-style `Column()` declarations:

```python
class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    # ... more columns
```

This causes mypy to see `Column[str]` types when analyzing code, but at runtime these are
actual `str` values. This mismatch requires suppressing `arg-type` errors in `scripture.*`
and `routes.*` modules.

#### Root Cause

1. **Static vs Runtime Types**: Mypy performs static analysis and sees the Column type
descriptors, not the runtime attribute values
2. **Legacy Syntax**: The Column-based syntax predates SQLAlchemy 2.0's improved type
annotations
3. **ORM Magic**: SQLAlchemy uses Python descriptors and metaclasses that mypy cannot
fully understand

#### Current Workaround

In `api/pyproject.toml`:

```toml
[[tool.mypy.overrides]]
module = "scripture.*"
disable_error_code = ["arg-type"]

[[tool.mypy.overrides]]
module = "routes.*"
disable_error_code = ["arg-type"]
```

This suppresses errors when passing ORM model attributes to Pydantic models:

```python
# Mypy sees: Column[str] passed where str expected
# Runtime: actual str value passed correctly
VerseResult(
    text=verse.text,  # mypy thinks this is Column[str], actually str
    chapter=verse.chapter_number,  # mypy thinks Column[int], actually int
)
```

#### Proposed Solution

Refactor to SQLAlchemy 2.0's `Mapped[]` syntax:

```python
from sqlalchemy.orm import Mapped, mapped_column

class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    # ... more columns
```

Benefits:

- ✅ Mypy understands that `book.name` is `str`, not `Column[str]`
- ✅ Better IDE autocomplete
- ✅ Removes need for error suppressions
- ✅ Aligns with SQLAlchemy 2.0 best practices
- ✅ More explicit about nullable vs non-nullable fields

#### Migration Steps

1. Update `scripture/models.py`:
   - Add `from sqlalchemy.orm import Mapped, mapped_column`
   - Convert each `Column()` to `Mapped[type] = mapped_column(...)`
   - Update relationship annotations

2. Update affected files:
   - `scripture/search.py`
   - `scripture/repository.py`
   - `routes/scripture.py`

3. Remove mypy overrides from `pyproject.toml`

4. Run full test suite to verify no regressions

5. Update documentation

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

**Status:** Placeholder exists
**Priority:** Medium
**Effort:** 4-6 hours

- Add Jest or Vitest for component unit tests
- Add React Testing Library for integration tests
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
