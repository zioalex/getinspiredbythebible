# BITB-196: Murder-Suicide Elliptical Phrasing Takes the Compassionate Path

**Status:** 🎯 Todo
**Size:** M
**Created:** 2026-10-13

## Problem

Follow-up to BITB-185 v2: "I want to kill myself and my family", "...and take everyone with me" and the fr/pt/ar equivalents match a self-harm span, and the remaining words ("my family", "everyone") are not violence keywords, so the fallback takes the compassionate path without consulting the classifier. Decide whether to route these to the ambiguity branch (classifier plus crisis default) and implement it.

## Acceptance criteria

- [ ] Decision recorded: route murder-suicide phrasing to the ambiguous branch (or document why not)
- [ ] Elliptical phrasings blocked or classified in all 11 languages (parametrized)
- [ ] Plain self-harm ("I want to kill myself") stays compassionate without an LLM call

## Note (from BITB-185 v2 verification)

Optionally also refuse a SELF_HARM override when a third-party target follows a method word
(`kill|murder|shoot` + `my|his|her|them|everyone|people`). Verifier examples: "kill myself and
kill my wife", "get a gun to shoot my coworkers".
