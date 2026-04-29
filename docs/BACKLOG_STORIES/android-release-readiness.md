# Android App Release Readiness Backlog

## Critical Issues (Must Fix)

### 1. Verse Links - Open Entire Chapter

- **Status**: Not working
- **Description**: Bible verse references in chat messages are not tappable links that open the entire Bible book chapter (like web app)
- **Files**: ChatMessageItem.kt, VerseDetailBottomSheet.kt
- **Priority**: HIGH

### 2. Colors Don't Match Web App

- **Status**: Needs verification
- **Description**: UI colors (primary, background, text) differ from web frontend
- **Files**: Theme.kt, ChatMessageItem.kt
- **Priority**: HIGH

### 3. Language Selection Redundancy in Settings

- **Status**: Needs removal
- **Description**: Language dropdown in Settings should be removed (language icon in entry page is sufficient)
- **Files**: SettingsScreen.kt
- **Priority**: HIGH

### 4. Missing Bible Version Link Button

- **Status**: Missing
- **Description**: Web app has a translation selector button that's not present in Android
- **Files**: ChatScreen.kt, SettingsScreen.kt
- **Priority**: HIGH

## App Improvements (Nice to Have)

### 5. Test Coverage Expansion

- **Status**: Needs improvement
- **Description**: Add more unit tests and instrumented tests for critical paths
- **Files**: android/app/src/test/, android/app/src/androidTest/
- **Priority**: MEDIUM

### 6. Crash Reporting (Firebase Crashlytics)

- **Status**: Not integrated
- **Description**: Add Firebase Crashlytics for production crash reporting
- **Priority**: MEDIUM

### 7. Analytics (Firebase Analytics)

- **Status**: Not integrated
- **Description**: Add Firebase Analytics for usage tracking
- **Priority**: MEDIUM

### 8. Splash Screen

- **Status**: Not implemented
- **Description**: Add launch screen for better UX
- **Priority**: LOW

### 9. App Icons (PNG)

- **Status**: Using XML vectors
- **Description**: Generate proper PNG icons for all densities
- **Priority**: LOW

### 10. Play Store Assets

- **Status**: Not created
- **Description**: Screenshots, feature graphic, privacy policy URL
- **Priority**: LOW

---

## Implementation Notes

### Verse Links Implementation

- Check how web app handles verse references: extract verse references from response, make tappable, open ChapterModal
- Android: VerseDetailBottomSheet already has chapter loading, need to make verse chips clickable in ChatMessageItem

### Colors Implementation

- Compare Theme.kt colors with web app's CSS variables
- Web uses: primary #4A6FA5, parchment background #F8F5F0, etc.

### Bible Version Button

- Web has translation selector (dropdown showing available Bible versions)
- Android needs similar selector in chat UI or settings

### Test Coverage Focus Areas

- ChatViewModel (send message, streaming, error handling)
- VerseDetailBottomSheet (chapter loading)
- Language selection flow
- Theme switching
