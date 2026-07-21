# BITB-053: Modern Open-Licensed Bible Translations Research (DBS / SWORD / unfoldingWord)

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — content freshness across all languages
**Size:** L (research + per-locale shortlist; spawns follow-up loading stories)
**Created:** 2026-06-17
**Source:** Product request — "offer more recent versions in all languages, starting from DBS / SWORD / unfoldingWord"

## User Story

**As a** reader in any supported language,
**I want** a *modern, readable* translation (not only century-old public-domain texts like
KJV or Luther 1912),
**so that** scripture feels current and natural to read.

## Problem

Most current translations integrated today are old public-domain editions. The genuinely
modern, well-known translations (NIV, ESV, Luther 2017, Einheitsübersetzung, …) are
**copyrighted** and cannot be embedded without a licence — the same conclusion reached in
BITB-046. The realistic path to "more recent" text is **open-licensed** modern translations.
This story researches three starting sources and produces a prioritized, license-verified
adoption shortlist that reuses the existing translation pipeline.

## The Three Sources — Redistributability Reality

| Source | What it is | Redistributability reality |
|---|---|---|
| **unfoldingWord** (Door43, `git.door43.org`) | ULT / UST — modern, **CC BY-SA 4.0**, in USFM / USX / HTML / plain text | **Strongest fit.** Genuinely open *and* modern. English ULT is a modern update of the ASV; Gateway-language texts exist for several of our locales. Obligations: visible **attribution** + **ShareAlike** (affects how we present/serve the text — ties to BITB-029). |
| **SWORD / CrossWire** (`ftp.crosswire.org/pub/sword/raw/`; plus the Kahunapule / eBible.org repo, 1200+ modules in 600+ languages) | GPL *software* + a large module catalogue; each module's text license varies | **Per-module license check required** — every module's `.conf` declares `DistributionLicense` / `TextSource`. Many are the same public-domain texts we already use; a subset are CC / PD moderns worth adding. |
| **DBS — Digital Bible Society** (`dbs.org`, `library.bible`, GitHub `digitalbiblesociety`) | Aggregator, 1000+ languages, offline "Bible" & "Treasures" libraries | **Discovery catalogue, not a blanket license.** "Treasures" libraries carry regional / no-sale restrictions; much of the underlying text is third-party licensed (e.g. FCBH audio). Use to *find* candidate texts, then verify each text's license **at its original source** before adoption. |

### Key caveats to carry into the shortlist

- **Copyright wall stands:** modern brand-name translations remain out of scope (BITB-046).
- **CC BY-SA implications:** we embed verses for semantic search and serve text via API.
  ShareAlike + attribution requirements must be satisfiable before adopting unfoldingWord
  text — this makes **BITB-029 (surface Bible version info / attribution)** a companion
  prerequisite, not a nice-to-have.
- **No double-counting:** skip any module/text that duplicates a translation already loaded.

## Approach

Produce a research document (this story's deliverable) that:

1. Catalogues, per source, which texts are *modern* **and** *redistributable*.
2. Builds a **per-locale adoption shortlist** for all current languages:
   en, it, es, fr, pt, de, ru, zh, hi, ko, ar.
3. Recommends a **phase-1 set** to adopt first (English ULT/UST is the clear lead candidate),
   and files one BITB-046-style follow-up implementation story per adopted translation.

### Per-locale shortlist template (to fill during research)

| Locale | Modern open option? | Candidate (code / source URL) | License | Confidence |
|---|---|---|---|---|
| en | ✅ | unfoldingWord ULT / UST (Door43) | CC BY-SA 4.0 | High |
| it | ? | (SWORD/eBible.org module or uW GL — verify) | verify | — |
| es | ? | (SWORD/eBible.org module or uW GL — verify) | verify | — |
| fr | ? | … | verify | — |
| pt | ? | … | verify | — |
| de | ? | (already covered by BITB-046; check uW GL) | verify | — |
| ru | ? | … | verify | — |
| zh | ? | … | verify | — |
| hi | ? | … | verify | — |
| ko | ? | … | verify | — |
| ar | ? | … | verify | — |

## Integration Path (reuse existing pipeline — no new architecture)

Adopting any chosen translation follows the **11-point checklist documented at the top of
`scripts/translations.py`**, exactly as BITB-046 did:

1. Register the translation in `scripts/translations.py` (reuse existing book-name maps).
2. Seed `scripts/init.sql` with INSERT rows.
3. Wire `api/utils/language.py` — `LANGUAGE_TRANSLATIONS[<locale>]` + `TRANSLATION_INFO`.
4. Map book names in `api/utils/translation_registry.py` (the single source of truth) and
   register in `api/utils/book_names.py` — never hardcode names (AGENTS.md pitfall #4).
5. Operator-load via `python scripts/load_bible.py --translation <code>` (post-merge).

**One genuine code addition for unfoldingWord:** `scripts/load_bible.py` currently ingests
**JSON** (getBible / scrollmapper). unfoldingWord ships **USFM/USX**, so adopting it needs a
**format adapter** in the loader. This becomes its own follow-up story — call it out explicitly;
SWORD/eBible.org modules that are already mirrored as JSON avoid this.

## Acceptance Criteria

- [ ] Research doc includes the **per-source redistributability table** (above), with each
      claim backed by a source URL.
- [ ] **Per-locale shortlist** completed for all 11 languages, each candidate carrying a
      **verified license** and **source URL** (or an explicit "no open modern option found").
- [ ] A recommended **phase-1 adoption set** is stated (English ULT/UST first).
- [ ] **Follow-up implementation stories filed** (one per adopted translation, BITB-046 style),
      plus a loader-USFM-adapter story if unfoldingWord is in phase 1.
- [ ] Doc cross-links BITB-046 and BITB-029 so it reads as *additive*, not duplicative.

## Implementation Notes

- This is a **research/spike** story: it does not load or embed any translation. Loading is an
  operator + infra step carried by the per-translation follow-ups.
- Verify exact module/translation codes against each source's manifest before quoting them
  (getBible manifest, Door43 repo, CrossWire `.conf`).
- Per translation: ~31k verses + embeddings, 30–60 min to load depending on embedding provider
  (see BITB-046).

## Testing

Documentation-only story — no automated tests. Verification = every cited source URL and
license claim resolves, and each shortlisted candidate's license permits embedding + API serving.

## Related

- **BITB-046** (German public-domain translations) — same copyright reasoning + loading pattern.
- **BITB-029** (surface Bible version info) — needed to satisfy CC BY-SA attribution.
- `docs/archive/MULTILINGUAL_PROGRESS.md`, `multiple_embeddings/BIBLE_EMBEDDING_PLAN.md` — embedding rollout.
- The 11-point checklist at the top of `scripts/translations.py`.
- Multi-Language / Translation System section in `AGENTS.md`.

## Sources

- unfoldingWord content & licensing: <https://unfoldingword.org/for-translators/content/>,
  Door43 repos <https://git.door43.org/unfoldingWord/en_ult>
- SWORD / CrossWire module repos & licensing:
  <https://wiki.crosswire.org/Official_and_Affiliated_Module_Repositories>,
  <https://www.crosswire.org/sword/about/license.jsp>
- Digital Bible Society: <https://dbs.org/>, <https://dbs.org/libraries>,
  <https://github.com/digitalbiblesociety>
- Cross-source data sets overview: <https://get.bible/bible-data-sets/>
