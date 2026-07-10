# BITB-068: Refresh & Expand Bible Translations from Bible SuperSearch

**Status:** 📋 Backlog
**Priority:** P2 (Medium) — content/coverage enhancement; several languages ship only one century-old version
**Size:** M (1-2 days, mostly data loading + registration)
**Created:** 2026-07-10
**Source:** Product owner request + Bible SuperSearch JSON collection —
`https://sourceforge.net/projects/biblesuper/files/All%20Bibles%20-%20JSON/`

## User Story

**As a** reader, **I want** access to additional and more current Bible translations — starting with
Italian — **so that** I can read Scripture in wording that feels closer to modern language and compare
translations, without being limited to a single century-old version per language.

## Problem / Motivation

The app ships 14 translations (seeded in `scripts/init.sql`, configured in `scripts/translations.py`,
surfaced via `api/utils/language.py`), and most are century-old public-domain texts — Riveduta 1927
(it), Luther 1912 (de), Schlachter 1951 (de), Elberfelder 1871 (de), Reina Valera 1909 (es), Louis
Segond 1910 (fr). Several languages offer only **one**, dated option, so readers cannot compare or read
in more contemporary phrasing.

The product owner found the **Bible SuperSearch** JSON collection (~54 translations across 40+
languages, organized as `<lang-code>/<version>.json`). It can add somewhat newer public-domain options:
**Diodati** (it), **Reina Valera 2010** (es), **Ostervald 1996** / **La Bible de l'Épée 2005** (fr),
**NET Bible** (en), plus alternates (Geneva, ASV, Martin 1744, etc.).

**Licensing constraint (important):** Bible SuperSearch states its files are "legally shareable for
non-commercial purposes; please see the copyright statement on each Bible." Truly modern translations
(NIV, ESV, Italian CEI 2008, Luther 2017) remain **copyrighted** and **cannot** be redistributed in
this repo/DB. "More current" is therefore bounded by what is public-domain / freely redistributable —
each candidate must be license-checked before import. This story deliberately scopes to freely
redistributable texts only.

## Acceptance Criteria

- [ ] Evaluate the Bible SuperSearch collection and select candidate translations that are
      **public-domain / freely redistributable** — verify the per-Bible copyright note; explicitly
      **exclude** copyrighted modern texts (NIV, ESV, CEI 2008, Luther 2017, etc.).
- [ ] **Italian prioritized:** add at least one additional Italian option (e.g. **Diodati**) alongside
      the existing Riveduta 1927, so the Italian picker offers more than one version.
- [ ] Add newer public-domain options for other languages where clearly free: **Reina Valera 2010**
      (es), **Ostervald 1996** / **La Bible de l'Épée 2005** (fr), **NET Bible** (en, per its
      distribution terms).
- [ ] Each new translation is imported via `scripts/load_bible.py` and registered end-to-end (see the
      "add a translation" checklist below), so it appears in `GET /scripture/translations` and is
      selectable in the frontend translation picker.
- [ ] Verse text **and** embeddings are loaded and searchable for each new translation.
- [ ] Book-name mapping is complete for each new translation — run
      `scripts/audit_book_name_coverage.py` with no regressions in
      `docs/audits/book-name-coverage.md`.
- [ ] A short provenance/license note (e.g. `data/bible/LICENSES.md`) records the source and license
      basis for each added text.
- [ ] Existing translations and per-language defaults are unchanged; all tests pass.

## Proposed Translations (candidates — confirm license before importing)

| Language | Candidate to add | Notes |
|---|---|---|
| Italian (it) | **Diodati (1649)** | Second Italian option alongside Riveduta 1927; classic public-domain. Investigate any newer freely-licensed Italian text if one exists. |
| Spanish (es) | **Reina Valera 2010** | Newer than the shipped RV 1909; confirm redistribution terms. |
| French (fr) | **Ostervald 1996** / **La Bible de l'Épée 2005** | Newer than Louis Segond 1910; confirm terms. |
| English (en) | **NET Bible** | Modern English; import per NET's stated distribution terms. |
| (optional) | Geneva, ASV, Martin 1744, Bishops | Alternates already partly covered elsewhere; add only if they add value. |

## Implementation Notes (gathered during exploration)

- **New source format.** The Bible SuperSearch JSON shape is a new source format.
  `scripts/load_bible.py` → `normalize_bible_data()` (~line 163) currently normalizes only the
  `thiagobodruk` and `getbible` shapes; add a `biblesuper` normalizer branch and a
  `source="biblesuper"` entry in the `TRANSLATIONS` dict in `scripts/translations.py` (~line 206).
  Where the same text already exists on getBible, prefer reusing the existing getBible path instead of
  a new format.
- **"Add a translation" checklist** (headers of `api/utils/translation_registry.py` lines 7-38 and
  `scripts/translations.py` lines 9-78) touches a known set of files:
  - `scripts/translations.py` — translation metadata + source/URL
  - `scripts/init.sql` — `translations` seed row
  - `api/utils/language.py` — `LANGUAGE_TRANSLATIONS`, `TRANSLATION_INFO`
  - `api/utils/translation_registry.py` — book-name dicts (only if a **new language** is introduced;
    all target languages here already exist)
  - frontend i18n files (translation picker labels)
  - `api/chat/prompts.py`
- **Runtime shape unaffected.** Verses land in Postgres `verses` (discriminated by the `translation`
  column) and are served by `api/scripture/repository.py` / `api/routes/scripture.py`. No API-shape
  change.
- **Sizing caveat.** Embeddings are generated per verse (`scripts/create_embeddings.py`, 1024-dim
  Ollama / `create_azure_embeddings.py`, 1536-dim Azure). Each new full translation is ~31k verses, so
  every added translation carries an embedding-generation cost — budget for it.

## Out of Scope

- Copyrighted modern translations (NIV, ESV, CEI 2008, Luther 2017, Einheitsübersetzung, NGÜ).
- Redesign of the translation picker UI.
- Changing the default translation for any language.

## Related

- `docs/BACKLOG_STORIES/BITB-046-german-translations-luther-elberfelder.md` — prior "add translations"
  story (same infrastructure and checklist).
- Existing translation infrastructure: `scripts/translations.py`, `scripts/load_bible.py`,
  `api/utils/translation_registry.py`, `api/utils/language.py`.
- `MULTILINGUAL_PROGRESS.md` — multilingual rollout context.
