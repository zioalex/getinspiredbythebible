# BITB-025: Verify and Fix Verse Linking in Android Chat

## User Story

As a user, I want to tap on Bible verse references in chat messages to see the full chapter, so I can read the complete context.

## Problem

Verse references in chat messages are not being rendered as clickable links in the Android app, or the tap handler is not working correctly.

## Root Cause Analysis

The Android app uses `injectVerseLinks()` to convert verse references to markdown links with `verse://` scheme, and `MarkdownText` library to render them. The web app uses a custom `highlightText()` function that creates clickable `<span>` elements.

## Current Implementation (Android)

- `injectVerseLinks()` converts "John 3:16" → `[John 3:16](verse://John/3/16)`
- `MarkdownText` component renders the markdown
- `onLinkClicked` callback should trigger `parseVerseLink()` and open chapter sheet

## Acceptance Criteria

- [ ] Verse references like "John 3:16" are visually highlighted (amber color)
- [ ] Tapping a verse reference opens the chapter sheet
- [ ] User can scroll through verses in the chapter sheet
- [ ] Behavior matches the web app (which has working verse linking)

## Technical Details

- Files to check:
  - `ChatMessageItem.kt` - Verse linking injection
  - `MarkdownText` library configuration
  - `ChapterSheetState` handling

## Comparison with Web App

The web app uses:

- `highlightText()` function to create `<span>` elements
- Regex pattern that handles multi-language book names
- `onClick={handleTextClick}` on verse spans

## Priority

High - Core user experience feature

## Assignee

android-expert
