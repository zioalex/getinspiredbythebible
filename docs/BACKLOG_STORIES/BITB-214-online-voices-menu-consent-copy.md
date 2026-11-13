# BITB-214: Show the Privacy Note When Online Voices Are Enabled From the Menu (Web)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-210 (PR #1190)

## Problem

Switching on "Allow online voices" in `frontend/src/components/MainMenu.tsx` grants consent directly.
It never shows the privacy note that the Listen-button dialog shows. This matches the BITB-210 spec and
the privacy policy covers it, but the two ways in disagree, and the menu path gives no notice. Needs a
product decision.

## Acceptance criteria

- [ ] Decision: open the same consent dialog from the menu toggle, or add a one-line caption under it
- [ ] Implemented in 11 locales; Vitest coverage
