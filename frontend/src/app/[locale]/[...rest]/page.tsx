import { notFound } from "next/navigation";

// Catch-all for unmatched paths under a locale (e.g. /ar/__x404). Without it,
// Next renders its built-in English 404 *outside* the locale layout; calling
// notFound() here renders the localized [locale]/not-found.tsx instead, with
// the correct <html lang/dir> and a 404 status.
export default function CatchAllNotFound() {
  notFound();
}
