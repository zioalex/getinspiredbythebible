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

import { viewport } from "./layout";

describe("viewport", () => {
  it("covers the safe area and keeps pinch-zoom enabled", () => {
    expect(viewport.viewportFit).toBe("cover");
    expect(viewport.maximumScale).toBe(5);
  });
});
