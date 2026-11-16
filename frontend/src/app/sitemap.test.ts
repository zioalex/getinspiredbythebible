import { describe, it, expect, vi, afterEach } from "vitest";
import sitemap from "./sitemap";
import { routing } from "@/i18n/routing";

// Deterministic generated dates; "/terms" and "/changelog" deliberately absent.
vi.mock("@/generated/lastmod.json", () => ({
  default: {
    "": "2026-10-30T23:22:54+01:00",
    "/about": "2026-10-11T19:41:32+02:00",
    "/privacy": "2026-11-11T20:16:54+01:00",
  },
}));

afterEach(() => {
  vi.useRealTimers();
});

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

  it("uses the generated git date for pages that have one", () => {
    const entries = sitemap();
    const home = entries.find((e) => e.url.endsWith("/en"));
    const privacy = entries.find((e) => e.url.endsWith("/en/privacy"));

    expect(home!.lastModified).toEqual(new Date("2026-10-30T23:22:54+01:00"));
    expect(privacy!.lastModified).toEqual(
      new Date("2026-11-11T20:16:54+01:00"),
    );
    expect(home!.lastModified).not.toEqual(privacy!.lastModified);
  });

  it("omits lastModified for pages without a generated date", () => {
    const entries = sitemap();
    const terms = entries.filter((e) => /\/terms$/.test(e.url));

    expect(terms).toHaveLength(routing.locales.length);
    for (const entry of terms) {
      expect(entry).not.toHaveProperty("lastModified");
    }
  });

  it("never stamps entries with the current time", () => {
    const now = new Date("2030-01-01T00:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);

    for (const entry of sitemap()) {
      if (entry.lastModified) {
        expect(new Date(entry.lastModified).getTime()).not.toBe(now.getTime());
      }
    }
  });
});
