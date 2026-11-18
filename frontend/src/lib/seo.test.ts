import { describe, it, expect } from "vitest";
import { routing } from "@/i18n/routing";
import { buildJsonLd, pageMetadata, SITE_URL } from "./seo";

type OgImage = { url: string; width: number; height: number; alt: string };

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

  it("resolves the Organization logo to SITE_URL/icon.svg", () => {
    const parsed = JSON.parse(
      buildJsonLd({
        locale: "en",
        description: "Get inspired daily by God's Word",
      }),
    );
    const organization = parsed["@graph"].find(
      (n: { "@type": string }) => n["@type"] === "Organization",
    );

    expect(organization.logo).toBe(`${SITE_URL}/icon.svg`);
  });
});

describe("pageMetadata", () => {
  it("upgrades the Twitter card to summary_large_image", () => {
    const metadata = pageMetadata({
      locale: "en",
      title: "Vox Quieta",
      description: "Get inspired daily by God's Word",
      ogImageAlt: "Vox Quieta — Get inspired daily by God's Word",
    });

    expect(metadata.twitter?.card).toBe("summary_large_image");
  });

  describe.each(routing.locales)("share image (%s)", (locale) => {
    const metadata = pageMetadata({
      locale,
      path: "/about",
      title: "Page title",
      description: "Page description",
      ogImageAlt: `alt-${locale}`,
    });

    it("points og:image at the static per-locale PNG", () => {
      const images = metadata.openGraph?.images as OgImage[];
      expect(images[0].url).toBe(`/og/${locale}.png`);
      expect(images[0].width).toBe(1200);
      expect(images[0].height).toBe(630);
      expect(images[0].alt).toBe(`alt-${locale}`);
    });

    it("points twitter:image at the same PNG with a non-empty alt", () => {
      const images = metadata.twitter?.images as OgImage[];
      expect(images[0].url).toBe(`/og/${locale}.png`);
      expect(images[0].alt).toBeTruthy();
    });
  });

  it("ends the Arabic and Hindi image URLs with /og/ar.png and /og/hi.png", () => {
    for (const locale of ["ar", "hi"]) {
      const m = pageMetadata({
        locale,
        title: "t",
        description: "d",
        ogImageAlt: "localized alt",
      });
      expect((m.openGraph?.images as OgImage[])[0].url).toMatch(
        new RegExp(`/og/${locale}\\.png$`),
      );
    }
  });
});
