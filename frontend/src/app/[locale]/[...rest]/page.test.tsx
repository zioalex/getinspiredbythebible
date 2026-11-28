import { describe, it, expect, vi } from "vitest";

const { notFound } = vi.hoisted(() => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));
vi.mock("next/navigation", () => ({ notFound }));
vi.mock("next-intl/server", () => ({
  getTranslations:
    async ({ locale }: { locale: string }) =>
    (key: string) =>
      `${locale}:${key}`,
}));

import CatchAllNotFound, { generateMetadata } from "./page";

describe("[locale] catch-all", () => {
  it("delegates unmatched paths to the localized not-found page", () => {
    expect(() => CatchAllNotFound()).toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalledTimes(1);
  });

  it("returns a localized, noindex title without a canonical", async () => {
    const md = await generateMetadata({
      params: Promise.resolve({ locale: "ar" }),
    });
    expect(md.title).toBe("ar:title");
    expect(md.robots).toEqual({ index: false, follow: false });
    expect(md.alternates).toEqual({});
  });
});
