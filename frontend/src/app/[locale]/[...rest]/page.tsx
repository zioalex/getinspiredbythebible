import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

// Catch-all for unmatched paths under a locale (e.g. /ar/__x404). Without it,
// Next renders its built-in English 404 *outside* the locale layout; calling
// notFound() here renders the localized [locale]/not-found.tsx instead, with
// a 404 status. The 404 shell actually takes its <title>/canonical from
// not-found.tsx generateMetadata (this one is not applied to the notFound()
// render). Note: the SSR HTML for a 404 is Next's `__next_error__` shell;
// the localized text only arrives via the RSC payload / client render, so the
// initial server HTML does not carry the correct <html lang/dir> (tracked in
// BITB-324).
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "NotFound" });
  return {
    title: t("title"),
    // Do not inherit the homepage canonical/hreflang from the locale layout.
    alternates: {},
    robots: { index: false, follow: false },
  };
}

export default function CatchAllNotFound() {
  notFound();
}
