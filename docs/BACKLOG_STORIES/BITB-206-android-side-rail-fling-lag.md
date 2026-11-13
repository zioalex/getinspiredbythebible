# BITB-206: Android Side Rail Trails One Frame Behind During a Fast Fling

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-205 (PR #1188)

## Problem

`BubbleRow` in `android/.../presentation/components/ChatMessageItem.kt` (~line 1144) records the
row's window Y in `onGloballyPositioned` (~line 1161) and reads it during placement to compute
`stickyRailOffset(...)`. The value read in placement is therefore always the previous frame's position,
so while the rail is pinned it shifts by one scroll step per frame during a fast fling before snapping back.

## Acceptance criteria

- [ ] The rail offset is computed from the row's current coordinates in the placement phase (e.g.
      `Placeable.PlacementScope.coordinates`, if available in the project's Compose BOM) and the
      `itemTop` state is removed
- [ ] Still no recomposition per scroll frame; `StickyRailOffsetTest` and `ListenButtonComposeTest` stay green
- [ ] Verified on a device with a fast fling over a long answer
