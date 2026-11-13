# BITB-207: Short Answers Grow to the Side Rail's Height (Android)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-205 (PR #1188)

## Problem

`BubbleRow` sizes the row as `max(bubble.height, rail.height)` (`ChatMessageItem.kt` ~line 1172). A
one-line answer is shorter than the three-button rail (~144 dp), so it gets blank space underneath. On
the web the row height comes from the bubble, so the platforms differ.

## Acceptance criteria

- [ ] Product decision recorded: let the rail overflow / lay out horizontally / collapse into a menu
      when the answer is shorter than the rail
- [ ] Android and web behave the same for short answers
- [ ] Compose test covers a one-line answer
