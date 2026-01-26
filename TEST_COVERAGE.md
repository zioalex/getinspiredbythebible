# Test Coverage - Multilingual Bible Support

**Total Tests**: 48 (all passing ✅)
**Test Files**: 4
**Last Updated**: 2026-01-25

## Test Summary

```text
✅ 48 tests passing
⚠️  3 warnings (Pydantic deprecation - non-critical)
❌ 0 failures
```

---

## Test Breakdown

### 1. Model Tests (`test_models.py`) - 7 tests

Tests for SQLAlchemy models with multilingual support:

- ✅ `test_book_model_creation` - Book model instantiation
- ✅ `test_verse_model_creation` - Verse model basic creation
- ✅ `test_verse_model_with_translation` - Verse with translation field
- ✅ `test_verse_model_italian` - Italian verse (ita1927)
- ✅ `test_translation_model_creation` - Translation model (KJV)
- ✅ `test_translation_model_italian` - Italian translation metadata
- ✅ `test_translation_model_german` - German translation metadata

**Coverage:**

- Translation model with all fields
- Verse model with translation support
- Multiple language verse instantiation

---

### 2. Translation Configuration Tests (`test_translations.py`) - 21 tests

Tests for translation configurations and book name mappings:

#### Book Name Mappings (8 tests)

- ✅ `test_italian_book_names_complete` - All 66 Italian books mapped
- ✅ `test_german_book_names_complete` - All 66 German books mapped
- ✅ `test_italian_old_testament_books` - OT sample mappings (Genesi→Genesis)
- ✅ `test_italian_new_testament_books` - NT sample mappings (Matteo→Matthew)
- ✅ `test_german_old_testament_books` - OT sample mappings (1. Mose→Genesis)
- ✅ `test_german_new_testament_books` - NT sample mappings (Matthäus→Matthew)
- ✅ `test_all_italian_books_unique` - No duplicate English names
- ✅ `test_all_german_books_unique` - No duplicate English names

#### Translation Configurations (7 tests)

- ✅ `test_translations_config_exists` - All 4 translations exist
- ✅ `test_kjv_translation_config` - KJV metadata valid
- ✅ `test_italian_translation_config` - Italian (ita1927) metadata valid
- ✅ `test_german_translation_config` - German (deu1912) metadata valid
- ✅ `test_get_translation_config` - Config retrieval function
- ✅ `test_get_translation_config_invalid` - Error handling for invalid codes
- ✅ `test_list_available_translations` - List all translations

#### Helper Functions (3 tests)

- ✅ `test_map_book_name_italian` - Italian→English mapping (Genesi→Genesis)
- ✅ `test_map_book_name_german` - German→English mapping (1. Mose→Genesis)
- ✅ `test_map_book_name_english` - English passthrough (Genesis→Genesis)
- ✅ `test_map_book_name_unknown_book` - Unknown book fallback

#### Validation Tests (3 tests)

- ✅ `test_translation_urls_valid` - All URLs well-formed
- ✅ `test_translation_sources` - Valid source names (thiagobodruk, getbible)

**Coverage:**

- Complete book name mappings (132 total: 66 Italian + 66 German)
- Translation metadata validation
- URL and source validation
- Helper function behavior

---

### 3. Integration Tests (`test_multilingual_integration.py`) - 13 tests

Integration tests verifying models + configurations work together:

#### Model Integration (3 tests)

- ✅ `test_verse_translation_can_be_set` - Verse translation field works
- ✅ `test_verse_supports_multiple_translations` - Same verse, multiple translations
- ✅ `test_verse_repr_includes_translation` - Repr shows translation

#### Translation Model (2 tests)

- ✅ `test_translation_model_with_defaults` - Default values work
- ✅ `test_translation_model_repr` - Repr output format

#### Configuration Validation (5 tests)

- ✅ `test_all_configured_translations_have_valid_metadata` - Required fields present
- ✅ `test_translation_language_codes_valid` - ISO 639-1 codes (en, it, de)
- ✅ `test_only_one_default_translation` - Only KJV is default
- ✅ `test_translation_code_matches_config_key` - Code consistency
- ✅ `test_all_translations_public_domain` - License verification

#### Book Name Mapping Integration (2 tests)

- ✅ `test_italian_and_german_have_book_name_mappings` - Non-English have mappings
- ✅ `test_english_translations_no_book_name_mappings` - English doesn't need mappings

#### Database Schema (1 test)

- ✅ `test_verse_unique_constraint_includes_translation` - Unique constraint verified

**Coverage:**

- Cross-cutting concerns (models + configs)
- Business rule validation
- Database constraint verification

---

## Test Execution

Run all multilingual tests:

```bash
# All tests
.venv/bin/python -m pytest api/tests/test_models.py \
                                api/tests/test_translations.py \
                                api/tests/test_multilingual_integration.py \
                                -v

# Individual test files
.venv/bin/python -m pytest api/tests/test_models.py -v
.venv/bin/python -m pytest api/tests/test_translations.py -v
.venv/bin/python -m pytest api/tests/test_multilingual_integration.py -v

# Specific test
.venv/bin/python -m pytest api/tests/test_translations.py::test_map_book_name_italian -v

# With coverage
.venv/bin/python -m pytest --cov=scripture --cov=translations api/tests/
```

---

## What's Tested

### ✅ Covered

1. **Models**: Translation & Verse with multilingual support
2. **Book Name Mappings**: All 132 mappings (66 Italian + 66 German)
3. **Translation Configs**: KJV, WEB, ITA1927, DEU1912
4. **Helper Functions**: map_book_name, get_translation_config, list_available_translations
5. **Validation**: URLs, source names, language codes, licenses
6. **Constraints**: Unique constraint on (book, chapter, verse, translation)
7. **Integration**: Models + configs work together

### ⏳ Not Yet Tested (Future)

1. **Database Operations**: Actual DB inserts/updates with translations
2. **Database Schema**: Manual schema updates or SQLAlchemy migrations
3. **Bible Loader**: load_bible.py functionality
4. **Embedding Generation**: create_embeddings.py with multilingual
5. **API Endpoints**: Translation filtering in scripture routes
6. **Cross-Lingual Search**: English query → Italian results
7. **Frontend**: Translation selector component

These will be added in later phases as the corresponding features are implemented.

---

## Key Test Patterns

### 1. Book Name Mapping Test Pattern

```python
def test_italian_book_mapping():
    assert ITALIAN_BOOK_NAMES["Genesi"] == "Genesis"
    assert ITALIAN_BOOK_NAMES["Matteo"] == "Matthew"
```

### 2. Translation Config Test Pattern

```python
def test_translation_config():
    config = TRANSLATIONS["ita1927"]
    assert config["code"] == "ita1927"
    assert config["language_code"] == "it"
```

### 3. Model Instantiation Pattern

```python
def test_verse_with_translation():
    verse = Verse(..., translation="ita1927")
    assert verse.translation == "ita1927"
```

---

## Coverage Metrics (Estimated)

- **Translation Configurations**: 100% (all 4 translations tested)
- **Book Name Mappings**: 100% (all 132 mappings tested)
- **Model Fields**: ~90% (core fields tested, some edge cases pending)
- **Helper Functions**: 100% (all public functions tested)
- **Integration**: ~70% (models + configs, pending DB/API)

---

## Running Tests in CI/CD

Tests are run automatically via pre-commit hooks and can be integrated into CI:

```yaml
# Example GitHub Actions
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
    - run: pip install -r api/requirements.txt
    - run: pytest api/tests/ -v
```

---

**Status**: All core tests passing ✅
**Next**: Add integration tests for Bible loader and API endpoints (Phases 7-12)

---

### 4. Database Schema Tests (`test_database_schema.py`) - 7 tests

Tests that verify database schema is correctly configured:

- ✅ `test_translation_table_exists` - Translation model has all required fields
- ✅ `test_verse_has_translation_column` - Verse has translation column
- ✅ `test_verse_table_constraints` - Unique constraint includes translation
- ✅ `test_verse_default_translation` - Translation defaults to 'kjv'
- ✅ `test_book_table_exists` - Book model structure
- ✅ `test_chapter_table_exists` - Chapter model structure
- ✅ `test_verse_relationships` - All relationships defined

**Coverage:**

- Schema validation (catches missing translation column errors)
- Default values verification
- Foreign key relationships
- Unique constraints with translation field
