import type { MetadataRoute } from "next";

/**
 * Web app manifest (served at `/manifest.webmanifest` via Next's App Router
 * file convention). Enables "Add to Home Screen" installability with a real
 * icon and standalone display, instead of a Safari bookmark.
 *
 * `lang` / `dir` are intentionally omitted. Next's `manifest.ts` convention
 * has no access to the request or the current locale (unlike
 * `generateMetadata`, which receives `params`), and the Web App Manifest spec
 * has no clean per-locale variant mechanism compatible with this app's
 * `[locale]` routing — there is exactly one manifest route shared across all
 * 11 locales, including RTL Arabic. Rather than hardcode `lang: "en"` (wrong
 * for the other 10 locales) or `dir: "ltr"` (wrong for Arabic), we leave both
 * unset so the document's own `<html lang dir>` — set correctly per-locale in
 * `[locale]/layout.tsx` — remains authoritative.
 *
 * `name` / `short_name` use the brand name, which is already language-neutral
 * throughout the app (see `SITE_NAME` in `@/lib/seo`), so no localization
 * decision is needed there. `description` stays a static English fallback:
 * it is not user-visible during normal use of the app (it only surfaces in
 * platform install-prompt UI, and only on some platforms), so the localization
 * gap is low-cost and not worth a per-locale manifest.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vox Quieta",
    short_name: "Vox Quieta",
    description:
      "Scripture-grounded conversations and daily Bible inspiration.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#faf5f0",
    theme_color: "#874a30",
    icons: [
      {
        src: "/icons/icon-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/icons/icon-512.png",
        sizes: "512x512",
        type: "image/png",
      },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
