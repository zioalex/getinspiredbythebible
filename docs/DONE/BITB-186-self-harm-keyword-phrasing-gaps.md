# BITB-186: Self-Harm Keyword Fallback — Cover Missed Crisis Phrasings and Negations

**Status:** ✅ Done — PR #1169 merged 2026-10-14 (native-speaker review AC left open)
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

- [x] Each missed phrasing triggers `compassionate_response_needed=True` (parametrized test)
- [x] Negated first-person and Bible-study variants stay clean (parametrized test)
- [ ] Patterns checked by a native speaker or against a reference list per language

## Out of scope

- Script-agnostic matching and violence/self-harm precedence (BITB-185).

## Implementation notes

- Patterns added in `api/utils/security.py` (ru/zh/hi/ko); zh `想死`/`想去死`/`想要死` now allow `后`/`後` when followed by `一了百了`; ru `хочу умереть` / `хочется умереть` carry a `(?<!\bне )` guard.
- Tests: `api/tests/test_self_harm_keyword_fallback_languages.py` (CRISIS + BENIGN additions).
- The native-speaker review AC stays unticked (owner step).
- Accepted limitation: the ru `не` guard is a fixed-width lookbehind, so a double space (`не  хочу умереть`) or an intervening word (`не очень хочу умереть`) still matches; this errs toward the compassionate path.
- Review round 2: ko `사라지고 싶지 않` negation, zh `想跳楼` / `活着没意思` third-person and question guards, ru `незачем жить во/в...` guard, hi `क्या`/`अगर`/`तो`/`?` guards.
- Accepted limitations (round 3): hi/zh question-form suppression (`क्या मुझे मरना है?`, `...活着没意思吗`) can miss a rhetorical crisis question; `一个人想跳楼` is missed by the 人 guard; quoted Bible speech that matches a crisis phrase fires, which is the safe direction. The ru `незачем жить` exclusion is deliberately narrow (`во грехе/страхе`, `ради денег`, `для себя`); other continuations (`без тебя`, `в одиночестве`) stay crisis.
