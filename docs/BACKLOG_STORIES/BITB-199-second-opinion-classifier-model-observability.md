# BITB-199: Second-Opinion Classifier Uses the Primary Model Only

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2: the classifier calls the primary `LLM_PROVIDER` model with `max_tokens=16`. A reasoning model may spend the budget on thinking and return no parseable label, which always degrades to the crisis block. Consider a dedicated small model setting, a fallback chain, and observability (unparseable rate alert).

## Acceptance criteria

- [ ] Choice of classifier model documented/configurable
- [ ] Unparseable/timeout/error rate visible on a dashboard or alert
- [ ] Test with a reasoning-style empty response keeps the crisis block
