import { promises as fs } from "fs";
import path from "path";

export type LegalDocType = "privacy-policy" | "terms-of-service";

const LEGAL_DIR = path.join(process.cwd(), "src", "content", "legal");

const LEGAL_TITLES: Record<LegalDocType, string> = {
  "privacy-policy": "Privacy Policy",
  "terms-of-service": "Terms of Service",
};

const TRANSLATION_NOTICE: Record<string, string> = {
  en: "",
  it: "This page is available in English. Localized legal translation is in progress.",
  de: "This page is available in English. Localized legal translation is in progress.",
  es: "This page is available in English. Localized legal translation is in progress.",
  fr: "This page is available in English. Localized legal translation is in progress.",
  pt: "This page is available in English. Localized legal translation is in progress.",
  ar: "This page is available in English. Localized legal translation is in progress.",
};

export async function getLegalMarkdown(
  docType: LegalDocType,
  locale: string,
): Promise<string> {
  const filePath = path.join(LEGAL_DIR, `${docType}.en.md`);
  const raw = await fs.readFile(filePath, "utf8");

  if (locale === "en") {
    return raw;
  }

  const notice = TRANSLATION_NOTICE[locale] ?? TRANSLATION_NOTICE.en;

  return `> ${notice}\n\n${raw}`;
}

export function getLegalMetadata(docType: LegalDocType) {
  const title = LEGAL_TITLES[docType];

  return {
    title: `${title} | Bible Inspiration`,
    description: `${title} for Get Inspired by the Bible.`,
  };
}
