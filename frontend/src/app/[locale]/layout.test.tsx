import { describe, it, expect, vi } from "vitest";

// layout.tsx's component tree pulls in next-intl's client navigation
// (@/i18n/navigation, via FooterGate/WhatsNewModal), which this test has no
// need to exercise — we only assert on the statically-exported `viewport`
// object. Mock it out so importing the module doesn't require a full
// next-intl/next runtime.
vi.mock("@/i18n/navigation", () => ({
  Link: () => null,
  usePathname: () => "/",
  useRouter: () => ({}),
  redirect: vi.fn(),
}));

// Real per-locale catalogs back the mocked server translator so we can assert
// on the actual shipped copy for every locale.
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(
    async ({ locale, namespace }: { locale: string; namespace: string }) => {
      const ns = (catalogs[locale] as Record<string, Record<string, string>>)[
        namespace
      ];
      return (key: string) => ns[key];
    },
  ),
  getMessages: vi.fn(),
  setRequestLocale: vi.fn(),
}));

import { generateMetadata, viewport } from "./layout";
import { routing } from "@/i18n/routing";

const catalogs = Object.fromEntries(
  Object.entries(
    import.meta.glob("../../../messages/*.json", {
      eager: true,
      import: "default",
    }) as Record<string, unknown>,
  ).map(([path, mod]) => [path.match(/([a-z]+)\.json$/)![1], mod]),
) as Record<string, unknown>;

describe("viewport", () => {
  it("covers the safe area and keeps pinch-zoom enabled", () => {
    expect(viewport.viewportFit).toBe("cover");
    expect(viewport.maximumScale).toBe(5);
  });

  it("lets the Android keyboard resize the layout viewport (#1224)", () => {
    expect(viewport.interactiveWidget).toBe("resizes-content");
  });
});

describe("generateMetadata (home page)", () => {
  it.each(routing.locales)(
    "uses a 120-155 char homeDescription distinct from the title for %s",
    async (locale) => {
      const md = await generateMetadata({
        params: Promise.resolve({ locale }),
      });
      const description = md.description as string;
      const defaultTitle = (md.title as { default: string }).default;

      expect(description.length).toBeGreaterThanOrEqual(120);
      expect(description.length).toBeLessThanOrEqual(155);
      expect(description).not.toBe(defaultTitle);
      expect(defaultTitle).not.toContain(description);
      // The short tagline stays in the title only.
      const tagline = (
        catalogs[locale] as { Metadata: { description: string } }
      ).Metadata.description;
      expect(description).not.toBe(tagline);
      expect(md.openGraph?.description).toBe(description);
      expect(md.twitter?.description).toBe(description);
    },
  );
});
