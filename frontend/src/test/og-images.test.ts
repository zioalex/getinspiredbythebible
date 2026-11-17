import { describe, it, expect } from "vitest";
import { createHash } from "crypto";
import { readFileSync, statSync } from "fs";
import { resolve } from "path";
import { routing } from "@/i18n/routing";

const root = resolve(__dirname, "../..");
const ogDir = resolve(root, "public/og");
const HINT = "run `npm run og:generate`";
const PNG_SIGNATURE = "89504e470d0a1a0a";

const manifest: Record<string, string> = JSON.parse(
  readFileSync(resolve(ogDir, "manifest.json"), "utf8"),
);

describe("share images (BITB-299)", () => {
  it("manifest covers exactly the supported locales", () => {
    expect(Object.keys(manifest).sort()).toEqual([...routing.locales].sort());
  });

  describe.each(routing.locales)("%s", (locale) => {
    const file = resolve(ogDir, `${locale}.png`);

    it("is a 1200x630 PNG under 150 KB", () => {
      let bytes: Buffer;
      try {
        bytes = readFileSync(file);
      } catch {
        throw new Error(`public/og/${locale}.png is missing — ${HINT}`);
      }
      expect(bytes.subarray(0, 8).toString("hex")).toBe(PNG_SIGNATURE);
      expect(bytes.subarray(12, 16).toString("ascii")).toBe("IHDR");
      expect(bytes.readUInt32BE(16)).toBe(1200);
      expect(bytes.readUInt32BE(20)).toBe(630);
      expect(statSync(file).size).toBeLessThan(150 * 1024);
    });

    it("matches the current Metadata copy in messages", () => {
      const { Metadata } = JSON.parse(
        readFileSync(resolve(root, `messages/${locale}.json`), "utf8"),
      );
      const expected = createHash("sha256")
        .update(`${Metadata.title}\n${Metadata.description}`)
        .digest("hex");
      expect(
        manifest[locale],
        `share image for "${locale}" is stale — ${HINT}`,
      ).toBe(expected);
    });
  });
});
