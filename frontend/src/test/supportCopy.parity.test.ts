import { describe, it, expect } from "vitest";
import en from "../../messages/en.json";
import it_ from "../../messages/it.json";
import de from "../../messages/de.json";
import es from "../../messages/es.json";
import fr from "../../messages/fr.json";
import pt from "../../messages/pt.json";
import ar from "../../messages/ar.json";
import ru from "../../messages/ru.json";
import zh from "../../messages/zh.json";
import hi from "../../messages/hi.json";
import ko from "../../messages/ko.json";

// BITB-168 anti-nag rules, enforced on the Support-Us copy in all 11 locales.
type Catalog = typeof en;
const catalogs: Record<string, Catalog> = {
  en,
  it: it_,
  de,
  es,
  fr,
  pt,
  ar,
  ru,
  zh,
  hi,
  ko,
};

function supportStrings(c: Catalog): Record<string, string> {
  return {
    "Footer.supportUs": c.Footer.supportUs,
    "About.supportTitle": c.About.supportTitle,
    "About.supportBody": c.About.supportBody,
    "About.supportLinkLabel": c.About.supportLinkLabel,
  };
}

describe.each(Object.keys(catalogs))("support copy (%s)", (locale) => {
  const strings = supportStrings(catalogs[locale]);

  it("has all keys non-empty", () => {
    for (const v of Object.values(strings)) {
      expect(typeof v).toBe("string");
      expect(v.trim().length).toBeGreaterThan(0);
    }
  });

  it("is translated, not an English fallback", () => {
    if (locale === "en") return;
    const enStrings = supportStrings(en);
    for (const [k, v] of Object.entries(strings)) {
      expect(v, k).not.toBe(enStrings[k]);
    }
  });

  it("has no urgency language, exclamation marks or emoji", () => {
    for (const [k, v] of Object.entries(strings)) {
      expect(v, k).not.toMatch(/goal|urgent|almost there/i);
      expect(v, k).not.toMatch(/[!！]/);
      expect(v, k).not.toMatch(/\p{Extended_Pictographic}/u);
    }
  });
});
