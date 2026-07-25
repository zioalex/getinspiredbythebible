import type { MetadataRoute } from "next";
import { routing } from "@/i18n/routing";
import { SITE_URL } from "@/lib/seo";

// Routes that exist under every locale. Keep in sync with the app router.
// `/tester` is intentionally omitted: the beta funnel is kept reachable by URL
// but no longer advertised to crawlers now that the official app is published.
const PATHS = ["", "/app", "/privacy", "/terms", "/changelog"];

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  return PATHS.flatMap((path) =>
    routing.locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      lastModified,
      alternates: {
        languages: Object.fromEntries(
          routing.locales.map((l) => [l, `${SITE_URL}/${l}${path}`]),
        ),
      },
    })),
  );
}
