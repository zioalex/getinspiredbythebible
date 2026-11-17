import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

const catalogs = Object.fromEntries(
  Object.entries(
    import.meta.glob("../../../messages/*.json", {
      eager: true,
      import: "default",
    }) as Record<string, { NotFound: Record<string, string> }>,
  ).map(([path, mod]) => [path.match(/([a-z]+)\.json$/)![1], mod]),
);

let activeLocale = "en";
vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async (ns: string) => {
    const messages = catalogs[activeLocale].NotFound;
    expect(ns).toBe("NotFound");
    return (key: string) => messages[key];
  }),
}));
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, ...props }: React.PropsWithChildren) => (
    <a {...props}>{children}</a>
  ),
}));

import NotFound, { generateMetadata } from "./not-found";

describe("localized not-found page", () => {
  it.each(["ar", "zh", "hi", "ru"])(
    "renders %s text instead of English",
    async (locale) => {
      activeLocale = locale;
      render(await NotFound());

      const m = catalogs[locale].NotFound;
      expect(screen.getByText(m.title)).toBeInTheDocument();
      expect(screen.getByText(m.body)).toBeInTheDocument();
      expect(screen.getByRole("link", { name: m.backHome })).toHaveAttribute(
        "href",
        "/",
      );
      expect(screen.queryByText("Page not found")).not.toBeInTheDocument();
      expect(m.title).not.toBe(catalogs.en.NotFound.title);
    },
  );

  it.each(["ar", "zh"])(
    "sets a localized noindex title with no inherited canonical (%s)",
    async (locale) => {
      activeLocale = locale;
      const md = await generateMetadata();
      expect(md.title).toBe(catalogs[locale].NotFound.title);
      expect(md.robots).toEqual({ index: false, follow: false });
      expect(md.alternates).toEqual({});
    },
  );

  it("has NotFound strings in all 11 locales", () => {
    expect(Object.keys(catalogs)).toHaveLength(11);
    for (const m of Object.values(catalogs)) {
      expect(m.NotFound.title).toBeTruthy();
      expect(m.NotFound.body).toBeTruthy();
      expect(m.NotFound.backHome).toBeTruthy();
    }
  });
});
