import { getTranslations } from "next-intl/server";

/**
 * Localized alt text for the share image: `"<title> — <description>"` from the
 * locale's `Metadata` namespace — exactly what the pre-rendered image shows,
 * regardless of which page is being described. Server-only (BITB-299).
 */
export async function getOgImageAlt(locale: string): Promise<string> {
  const t = await getTranslations({ locale, namespace: "Metadata" });
  return `${t("title")} — ${t("description")}`;
}
