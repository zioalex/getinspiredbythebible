import { describe, it, expect } from "vitest";
import { buildJsonLd, pageMetadata, SITE_URL } from "./seo";

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
    });

    expect(metadata.twitter?.card).toBe("summary_large_image");
  });
});
