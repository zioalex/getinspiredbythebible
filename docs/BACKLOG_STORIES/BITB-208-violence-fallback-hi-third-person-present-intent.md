# BITB-208: Hindi Present-Tense Third-Person Intent Blocked (शैतान हमें मारना चाहता है)

**Status:** 🎯 Todo
**Size:** S
**Created:** 2026-10-18

Deferred from BITB-198 verification. The hi intent pattern `मारना चाहता/चाहती/चाहते` is not restricted to first person, so Bible questions such as `शैतान हमें मारना चाहता है` or `हेरोदेस यीशु को मारना चाहता है` are blocked in the fallback. Past tense (`था/थी/थे`) is already excluded.

## Acceptance criteria

- [ ] Decide how to distinguish first-person intent from third-person narrative in hi
- [ ] Third-person present examples clean; `मैं उसे मारना चाहता हूँ` still blocked
- [ ] Parametrized tests
