# BITB-197: Blocked-Response Templates Missing ru/zh/hi/ko

**Status:** 🔍 In Review (2026-10-21)
**Size:** S
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2: only `self_harm_blocked` was localized for ru, zh, hi, ko. The `violence_or_threat`, hate, directed-harm, sexual and generic blocked templates in `api/chat/prompts.py` still lack those four languages and fall back to English.

## Acceptance criteria

- [x] Each blocked template exists in all 11 languages
- [x] Parametrized test asserts every template x language is non-English
- [ ] Native-speaker or reference review recorded
