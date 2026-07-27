import { describe, it, expect } from "vitest";
import sitemap from "./sitemap";
import { routing } from "@/i18n/routing";

describe("sitemap", () => {
  it("includes /about once per locale", () => {
    const entries = sitemap();
    const aboutEntries = entries.filter((e) => /\/about$/.test(e.url));

    expect(aboutEntries).toHaveLength(routing.locales.length);
    for (const locale of routing.locales) {
      expect(aboutEntries.some((e) => e.url.endsWith(`/${locale}/about`))).toBe(
        true,
      );
    }
  });

  it("gives /about hreflang alternates for every locale", () => {
    const entries = sitemap();
    const enAbout = entries.find((e) => e.url.endsWith("/en/about"));

    expect(enAbout).toBeDefined();
    const languages = enAbout!.alternates!.languages as Record<string, string>;
    expect(Object.keys(languages)).toHaveLength(routing.locales.length);
  });
});
