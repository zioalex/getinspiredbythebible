# BITB-200: Self-Harm Fallback — Question-Form and Edge Recall Gaps (hi/zh)

**Status:** Todo
**Size:** S
**Created:** 2026-10-14

Follow-up to BITB-186. Guards added there to avoid Bible-study false positives suppress some
genuine crisis phrasings:

- hi: `मुझे मरना है तो मैं क्या करूँ` (a plea for help, not a question) is missed by the `(?! तो)` guard;
  `मुझे मरना है ?` (space before `?`) and `बस अब मुझे मरना है?` are missed by the `?` guard.
- zh: `我一个人想跳楼` is missed by the `人` lookbehind; `我觉得这样活着没意思吗` is missed by the `吗` guard.
- ru: `мне незачем жить без Бога` now fires (ambiguous faith statement; safe direction, review only).

## Acceptance criteria

- [ ] Each missed phrasing above triggers the compassionate path (parametrized test)
- [ ] BITB-186's Bible-study/negated BENIGN cases stay clean
- [ ] Reviewed by a native speaker or reference list (owner step)
