# BITB-216: Watch for a Visible "Verses Cited" List Being Read Aloud (Web + Android)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-211 (PR #1190)

## Problem

BITB-211 stopped both readers from speaking the hidden `<!-- VERSES: … -->` marker. If the model ever
ends an answer with a *visible* reference list (a heading such as "Verses cited:" followed by bare
references), that list would still be read. The prompt asks for flowing prose, and no such list has been
observed so far.

## Acceptance criteria

- [ ] Check recent production answers in all 11 languages for trailing reference-only lists
- [ ] If found: a shared fixture rule (and parity test) that drops a trailing block made only of verse
      references, plus a prompt fix; otherwise close this as not needed
