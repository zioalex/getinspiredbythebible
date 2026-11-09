# BITB-281: pt Directed Harm — "Que você morra para o pecado, seu idiota" No Longer Blocks

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-11-09

## Problem

Follow-up to BITB-239 (#1261). The die-to-sin lookahead on `que você/tu morra` exempts "Que você morra para o pecado",
but the same clause followed by an insult ("…, seu idiota") now passes Stage 1, whereas it blocked before BITB-239.
Italian is covered by a `muoia … <insult>` tail pattern; Portuguese has no equivalent. Stage 2 ML still catches it when up.

## Acceptance criteria

- [ ] pt die-to-sin wording followed by an insult blocks; plain die-to-sin wording stays allowed
- [ ] Parametrized across the 11 language codes
