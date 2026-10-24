# BITB-217: Android — Offer Network Voices per Device When No Offline Voice Exists

**Status:** 🎯 Todo
**Priority:** P3
**Size:** M
**Created:** 2026-10-22
**Follow-up of:** BITB-210 (PR #1190), which did this for web only

## Problem

On Android, `AndroidSpeechEngine` (`android/.../tts/SpeechEngine.kt`) uses only voices with
`isNetworkConnectionRequired == false`. On a device with no offline voice for the UI language, Listen
stays hidden, and nothing tells the user why. The web now explains this and offers a per-device opt-in
to online voices (BITB-210); the Android app does neither.

## Acceptance criteria

- [ ] Same three states as web: local / network-only / none
- [ ] Network-only: a one-time consent dialog with the same privacy wording as the web. The choice is
      stored in DataStore and can be changed in Settings
- [ ] None: Settings explains that no voice is installed, with a link to the system TTS settings
- [ ] Strings in all 11 locales; ViewModel and Compose tests
