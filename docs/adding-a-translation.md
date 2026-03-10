# Adding a New Bible Translation

This guide walks you through every step needed to add a new language/translation to the app —
backend, frontend, and the testing checklist that proves it works.

---

## Background: how book names flow through the system

```text
User message (any language)
        │
        ▼
verse_parser.py ──► ALL_BOOK_NAMES (regex set)
                         built from:  TRANSLATION_REGISTRY values
                                    + EXTRA_REVERSE_MAPPINGS keys
        │
        │  normalize_book_name()
        ▼
  English book name  ──► DB query  ──► verse JSON (reference always in English)
        │
        ▼
  API response: { reference: "John 3:16", ... }
        │
        ▼
  Frontend extractVerseReferences()
        │  LOCALIZED_BOOK_TO_ENGLISH lookup
        ▼
  Set<"john 3:16">  ──► isVerseReferenced()  ──► verse card visible ✓
```

Everything hinges on two lookups:

| Layer | File | What it does |
| --- | --- | --- |
| Backend | `api/utils/translation_registry.py` | `ENGLISH_TO_*` dicts + `EXTRA_REVERSE_MAPPINGS` |
| Backend | `api/utils/book_names.py` | Auto-builds reverse dicts + `normalize_book_name()` |
| Backend | `api/utils/verse_parser.py` | `ALL_BOOK_NAMES` regex set + `parse_verse_reference()` |
| Frontend | `frontend/src/lib/verseExtraction.ts` | `LOCALIZED_BOOK_TO_ENGLISH` + `extractVerseReferences()` |

---

## Step 1 — Add the forward dict to `translation_registry.py`

Add an `ENGLISH_TO_<LANGUAGE>` dict with **exactly 66 entries** — one per Protestant canon book —
using the names that actually appear in the source feed (getbible.net, etc.):

```python
# Portuguese (Almeida Revista e Corrigida / almeida)
ENGLISH_TO_PORTUGUESE: dict[str, str] = {
    "Genesis": "Gênesis",
    "Exodus": "Êxodo",
    # ... 64 more entries ...
    "Revelation": "Apocalipse",
}
```

**Rules:**

- Keys must be the 66 standard English book names (see existing dicts for the exact list).
- Values must be unique — no two English books may map to the same localized name.
- Use the _canonical_ form from the feed, not a display-friendly variant.

---

## Step 2 — Handle citation forms (critical for inflecting languages)

> **This is the step that caused the Russian production bug.**
> Skip it and verse references will silently fail for your language.

### Does your language inflect book names?

Ask yourself: _when an LLM cites "John 3:16" in this language, does the book name change
its ending or gain a prefix compared to the standalone book title?_

| Language family | Example | Risk |
| --- | --- | --- |
| **Slavic** (Russian ✓, Ukrainian, Bulgarian, Serbian, Polish, Czech, Slovak) | Russian: canonical "Иоанн", but citations use genitive "Иоанна 3:16" | **High — always needed** |
| **Arabic** | Definite article "ال" prefix may appear in citation context | **Medium — verify with prompts** |
| **Romance, Germanic, CJK** (Italian, German, Spanish, French, Portuguese, Chinese, Korean, Hindi) | No inflection — same form used everywhere | **None** |

### If citation forms are needed

Add a `<LANGUAGE>_CITATION_FORMS` dict **immediately after** `ENGLISH_TO_<LANGUAGE>`.
Map each inflected citation form → canonical English name:

```python
ENGLISH_TO_RUSSIAN: dict[str, str] = { ... }  # nominative forms

# Russian genitive/citation forms — what an LLM writes when citing a verse
# ("Иоанна 3:16", not the nominative "Иоанн 3:16" stored in ENGLISH_TO_RUSSIAN)
RUSSIAN_CITATION_FORMS: dict[str, str] = {
    "Иоанна": "John",
    "Матфея": "Matthew",
    "Луки": "Luke",
    "Марка": "Mark",
    "Деяний": "Acts",
    # ... remaining unambiguous genitive forms ...
}
```

> **Ambiguity rule:** Omit any form shared by two or more books (e.g. bare "Петра" could be
> 1 Peter or 2 Peter). Include the numbered version instead ("1 Петра", "2 Петра") —
> those are unambiguous.

### How to collect citation forms

The most reliable method is to ask the LLM directly:

```text
In [language], how would you write a reference to John chapter 3 verse 16?
Now do the same for Matthew, Luke, Mark, Acts, Genesis, Psalms, Revelation.
```

Compare each answer to the canonical form in `ENGLISH_TO_<LANGUAGE>`.
Any form that differs → add it to `<LANGUAGE>_CITATION_FORMS`.

---

## Step 3 — Handle aliases (orthographic variants)

If the feed or LLM may produce forms that differ from the canonical value for reasons other
than grammatical inflection (encoding variant, BOM prefix, spacing variant, alternate historical
name), add a `<LANGUAGE>_ALIASES` dict:

```python
CHINESE_ALIASES: dict[str, str] = {
    "\ufeff创世记": "Genesis",   # BOM-prefixed variant from some feeds
    "启示录": "Revelation",      # Simplified variant vs canonical 啟示錄
}

KOREAN_ALIASES: dict[str, str] = {
    "예레미야애가": "Lamentations",  # no-space variant (some LLMs omit the space)
}

GERMAN_ALIASES: dict[str, str] = {
    "Rut": "Ruth",               # alternate spelling
    "Ester": "Esther",           # alternate spelling
    "Hohes Lied": "Song of Solomon",
    "Zefanja": "Zephaniah",
}
```

---

## Step 4 — Register the translation and merge aliases

```python
# In TRANSLATION_REGISTRY:
TRANSLATION_REGISTRY: dict[str, dict[str, str] | None] = {
    ...
    "almeida": ENGLISH_TO_PORTUGUESE,   # ← add your translation code here
}

# In EXTRA_REVERSE_MAPPINGS:
EXTRA_REVERSE_MAPPINGS: dict[str, str] = {
    **RUSSIAN_CITATION_FORMS,
    **RUSSIAN_ALIASES,
    **CHINESE_ALIASES,
    **KOREAN_ALIASES,
    **GERMAN_ALIASES,
    **PORTUGUESE_CITATION_FORMS,   # ← add if you created one
    # add new language citation forms and aliases here
}
```

**What updates automatically** (no further changes needed):

- `api/utils/book_names.py` — builds `<LANG>_TO_ENGLISH` reverse dict and `LOCALIZED_TO_ENGLISH`
- `api/utils/verse_parser.py` — extends `ALL_BOOK_NAMES` regex set with all new book names
- `scripts/translations.py` — uses `TRANSLATION_REGISTRY` for feed downloads

---

## Step 5 — Update the frontend lookup table

Open `frontend/src/lib/verseExtraction.ts` and add a section to `LOCALIZED_BOOK_TO_ENGLISH`.

The table maps **lowercased localized book name → lowercase English canonical name**. Add:

1. All 66 canonical forms from `ENGLISH_TO_<LANGUAGE>` (lowercased as keys)
2. All citation forms from `<LANGUAGE>_CITATION_FORMS` (if any)
3. All alias forms from `<LANGUAGE>_ALIASES` (if any)

```typescript
// ── Portuguese (Almeida / almeida) ──────────────────────────────────────
gênesis: "genesis",
êxodo: "exodus",
// ... 64 more ...
apocalipse: "revelation",
```

> **Why the frontend needs its own table:** The API always returns verse references in English
> ("John 3:16"). The frontend's `extractVerseReferences()` parses the user's message (which may
> be in any language), normalizes every book name to English via this table, and stores it in a
> `Set<string>`. Then `isVerseReferenced()` matches those English keys against the English keys
> from the API. Without this table, cross-language matching silently fails — verse cards never
> appear in the right pane.

---

## Step 6 — Verify with the test suite

Run the existing comprehensive tests.
They automatically cover any new language added to `TRANSLATION_REGISTRY` for structural integrity:

```bash
# Backend — structural integrity + normalize round-trips
DATABASE_URL=postgresql://... EMBEDDING_PROVIDER=ollama LLM_PROVIDER=ollama \
  python -m pytest api/tests/test_book_names_comprehensive.py -v

# Backend — parse_verse_reference end-to-end
python -m pytest api/tests/test_verse_parser.py -v

# Frontend — extractVerseReferences + isVerseReferenced
cd frontend && npx jest src/lib/verseExtraction.test.ts --no-coverage
```

### What the tests catch automatically

| Test | What it proves |
| --- | --- |
| `test_<lang>_dict_has_66_entries` | You didn't miss a book |
| `test_<lang>_dict_has_no_duplicate_values` | No two English books map to the same localized name |
| `test_<lang>_all_values_round_trip_via_normalize` | Every canonical form normalizes back correctly |
| `test_extra_reverse_mappings_all` | Every alias + citation form resolves correctly |
| `TestParseVerseReferenceNonEnglish` | Full pipeline from raw text → parsed reference |
| `LOCALIZED_BOOK_TO_ENGLISH table integrity` | Frontend table is consistent with backend dicts |

### What you must add manually

The structural tests run for every language in `TRANSLATION_REGISTRY` automatically.
But you should add **language-specific tests** for:

1. **Citation forms** — one test per citation form you added:

```python
def test_parse_portuguese_genitive_john():
    result = parse_verse_reference("João 3:16")
    assert result is not None and result.book == "John"
```

1. **Frontend cross-language matching** — confirm verse cards appear:

```typescript
it("matches Portuguese verse card from Portuguese message", () => {
  const refs = extractVerseReferences("João 3:16");
  const card = { reference: "John 3:16" } as any;
  expect(isVerseReferenced(card, refs)).toBe(true);
});
```

1. **Numbered books** — especially if your language's numbering pattern differs from English:

```typescript
it("matches 1 Corinthians from Portuguese message", () => {
  const refs = extractVerseReferences("1 Coríntios 13:4");
  const card = { reference: "1 Corinthians 13:4" } as any;
  expect(isVerseReferenced(card, refs)).toBe(true);
});
```

---

## Quick checklist

```text
Backend
-------
☐ ENGLISH_TO_<LANG> added to translation_registry.py (exactly 66 entries)
☐ All values are unique within the dict
☐ <LANGUAGE>_CITATION_FORMS added (if language inflects book names)
☐ <LANGUAGE>_ALIASES added (if feed/LLM produces variant forms)
☐ Translation code added to TRANSLATION_REGISTRY
☐ New dicts merged into EXTRA_REVERSE_MAPPINGS
☐ python -m pytest api/tests/test_book_names_comprehensive.py → all pass
☐ python -m pytest api/tests/test_verse_parser.py → all pass (add non-English tests)

Frontend
--------
☐ All 66 canonical forms added to LOCALIZED_BOOK_TO_ENGLISH (lowercased)
☐ Citation forms and aliases added to LOCALIZED_BOOK_TO_ENGLISH
☐ npx jest src/lib/verseExtraction.test.ts → all pass (add cross-language tests)

Manual smoke test
-----------------
☐ Ask the LLM: "Quote John 3:16 in [language]" → right-pane verse card appears
☐ Ask the LLM: "Quote 1 Corinthians 13:4 in [language]" → verse card appears
☐ Ask the LLM: "Cite Psalm 23 in [language]" → verse card appears
```

---

## Reference: the Russian bug post-mortem

**What broke:** Russian (Synodal) uses nominative case for book titles ("Иоанн") but genitive
case when citing ("Иоанна 3:16"). The `ENGLISH_TO_RUSSIAN` dict stored nominative forms. When
the LLM cited a verse in Russian, `normalize_book_name("Иоанна")` found no match and returned
the input unchanged, causing a 404 from the backend. Simultaneously, the frontend stored the
localized key in its Set but compared it to the English key from the API — guaranteed never
to match, so verse cards were always hidden.

**The two-layer fix:**

1. **Backend** (`translation_registry.py`): Added `RUSSIAN_CITATION_FORMS` with 18 unambiguous
   genitive forms merged into `EXTRA_REVERSE_MAPPINGS`.
2. **Frontend** (`verseExtraction.ts`): Added `LOCALIZED_BOOK_TO_ENGLISH` table with all
   nominative + genitive Russian forms, plus Chinese and Korean canonical forms.
   `extractVerseReferences()` now normalizes to English before storing in the Set.

**The structural fix** (this refactor): Split the flat `EXTRA_REVERSE_MAPPINGS` into named
`*_CITATION_FORMS` and `*_ALIASES` dicts per language, making it self-evident that inflecting
languages need a companion dict and showing exactly where to add one.

**How the comprehensive tests prevent regression:** 1452 tests (660 round-trip normalize tests
across all 10 languages, 51 alias/citation-form tests, structural integrity checks, and frontend
extraction/matching tests) now run on every PR.
