import { describe, it, expect } from "vitest";
import { resolveBuildId } from "./generate-build-info.mjs";

describe("resolveBuildId", () => {
  it("uses NEXT_PUBLIC_BUILD_ID verbatim when it's already a safe value", () => {
    expect(resolveBuildId({ NEXT_PUBLIC_BUILD_ID: "abc123" })).toBe("abc123");
  });

  it("falls back to a dev-<timestamp> id when unset", () => {
    expect(resolveBuildId({})).toMatch(/^dev-\d+$/);
  });

  it("falls back to a dev-<timestamp> id when blank/whitespace", () => {
    expect(resolveBuildId({ NEXT_PUBLIC_BUILD_ID: "" })).toMatch(/^dev-\d+$/);
    expect(resolveBuildId({ NEXT_PUBLIC_BUILD_ID: "   " })).toMatch(
      /^dev-\d+$/,
    );
    expect(resolveBuildId(undefined)).toMatch(/^dev-\d+$/);
  });

  it("sanitizes disallowed characters to hyphens", () => {
    expect(resolveBuildId({ NEXT_PUBLIC_BUILD_ID: "feat/my branch#1" })).toBe(
      "feat-my-branch-1",
    );
  });

  it("truncates to at most 64 characters", () => {
    const long = "a".repeat(200);
    const result = resolveBuildId({ NEXT_PUBLIC_BUILD_ID: long });
    expect(result.length).toBeLessThanOrEqual(64);
    expect(result).toBe("a".repeat(64));
  });
});
