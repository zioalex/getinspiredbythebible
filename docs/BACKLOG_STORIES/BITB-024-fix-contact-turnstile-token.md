# BITB-024: Fix Contact Form Turnstile Token Expiry

## User Story

As a user, I want to submit the contact form so that I can report bugs and request features.

## Problem

When the user taps "Get in Touch" in Settings and submits the contact form, the request fails with a 403 error because the Turnstile token has expired or was already consumed by a previous API call.

## Root Cause

`ContactRepositoryImpl.submitContact()` doesn't call `TurnstileManager.onTokenConsumed()` after the API call. The Turnstile token is single-use, so after being consumed by a chat message, subsequent contact submissions fail.

## Acceptance Criteria

- [ ] User can successfully submit contact form from Settings screen
- [ ] Turnstile token is refreshed before each contact submission
- [ ] Error message shown if contact submission fails

## Technical Details

- File: `android/app/src/main/kotlin/com/bibleinspiration/data/repositories/ContactRepositoryImpl.kt`
- Related: `TurnstileManager.kt`, `TurnstileInterceptor.kt`

## Priority

High - Users cannot report bugs or request features

## Assignee

android-expert
