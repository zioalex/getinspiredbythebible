# BITB-027: Translate Privacy Policy and Terms of Service into All Supported Languages

## User Story

As a non-English speaker using Vox Quieta, I want the Privacy Policy and Terms of Service pages to be available in my own language, so that I can understand what data is collected and what rules govern my use of the App without having to read English legalese.

## Problem

The frontend exposes Privacy Policy and Terms of Service pages at `/{locale}/privacy` and `/{locale}/terms`, and the Android app links to those URLs using a locale segment derived from the device language (`android/app/src/main/kotlin/org/voxquieta/app/utils/LegalUrls.kt`).

However, the underlying markdown documents only exist in English:

```
frontend/public/legal/
├── privacy-policy.md      # English only
└── terms-of-service.md    # English only
```

The loader in `frontend/src/lib/legalDocs.ts` already supports locale-suffixed files (e.g. `privacy-policy.it.md`) and falls back to the base English file when one is missing. As a result, every non-English locale silently serves the English document — even though the surrounding page chrome (titles, labels, last-updated date) is correctly localized through `messages/{locale}.json` under the `Legal` namespace.

This is a compliance and UX issue:

- **GDPR / consumer-protection regulations** generally require that privacy notices be presented in a language the user can reasonably understand. Serving English to users who selected Italian, German, French, etc. weakens that.
- **Trust**: users who opened the page in their language and got an English legal document may assume the App is not seriously localized or that the content does not apply to them.
- **Android in-app links** route to the same web pages, so the issue is visible from both surfaces.

Supported locales (from `frontend/src/i18n/routing.ts` and `LegalUrls.kt`):
`en, it, de, es, fr, pt, ar, ru, zh, hi, ko` — 10 languages need translations.

## Proposed Changes

### 1. Author translated markdown documents

For each non-English locale, add a locale-suffixed file under `frontend/public/legal/`:

```
privacy-policy.it.md     terms-of-service.it.md
privacy-policy.de.md     terms-of-service.de.md
privacy-policy.es.md     terms-of-service.es.md
privacy-policy.fr.md     terms-of-service.fr.md
privacy-policy.pt.md     terms-of-service.pt.md
privacy-policy.ar.md     terms-of-service.ar.md
privacy-policy.ru.md     terms-of-service.ru.md
privacy-policy.zh.md     terms-of-service.zh.md
privacy-policy.hi.md     terms-of-service.hi.md
privacy-policy.ko.md     terms-of-service.ko.md
```

Each file should:

- Preserve the YAML frontmatter (`lastUpdated: YYYY-MM-DD`) so the date matches the English source.
- Translate body text accurately while keeping all URLs, email addresses (`privacy@voxquieta.org`, `legal@voxquieta.org`, `contact@voxquieta.org`), and the MIT/GitHub references unchanged.
- Keep the markdown structure (heading levels, table layout in the Privacy Policy "Third-Party Services" section, the all-caps disclaimer/warranty paragraphs in the Terms).
- For Arabic, ensure the document renders correctly with right-to-left flow when paired with the existing page layout. If page-level RTL handling is missing, file a follow-up.

### 2. Translation source of truth

- The English documents (`privacy-policy.md`, `terms-of-service.md`) remain the canonical version.
- Add a short note at the top of each translation (under the heading) such as: *"This translation is provided for convenience. In case of discrepancy, the English version prevails."* Translate the note itself.
- Decide and document who provides translations:
  - Option A: professional legal-translation service (best for compliance, paid).
  - Option B: native-speaker contributors with a follow-up legal review.
  - Option C: machine translation (DeepL / GPT) with native-speaker proofreading — acceptable for an MVP free app, but each file should still be reviewed by at least one fluent speaker before merging.

### 3. Update `lastUpdated` workflow

- When the English source changes, all translated copies must be updated and their `lastUpdated` bumped. Add a CONTRIBUTING note (or a CI check) that flags translated files whose `lastUpdated` lags behind the English source.

### 4. Tests / verification

- Extend `src/test/legal-pages.test.tsx` to assert that for each supported locale the served document is **not** the English fallback (e.g. by checking for a locale-specific marker phrase) — this prevents regressions where a translated file is accidentally deleted.
- Add a smoke check that `getLegalDocContent("privacy-policy", locale)` returns the locale-specific file for every locale in `routing.locales`.
- Manual QA: open `/{locale}/privacy` and `/{locale}/terms` for each locale and verify the content is rendered in the expected language. Verify the Android app's "Privacy Policy" and "Terms of Service" buttons in Settings open the correct localized page.

## Acceptance Criteria

- [ ] `frontend/public/legal/` contains a `privacy-policy.{locale}.md` and `terms-of-service.{locale}.md` for every non-English locale in `routing.locales`.
- [ ] Each translated file preserves the YAML frontmatter, all URLs, and all email addresses from the English source.
- [ ] Each translated file has been reviewed by at least one fluent speaker of that language (note the reviewer in the PR).
- [ ] Visiting `/{locale}/privacy` and `/{locale}/terms` for each locale shows fully translated content (no English paragraphs leaking through).
- [ ] `legal-pages.test.tsx` includes a per-locale assertion that the rendered document is not the English fallback.
- [ ] The Android Settings "Privacy Policy" / "Terms of Service" buttons open the localized page on a device set to that language.

## Files to Modify / Add

| File | Change |
|---|---|
| `frontend/public/legal/privacy-policy.{locale}.md` (×10) | Add translated Privacy Policy |
| `frontend/public/legal/terms-of-service.{locale}.md` (×10) | Add translated Terms of Service |
| `frontend/src/test/legal-pages.test.tsx` | Per-locale "not-English-fallback" assertion |
| `docs/CONTRIBUTING.md` (or new section) | Note the rule that translated files must be re-synced when the English source changes |

## Out of Scope

- Right-to-left (RTL) layout work for the Arabic Privacy/ToU pages beyond what already exists site-wide. If the current layout doesn't render Arabic well, file a separate UX story.
- Translating other long-form content (e.g. README, in-app help text).
- Backend changes — these documents are static frontend assets.

## Priority

P1 – High (legal/compliance exposure for non-English users; impacts both web and Android surfaces).

## Size

M (4–8 hours of authoring/review work, plus per-language proofreading time which depends on contributor availability).

## Assignee

frontend-expert + per-language reviewers
