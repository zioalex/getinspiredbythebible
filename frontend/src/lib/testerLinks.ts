/**
 * Links used by the /tester page to recruit Android closed-beta testers.
 *
 * The Android app is in Google Play *closed* testing using a public Google
 * Group as the tester list, so enrollment is self-serve: a visitor joins the
 * group, opts in, then installs from the Play Store. Each URL can be overridden
 * at build time via a NEXT_PUBLIC_* env var (same convention as lib/api.ts);
 * the defaults below are the live production links.
 */
export const TESTER_GROUP_URL =
  process.env.NEXT_PUBLIC_TESTER_GROUP_URL ??
  "https://groups.google.com/g/vox-quieta-closed-test/";

export const TESTER_OPTIN_URL =
  process.env.NEXT_PUBLIC_TESTER_OPTIN_URL ??
  "https://play.google.com/apps/testing/org.voxquieta";

export const PLAY_STORE_URL =
  process.env.NEXT_PUBLIC_PLAY_STORE_URL ??
  "https://play.google.com/store/apps/details?id=org.voxquieta";
