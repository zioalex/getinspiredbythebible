import { describe, it, expect } from "vitest";
import { routing } from "@/i18n/routing";
import fs from "fs";
import path from "path";

describe("i18n routing configuration", () => {
  it("has en as default locale", () => {
    expect(routing.defaultLocale).toBe("en");
  });

  it("supports en, it, de, es, fr, pt, and ar locales", () => {
    expect(routing.locales).toEqual(["en", "it", "de", "es", "fr", "pt", "ar"]);
  });

  it("uses localePrefix always", () => {
    expect(routing.localePrefix).toBe("always");
  });

  it("default locale is included in locales list", () => {
    expect(routing.locales).toContain(routing.defaultLocale);
  });

  it("every locale has a corresponding message file", () => {
    const messagesDir = path.resolve(__dirname, "../../messages");
    for (const locale of routing.locales) {
      const filePath = path.join(messagesDir, `${locale}.json`);
      expect(fs.existsSync(filePath), `Missing messages/${locale}.json`).toBe(
        true,
      );
    }
  });

  it("no message file exists without a matching locale", () => {
    const messagesDir = path.resolve(__dirname, "../../messages");
    const files = fs
      .readdirSync(messagesDir)
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(".json", ""));

    for (const file of files) {
      expect(
        (routing.locales as readonly string[]).includes(file),
        `messages/${file}.json exists but locale "${file}" is not in routing.locales`,
      ).toBe(true);
    }
  });
});
