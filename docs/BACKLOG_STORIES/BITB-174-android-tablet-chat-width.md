# BITB-174: Android Tablet — Chat Messages Don't Fill the Available Width

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** S
**Created:** 2026-10-03
**Type:** Bug (Android)

## User Story

**As** a user running the Android app on a tablet, **I want** the chat conversation
to use the available screen width in both portrait and landscape, **so that** answers
are not squeezed into a narrow strip with large empty areas beside them.

## Bug Report

Reported 2026-10-03: on a tablet, in **both portrait and landscape**, the main
central chat window does not fill the available space.

## Root Cause

`ChatMessageItem.kt` wraps every message bubble (user and assistant) in
`Modifier.widthIn(max = 320.dp)`. That cap was sized for phones (360–411dp wide);
on a tablet (~600–900dp portrait, ~960–1340dp landscape) messages stay at 320dp,
leaving most of the screen empty. The surrounding `ChatScreen` Scaffold /
`LazyColumn` already fill the screen — the constraint is purely the bubble cap.
(BITB-122 enabled tablets via minSdk 24 but never adapted the layout.)

## Decision (agreed with the reporter)

**Adaptive bubbles:** a bubble may take ~85% of the available row width, never less
than the old 320dp (so phones look unchanged), and never more than a readable
840dp cap on very wide landscape screens. Bubbles keep their start/end alignment.

## Requirements (spec)

**Functional**

- FR1: On tablets, chat bubbles (user and assistant) use the available width in
  portrait and in landscape.
- FR2: Phone layout stays visually the same (bubble cap 320dp).
- FR3: On very wide screens, bubbles are capped at a readable 840dp, and keep
  their start (assistant) / end (user) alignment.

**Non-functional**

- Platform: native Android app only (confirmed by the reporter); the web frontend
  is out of scope.
- Language-agnostic: the layout depends only on width, so it applies to all 11
  locales, including RTL Arabic (start/end alignment mirrors automatically).
- No change to scrolling, streaming or bottom-sheet behaviour.

**Open questions:** none. A two-pane tablet layout is a possible follow-up.

## Acceptance Criteria

- [ ] Bubble max width is computed from the available width by a pure function
      (`bubbleMaxWidth(available: Dp): Dp`) — no hardcoded 320dp cap
- [ ] Phone widths (≤ ~411dp) render as before (max = 320dp, or the available
      width if narrower)
- [ ] Tablet portrait (e.g. 800dp) bubbles are wider than 320dp
- [ ] Tablet landscape (e.g. 1280dp) bubbles are capped at 840dp
- [ ] JVM unit tests cover the function across phone / tablet portrait / tablet
      landscape / narrow edge cases
- [ ] Robolectric Compose test at tablet qualifiers proves a long assistant message
      renders wider than 320dp
- [ ] Android unit tests, Compose tests and lint pass
- [ ] PR merged

## Out of Scope

- Two-pane / permanent navigation drawer layouts for tablets (possible follow-up)
- Web frontend (reporter confirmed the issue is in the native Android app)
