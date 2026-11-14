import { describe, it, expect } from "vitest";
import {
  buildHtml,
  fontFamily,
  fontPackages,
  localeDir,
  manifestHash,
  rewriteFontCss,
  LOCALES,
} from "./generate-og-images.mjs";

describe("generate-og-images pure helpers", () => {
  it("uses rtl only for Arabic", () => {
    for (const l of LOCALES) {
      expect(localeDir(l)).toBe(l === "ar" ? "rtl" : "ltr");
    }
    expect(buildHtml("ar", "t", "d")).toContain('lang="ar" dir="rtl"');
    expect(buildHtml("en", "t", "d")).toContain('lang="en" dir="ltr"');
  });

  it("puts the right Noto family first, Noto Sans always present", () => {
    expect(fontFamily("ar")).toMatch(/^'Noto Sans Arabic', 'Noto Sans'/);
    expect(fontFamily("hi")).toMatch(/^'Noto Sans Devanagari', 'Noto Sans'/);
    expect(fontFamily("zh")).toMatch(/^'Noto Sans SC', 'Noto Sans'/);
    expect(fontFamily("ko")).toMatch(/^'Noto Sans KR', 'Noto Sans'/);
    for (const l of ["en", "it", "de", "es", "fr", "pt", "ru"]) {
      expect(fontFamily(l)).toMatch(/^'Noto Sans', sans-serif$/);
    }
    expect(fontPackages("hi")).toEqual(["noto-sans-devanagari", "noto-sans"]);
    expect(fontPackages("en")).toEqual(["noto-sans"]);
  });

  it("hashes title + newline + description with sha256", () => {
    expect(manifestHash("a", "b")).toBe(
      "7e18f737311b2dc3b2f269dd78396b0351f14fb66efa879f768cb23181883c78",
    );
    expect(manifestHash("a", "b")).toMatch(/^[0-9a-f]{64}$/);
    expect(manifestHash("a", "b")).not.toBe(manifestHash("ab", ""));
    expect(manifestHash("a", "b")).not.toBe(manifestHash("a\nb", ""));
  });

  it("escapes HTML in title and description", () => {
    const html = buildHtml("en", "<b>", "a & b");
    expect(html).toContain("&lt;b&gt;");
    expect(html).toContain("a &amp; b");
  });

  it("rewrites fontsource urls to absolute file urls (woff2 only)", () => {
    const css =
      "src: url(./files/x-400-normal.woff2) format('woff2'), url(./files/x-400-normal.woff) format('woff');";
    expect(rewriteFontCss(css, "file:///f")).toBe(
      "src: url(file:///f/x-400-normal.woff2) format('woff2');",
    );
  });
});
