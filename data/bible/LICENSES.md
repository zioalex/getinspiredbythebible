# Committed Bible Data — Provenance & Licenses

Most translations are fetched at seed time from getBible (`https://api.getbible.net/`) and
are not committed to this repo. The translations below have `source: "manual"` in
`scripts/translations.py` because no such live API serves them, so their text is committed
directly under `data/bible/translations/`.

## luther1912.json — Luther 1912 (German)

- **Source:** Unbound Bible, via the Bible SuperSearch JSON collection.
- **License:** Public Domain.
- **Added:** BITB-046 (`#851`).

## hindi.json — Hindi IRV (इंडियन रिवाइज्ड वर्जन)

- **Source:** [eBible.org](https://ebible.org/find/details.php?id=hin2017), file `hin2017_usfx.zip`
  ("Hindi Indian Revised Version Bible", eBible short code `hin2017`), listed under eBible's
  "Open Access License Bibles".
- **Translation by:** Bridge Connectivity Solutions Pvt. Ltd.
- **Copyright:** © 2017, 2018, 2019 Bridge Connectivity Solutions.
- **License:** Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0). Sharing,
  redistribution, and reasonable revisions/adaptations are permitted provided the copyright
  and source above are retained, changes are indicated, and redistributions use the same
  license.
- **Conversion:** Downloaded as USFX XML (66 books, no deuterocanon) and normalized to the
  loader's `[{"name": "<English book name>", "chapters": [[verse, ...], ...]}]` shape.
  Footnotes (`<f>`), cross-references (`<x>`, `<bdit>`), and other apparatus were stripped;
  only the running verse text was kept. 31,104 verses across 66 books.
- **Added:** Investigation started as an incident report (Hindi missing from the DB — it had
  never actually loaded, since `source: "manual"`/`url: None` with no committed file means
  `load_bible.py` always loads zero verses for it). See
  `api/tests/test_translations.py::test_manual_source_translations_have_committed_data_file`.
