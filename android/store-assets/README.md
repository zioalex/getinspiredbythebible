# Android Store Assets

This folder contains the working files needed for Google Play Store submission.

Use it as the single place for listing copy, screenshots, exported graphics,
and release metadata for the Android app.

## Folder Layout

```text
android/store-assets/
├── README.md
├── listing-copy.md
├── release-notes-template.md
├── graphics/
│   └── README.md
└── screenshots/
    └── README.md
```

## What Belongs Here

- Draft and approved Play listing copy
- Screenshot plans and exported screenshots
- App icon exports for store submission
- Feature graphic exports
- Release note templates
- Final URLs for privacy policy and terms of service

## What Does Not Belong Here

- Signing keys
- Passwords or secrets
- Raw production credentials
- Very large design source files that should live in a dedicated design system

## Naming Conventions

Use stable, explicit names so assets are easy to version.

Examples:

- `phone-en-01-welcome.png`
- `phone-en-02-chat.png`
- `phone-ar-01-rtl-chat.png`
- `feature-graphic-v1.png`
- `app-icon-play-512.png`

## Minimum Submission Set

Before Play submission, this folder should contain or reference:

- Final short description
- Final full description
- App icon export
- Feature graphic export
- At least 2 phone screenshots
- Public Privacy Policy URL
- Public Terms of Service URL
- Release notes for the uploaded build

## Review Process

Recommended release workflow:

1. Draft copy in `listing-copy.md`.
2. Export graphics into `graphics/`.
3. Export screenshots into `screenshots/`.
4. Check dimensions, spelling, and consistency.
5. Upload the approved assets to Play Console.

## Related Docs

- `docs/ANDROID_PLAY_STORE_ONBOARDING.md`
- `docs/PRIVACY_POLICY.md`
- `docs/TERMS_OF_SERVICE.md`
