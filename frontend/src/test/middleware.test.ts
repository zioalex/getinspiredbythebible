import { describe, it, expect, vi } from "vitest";

vi.mock("next-intl/middleware", () => ({
  default: vi.fn(() => vi.fn()),
}));

vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en", "it", "de"], defaultLocale: "en" },
}));

// Import after mocks
import { config } from "../../middleware";

describe("Middleware config", () => {
  it("matcher is an array", () => {
    expect(Array.isArray(config.matcher)).toBe(true);
  });

  it("matcher explicitly includes root path /", () => {
    expect(config.matcher).toContain("/");
  });

  it("matcher includes catch-all pattern for non-static paths", () => {
    const catchAll = config.matcher.find(
      (m: string) => m !== "/" && m.includes("(?!"),
    );
    expect(catchAll).toBeDefined();
  });

  it("catch-all pattern excludes api routes", () => {
    const catchAll = config.matcher.find((m: string) => m.includes("(?!"));
    expect(catchAll).toContain("api");
  });

  it("catch-all pattern excludes _next routes", () => {
    const catchAll = config.matcher.find((m: string) => m.includes("(?!"));
    expect(catchAll).toContain("_next");
  });

  it("catch-all pattern excludes files with dots (static assets)", () => {
    const catchAll = config.matcher.find((m: string) => m.includes("(?!"));
    expect(catchAll).toContain("\\.");
  });
});
