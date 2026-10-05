# BITB-176: Read Aloud — Keep Playing with the Screen Off (Android)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-10-04
**Prompted by:** BITB-119 verification — v1 deliberately stops playback on `ON_STOP` (screen off /
app backgrounded), so the "listen with the display off" use case is not served yet.

## User Story

**As** someone listening to an answer while driving or praying with eyes closed, **I want** the
reading to continue when the screen turns off, **so that** I don't have to keep the phone awake.

## Notes

Requires a foreground service (`FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MEDIA_PLAYBACK`
permissions and Play policy declaration) with a media-session notification exposing Stop.
Gate on BITB-119 listen-rate telemetry (`tts_started`) showing real usage first.

## Acceptance Criteria

- [ ] Playback continues on screen-off/background; a notification with Stop is shown while speaking
- [ ] Stop from the notification, audio-focus loss and starting another answer all stop playback
- [ ] Play Console foreground-service declaration and Data Safety reviewed
- [ ] Robolectric tests for the service lifecycle; manual real-device pass
