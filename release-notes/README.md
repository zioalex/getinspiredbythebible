# User release notes ("What's new")

What users see after an update, in their own language: the web "What's new" popup, the Android
"What's New" sheet and the Google Play "What's new" field (BITB-175). The developer
`CHANGELOG.md` (release-please) is not shown to users any more.

One folder per release, one file per app language:

```text
release-notes/1.63.0/en.md
release-notes/1.63.0/it.md   … de es fr pt ar ru zh hi ko (all 11)
```

Rules (`python3 scripts/release_notes.py check` enforces them in CI):

- 3–5 lines, each a bullet (a dash and a space), in plain words a user understands: what they can now do, or what
  works again. No story ids (`BITB-…`), PR numbers, code, tool or provider names.
- At most 500 characters per file (the Play Store limit).
- Only `feature` and user-visible `fix` changes; `nfr` only when users notice it ("answers arrive
  faster"), never `chore` or `spike`.

How to write them, and when: `docs/RELEASE_PROCESS.md`, "Writing the user What's New".
A release without a folder shows no popup or sheet; Play gets a generic "Bug fixes and
improvements."
