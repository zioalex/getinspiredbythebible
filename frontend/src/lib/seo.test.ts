import { describe, it, expect } from "vitest";
import { buildJsonLd, pageMetadata, OG_LOCALE, SITE_URL } from "./seo";
import { routing } from "@/i18n/routing";

describe("buildJsonLd", () => {
  it("returns a string that parses cleanly as JSON", () => {
    const json = buildJsonLd({
      locale: "en",
      description: "Get inspired daily by God's Word",
    });
    expect(typeof json).toBe("string");
    expect(() => JSON.parse(json)).not.toThrow();
  });

  it("builds a @graph with exactly one WebSite and one Organization node", () => {
    const parsed = JSON.parse(
      buildJsonLd({
        locale: "en",
        description: "Get inspired daily by God's Word",
      }),
    );

    expect(parsed["@context"]).toBe("https://schema.org");
    expect(Array.isArray(parsed["@graph"])).toBe(true);

    const websites = parsed["@graph"].filter(
      (n: { "@type": string }) => n["@type"] === "WebSite",
    );
    const organizations = parsed["@graph"].filter(
      (n: { "@type": string }) => n["@type"] === "Organization",
    );
    expect(websites).toHaveLength(1);
    expect(organizations).toHaveLength(1);
  });

  it("sets the WebSite url/description/inLanguage from the given inputs", () => {
    const parsed = JSON.parse(
      buildJsonLd({
        locale: "de",
        description: "Täglich inspiriert durch Gottes Wort",
      }),
    );
    const website = parsed["@graph"].find(
      (n: { "@type": string }) => n["@type"] === "WebSite",
    );

    expect(website.url).toContain("/de");
    expect(website.description).toBe("Täglich inspiriert durch Gottes Wort");
    expect(website.inLanguage).toBe("de");
  });

  it("resolves the Organization logo to a raster icon (SVG logos are not accepted)", () => {
    const parsed = JSON.parse(
      buildJsonLd({
        locale: "en",
        description: "Get inspired daily by God's Word",
      }),
    );
    const organization = parsed["@graph"].find(
      (n: { "@type": string }) => n["@type"] === "Organization",
    );

    expect(organization.logo).toBe(`${SITE_URL}/icons/icon-512.png`);
  });
});

describe("pageMetadata", () => {
  it("upgrades the Twitter card to summary_large_image", () => {
    const metadata = pageMetadata({
      locale: "en",
      title: "Vox Quieta",
      description: "Get inspired daily by God's Word",
    });

    expect(metadata.twitter?.card).toBe("summary_large_image");
  });
});

describe("pageMetadata Open Graph locale", () => {
  const expected: Record<string, string> = {
    en: "en_US",
    it: "it_IT",
    de: "de_DE",
    es: "es_ES",
    fr: "fr_FR",
    pt: "pt_BR",
    ar: "ar_AR",
    ru: "ru_RU",
    zh: "zh_CN",
    hi: "hi_IN",
    ko: "ko_KR",
  };

  it("covers every routing locale in the map", () => {
    expect(Object.keys(OG_LOCALE).sort()).toEqual([...routing.locales].sort());
  });

  it.each(Object.entries(expected))(
    "uses region-qualified og:locale for %s (%s) and lists the other ten as alternates",
    (locale, ogLocale) => {
      const md = pageMetadata({
        locale,
        title: "t",
        description: "d",
      });
      const og = md.openGraph as {
        locale: string;
        alternateLocale: string[];
      };
      expect(og.locale).toBe(ogLocale);
      expect(og.alternateLocale).toHaveLength(10);
      expect(og.alternateLocale).not.toContain(ogLocale);
      expect(new Set([og.locale, ...og.alternateLocale])).toEqual(
        new Set(Object.values(expected)),
      );
    },
  );
});
