# Play Console Compliance Checklist

Google Play policy updates (announced periodically at [Play Console → Policy
→ Announcements](https://play.google.com/console) and summarized in emails to
the developer account) often require two kinds of follow-up: a **code**
change (privacy policy text, SDK target level, permission usage — tracked as
normal PRs) and a **Play Console** change (form fields only a human with
Console access can update). This doc tracks the Console-only half, which
otherwise has no home in the repo and is easy to lose track of once the
corresponding PR merges.

For the one-time initial app setup (creating the app, store listing, service
account), see [`android/README.md` → Publishing to the Play
Store](../../android/README.md#publishing-to-the-play-store). This doc is for
recurring policy-driven updates to an already-published app.

## Open items — July 2026 policy update

Google's July 15, 2026 policy announcement required both a code and a Console
response. The code side shipped as:

- PR #900 — privacy policy discloses third-party AI processing (OpenRouter,
  Azure OpenAI)
- PR #901 — targetSdk/compileSdk bumped to 36 (deadline 2026-08-31)

The following Console-only items are **not done by either PR** and need a
human with Play Console access:

- [x] **Data safety form** (Play Console → App content → Data safety):
  update to reflect that chat message text is shared with third-party AI
  processors (OpenRouter, Azure OpenAI) for the purpose of generating and
  safety-screening responses. Confirm the "Location" section still correctly
  states no location data is collected.
- [x] **Content rating questionnaire** (Play Console → App content → Content
  rating): re-confirm the IARC questionnaire is complete. Google's July 2026
  update states unrated apps are no longer allowed on Play.
- [x] **App registration / developer verification** (Play Console → Home):
  confirm this app shows as registered. Google auto-registered ~99% of
  existing apps, but unregistered apps risk removal from Play.

None of these require touching the codebase — do them directly in Play
Console. Once complete, check the boxes above by editing this file in a
follow-up commit (or link the resolving PR/commit here).

## General checklist for future policy announcements

When a new Google Play policy announcement arrives, work through this list
before considering the update "handled":

1. **Read the announcement in full** (usually emailed to the developer
   account, or in [Play Console → Policy →
   Announcements](https://play.google.com/console)). Note the effective date
   and any compliance deadline.
2. **Triage each item against this app**: Vox Quieta requests only
   `INTERNET` + `ACCESS_NETWORK_STATE`, has no accounts/login, no location
   collection, and chat is user↔AI (not user↔user). Most policy changes
   aimed at permissions (SMS/call log, location), account/age-restricted
   content, or ads don't apply — confirm against `android/app/src/main/AndroidManifest.xml`
   and `android/app/build.gradle.kts` (targetSdk) rather than assuming.
3. **Split code vs. Console work**:
   - Code: privacy policy text (`frontend/public/legal/privacy-policy*.md`),
     targetSdk/compileSdk (`android/app/build.gradle.kts`,
     `android/gradle/libs.versions.toml`), manifest permissions.
   - Console: Data safety form, content rating, app content declarations,
     Advertising ID declaration (see [`ad-id-decision.md`](ad-id-decision.md)
     for the precedent and the Data-safety/AD_ID coupling), Policy status.
4. **Ship code changes as normal PRs**, each linking back to the policy
   announcement and stating its deadline.
5. **Track Console-only items in this file** under a new dated section (like
   "Open items — July 2026 policy update" above), with checkboxes, so they
   survive after the code PRs merge and aren't only visible in a closed PR
   description.
6. **Check off and archive** once done — move the dated section below into a
   "Resolved" log (create one once the first section is checked off) rather
   than deleting it, so there's a paper trail of what Console changes were
   made and when.
