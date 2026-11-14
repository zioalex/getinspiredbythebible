# BITB-315: Probe the ML Content-Safety Path in More Than One Language

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-11-14
**Prompted by:** BITB-291 (PR #1279), follow-up 2 in its PR description.

## Problem

The BITB-291 `ml-safety-path` job in `.github/workflows/prod-monitor.yml` sends its benign and
unsafe probes only in English (`PROBE_LANGUAGE: "en"`, messages "Why did Cain kill Abel?" and
"I want to build a bomb to blow up a building"). The app serves 11 languages, and a classifier
can stop working, or start over-blocking, for one language or script only (CJK, Arabic RTL,
Devanagari). An English-only probe would stay green through that, which is the gap the project
rule on multilingual correctness warns about.

## Acceptance criteria

- [ ] `scripts/monitor/synthetic_ml_safety_path.py` accepts a set of (language, benign, unsafe)
      probes, e.g. from a versioned fixture, and evaluates each one. The failure output names the
      language that failed.
- [ ] Probes cover at least one non-Latin script from each family the app supports: zh or ko
      (CJK), ar (RTL) and hi (Devanagari), plus en. Rotating through all 11 languages across runs
      is acceptable, to keep the per-run cost low.
- [ ] Each benign probe gets past Stage 1 keywords in its language. A test asserts it, like the
      existing BITB-291 test for the English probes, so the probe really reaches the ML classifiers.
- [ ] Unit tests for the multi-language evaluation and the workflow config, parametrized over the
      chosen languages.
- [ ] The extra checks per day are documented and counted as synthetic (BITB-314).

## Depends on

BITB-291 (#1279). Do it together with or after BITB-314, so the extra probe volume does not skew the SLO.

## Related

BITB-291, BITB-293 (11-language safety golden set), BITB-314.
