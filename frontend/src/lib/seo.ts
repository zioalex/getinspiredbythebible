import type { Metadata } from "next";
import { routing } from "@/i18n/routing";

/**
 * Canonical production origin. Used as the metadataBase (so relative OG /
 * canonical URLs resolve to absolute ones) and by the sitemap / robots routes.
 */
export const SITE_URL = "https://voxquieta.org";

/** Brand name — language-neutral, used in OG siteName and the title template. */
export const SITE_NAME = "Vox Quieta";

/**
 * Build per-page alternates (canonical + hreflang) for a locale-prefixed route.
 *
 * `path` is the route *below* the locale segment, with a leading slash and no
 * trailing slash — "" for the home page, "/privacy" for /‹locale›/privacy.
 * Emitting these per page (rather than once in the layout) keeps each hreflang
 * pointing at the matching translated page instead of every locale's home.
 */
export function buildAlternates(
  locale: string,
  path = "",
): Metadata["alternates"] {
  const languages: Record<string, string> = {};
  for (const l of routing.locales) {
    languages[l] = `/${l}${path}`;
  }
  // x-default tells crawlers which page to serve when no locale matches.
  languages["x-default"] = `/${routing.defaultLocale}${path}`;

  return {
    canonical: `/${locale}${path}`,
    languages,
  };
}

/**
 * Assemble the common metadata block (title, description, canonical/hreflang,
 * Open Graph, Twitter card) for a page. Relative URLs resolve against
 * metadataBase, set once in the root layout.
 */
export function pageMetadata({
  locale,
  path = "",
  title,
  description,
}: {
  locale: string;
  path?: string;
  title: string;
  description: string;
}): Metadata {
  const url = `/${locale}${path}`;
  return {
    title,
    description,
    alternates: buildAlternates(locale, path),
    openGraph: {
      type: "website",
      siteName: SITE_NAME,
      title,
      description,
      url,
      locale,
    },
    twitter: {
      card: "summary",
      title,
      description,
    },
  };
}
