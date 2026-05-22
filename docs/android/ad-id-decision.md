# AD_ID permission: decision and resolution

## Decision

The app **declares advertising ID usage** in Play Console with purposes
**App functionality** + **Analytics**. The
`com.google.android.gms.permission.AD_ID` permission ships in the merged
manifest (auto-merged from `play-services-measurement-api`), and Firebase
Analytics' runtime ad-ID collection stays enabled.

The app does **not** show ads, do remarketing, or run an advertising SDK.
The declaration covers Firebase Analytics' use of the ad ID for user-base
analysis (audiences, demographics, retention).

## Required Play Console state

If the upload is rejected with
*"This release includes the `com.google.android.gms.permission.AD_ID`
permission but your declaration on Play Console says your app doesn't use
advertising ID"*, verify all three:

1. **App content → Advertising ID → Manage** → **Yes** + tick *App
   functionality* and *Analytics* → **Save**.
2. **App content → Data safety** → "Device or other IDs → Advertising ID"
   listed with matching purposes → **Save**.
3. **Privacy policy** (store listing) mentions analytics-based ad-ID
   collection.

All three must be saved. The error message is misleading — it can fire
when the form is incomplete even if the visible "answer" looks correct.

## What ships in the AAB

Auto-merged into the release manifest from
`com.google.android.gms:play-services-measurement-api:22.1.2`:

```
<uses-permission android:name="com.google.android.gms.permission.AD_ID" />
<uses-permission android:name="android.permission.ACCESS_ADSERVICES_ATTRIBUTION" />
<uses-permission android:name="android.permission.ACCESS_ADSERVICES_AD_ID" />
```

Only the first one is gated by Play Console's "uses advertising ID"
question. The two `ACCESS_ADSERVICES_*` permissions are Privacy Sandbox
APIs (Android 13+) and are not part of that declaration.

## What we tried first (and why it failed)

| PR | Approach | Result |
|---|---|---|
| #487 | Add `LocalResources` for live language swap (unrelated to AD_ID, but bundled) | Merged |
| #488 | Live language swap via Compose, no Activity recreate | Merged |
| #489 | Strip AD_ID via `tools:node="remove"` in `AndroidManifest.xml` | Upload still failed |
| #490 | Gradle exclude `play-services-ads-identifier` | Wrong module — AD_ID comes from `play-services-measurement-api`, not `ads-identifier`. Reverted. |
| #491 | Revert #489 + #490 | Back to baseline |
| #499 | Re-strip AD_ID + disable runtime collection (`google_analytics_adid_collection_enabled=false`) | Upload still failed with the same error |
| #500 | **Reverse course: declare Yes in Play Console + remove the strip** | Upload succeeds |

The manifest blame report (from the diagnostic workflow at
`.github/workflows/android-debug.yml`) confirmed
`play-services-measurement-api:22.1.2` as the AAR declaring the
permission — see line 14 of `manifest-merger-release-report.txt` in any
debug-dump artifact.

## Future considerations

- If we ever drop Firebase Analytics, switch the Play Console answer back
  to **No** *and* update the privacy policy to match.
- For an in-app GDPR/CCPA opt-out, use `FirebaseAnalytics.setConsent(...)`
  with `ConsentType.AD_PERSONALIZATION` / `AD_USER_DATA`. Don't disable the
  permission at the manifest level — that just creates a mismatch with the
  Console declaration.
- The diagnostic workflow `Android Debug Dump` (manually triggered) emits
  the merged release manifest, dependency tree, and merger blame report.
  Run it whenever a future SDK upgrade introduces a new permission and you
  need to identify the source AAR.
