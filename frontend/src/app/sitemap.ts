import type { MetadataRoute } from "next";
import { routing } from "@/i18n/routing";
import { SITE_URL } from "@/lib/seo";
import lastmod from "@/generated/lastmod.json";

// Routes that exist under every locale. Keep in sync with the app router and
// with SOURCES in scripts/generate-lastmod.mjs.
// `/tester` is intentionally omitted: the beta funnel is kept reachable by URL
// but no longer advertised to crawlers now that the official app is published.
const PATHS = ["", "/app", "/about", "/privacy", "/terms", "/changelog"];

// path -> ISO date of the last git commit touching that page (generated at
// build time by scripts/generate-lastmod.mjs). A path with no entry gets no
// <lastmod> at all: an honest omission beats a fake "now" on every URL.
const LASTMOD = lastmod as Record<string, string | undefined>;

export default function sitemap(): MetadataRoute.Sitemap {
  return PATHS.flatMap((path) => {
    const date = LASTMOD[path];
    return routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      ...(date ? { lastModified: new Date(date) } : {}),
      alternates: {
        languages: Object.fromEntries(
          routing.locales.map((l) => [l, `${SITE_URL}/${l}${path}`]),
        ),
      },
    }));
  });
}
