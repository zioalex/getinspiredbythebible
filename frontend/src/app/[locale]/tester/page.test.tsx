import { describe, it, expect, vi } from "vitest";

vi.mock("next-intl/server", () => ({
  getTranslations: vi.fn(async () => (key: string) => key),
  setRequestLocale: vi.fn(),
}));
vi.mock("@/i18n/navigation", () => ({ Link: () => null }));

import { generateMetadata } from "./page";
import { routing } from "@/i18n/routing";

describe("tester page metadata", () => {
  it.each(routing.locales)("is noindex,nofollow for %s", async (locale) => {
    const md = await generateMetadata({ params: Promise.resolve({ locale }) });
    expect(md.robots).toEqual({ index: false, follow: false });
    // Still carries the shared canonical/OG block.
    expect(md.alternates?.canonical).toBe(`/${locale}/tester`);
  });
});
