# BITB-186: Self-Harm Keyword Fallback — Cover Missed Crisis Phrasings and Negations

**Status:** Todo
**Size:** S
**Created:** 2026-10-11

**As a** user in crisis writing in Chinese, Korean, Russian or Hindi, **I want** common
phrasings of distress to be recognised by the keyword fallback, **so that** I get the
compassionate response when ML moderation is down.

## Problem

BITB-183 added phrase-level patterns, deliberately narrow to avoid flagging Bible-study
questions. Independent review found common phrasings still missed and one negated false
positive:

- zh: 我想跳楼, 活着没意思 (and 我想死后一了百了, lost to the 后 lookahead)
- ko: 사라지고 싶어
- ru: Хочу сдохнуть, Мне незачем жить
- hi: मुझे मरना है
- ru false positive: "Я не хочу умереть без покаяния" matches `хочу умереть`

## Acceptance criteria

- [ ] Each missed phrasing triggers `compassionate_response_needed=True` (parametrized test)
- [ ] Negated first-person and Bible-study variants stay clean (parametrized test)
- [ ] Patterns checked by a native speaker or against a reference list per language

## Out of scope

- Script-agnostic matching and violence/self-harm precedence (BITB-185).
