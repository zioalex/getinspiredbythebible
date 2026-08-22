import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  TRADITIONAL_TO_SIMPLIFIED,
  normalizeTraditionalToSimplified,
} from "./chineseScript";

interface T2sCharMapFixture {
  description: string;
  char_map: Record<string, string>;
}

// frontend/src/lib/ -> repo root is three levels up: lib -> src -> frontend -> repo root.
// Read via Node fs/path rather than a TS/JSON import, matching
// localizedBookMap.parity.test.ts: the fixture lives outside frontend/ at the
// repo root and is shared with the backend/Android implementations.
const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_PATH = resolve(
  __dirname,
  "../../../tests/fixtures/t2s_char_map.json",
);

const fixture: T2sCharMapFixture = JSON.parse(
  readFileSync(FIXTURE_PATH, "utf-8"),
);

describe("normalizeTraditionalToSimplified", () => {
  it("converts every table entry", () => {
    for (const [traditional, simplified] of Object.entries(
      TRADITIONAL_TO_SIMPLIFIED,
    )) {
      expect(normalizeTraditionalToSimplified(traditional)).toBe(simplified);
    }
  });

  it("is a no-op on English text", () => {
    const text = "John 3:16, for God so loved the world";
    expect(normalizeTraditionalToSimplified(text)).toBe(text);
  });

  it("is a no-op on Cyrillic text", () => {
    const text = "Иоанна 3:16";
    expect(normalizeTraditionalToSimplified(text)).toBe(text);
  });

  it("is a no-op on Korean text", () => {
    const text = "요한복음 3:16";
    expect(normalizeTraditionalToSimplified(text)).toBe(text);
  });

  it("is a no-op on Arabic text", () => {
    const text = "يوحنا 3:16";
    expect(normalizeTraditionalToSimplified(text)).toBe(text);
  });

  it("is a no-op on already-Simplified text", () => {
    const text = "约翰福音 3:16";
    expect(normalizeTraditionalToSimplified(text)).toBe(text);
  });

  it("is a no-op on an empty string", () => {
    expect(normalizeTraditionalToSimplified("")).toBe("");
  });

  it("is length-preserving over every table entry", () => {
    for (const traditional of Object.keys(TRADITIONAL_TO_SIMPLIFIED)) {
      expect(normalizeTraditionalToSimplified(traditional).length).toBe(
        traditional.length,
      );
    }
  });

  it("is length-preserving over mixed text", () => {
    const text = "請閱讀約翰福音 3:16, danke, 谢谢, 감사합니다";
    expect(normalizeTraditionalToSimplified(text).length).toBe(text.length);
  });

  it("is idempotent", () => {
    const text = "約翰福音 3:16";
    const once = normalizeTraditionalToSimplified(text);
    const twice = normalizeTraditionalToSimplified(once);
    expect(once).toBe(twice);
  });

  it("converts John's book name", () => {
    expect(normalizeTraditionalToSimplified("約翰福音")).toBe("约翰福音");
  });

  it("converts Matthew's book name", () => {
    expect(normalizeTraditionalToSimplified("馬太福音")).toBe("马太福音");
  });

  it("handles mixed-script text (single Traditional character)", () => {
    expect(normalizeTraditionalToSimplified("創世记")).toBe("创世记");
  });

  it("maps both Traditional variants of qi (啟/啓) to the same Simplified target", () => {
    expect(normalizeTraditionalToSimplified("啟")).toBe("启");
    expect(normalizeTraditionalToSimplified("啓")).toBe("启");
  });
});

describe("TRADITIONAL_TO_SIMPLIFIED — fixture parity", () => {
  it("matches tests/fixtures/t2s_char_map.json exactly", () => {
    expect(TRADITIONAL_TO_SIMPLIFIED).toEqual(fixture.char_map);
  });
});
