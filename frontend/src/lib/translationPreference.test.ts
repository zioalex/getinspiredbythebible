import { describe, it, expect, beforeEach } from "vitest";
import {
  getTranslationPreference,
  setTranslationPreference,
  migrateLegacyTranslationPreference,
} from "./translationPreference";
import { TranslationInfo } from "@/lib/api";

const LEGACY_KEY = "preferredTranslation";

const fixtureTranslations: TranslationInfo[] = [
  {
    code: "web",
    name: "World English Bible",
    short_name: "WEB",
    language: "English",
    language_code: "en",
  },
  {
    code: "ita1927",
    name: "Riveduta 1927",
    short_name: "RIV",
    language: "Italiano",
    language_code: "it",
  },
];

beforeEach(() => {
  localStorage.clear();
});

describe("getTranslationPreference / setTranslationPreference", () => {
  it("keeps preferences isolated across locales", () => {
    setTranslationPreference("en", "web");
    expect(getTranslationPreference("it")).toBeNull();
    expect(getTranslationPreference("en")).toBe("web");
  });

  it("round-trips a preference for the same locale", () => {
    setTranslationPreference("it", "ita1927");
    // Simulate leaving and returning: read again independently.
    expect(getTranslationPreference("it")).toBe("ita1927");
  });

  it("clears the preference when passed null", () => {
    setTranslationPreference("en", "web");
    setTranslationPreference("en", null);
    expect(getTranslationPreference("en")).toBeNull();
  });
});

describe("migrateLegacyTranslationPreference", () => {
  it("migrates a resolvable legacy value to its own language only", () => {
    localStorage.setItem(LEGACY_KEY, "ita1927");

    migrateLegacyTranslationPreference(fixtureTranslations);

    expect(getTranslationPreference("it")).toBe("ita1927");
    expect(getTranslationPreference("en")).toBeNull();
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it("discards an unresolvable legacy value without writing any scoped key", () => {
    localStorage.setItem(LEGACY_KEY, "some-unknown-code");

    migrateLegacyTranslationPreference(fixtureTranslations);

    expect(getTranslationPreference("en")).toBeNull();
    expect(getTranslationPreference("it")).toBeNull();
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it("does not clobber an existing scoped preference", () => {
    setTranslationPreference("it", "some-other-code");
    localStorage.setItem(LEGACY_KEY, "ita1927");

    migrateLegacyTranslationPreference(fixtureTranslations);

    expect(getTranslationPreference("it")).toBe("some-other-code");
    expect(localStorage.getItem(LEGACY_KEY)).toBeNull();
  });

  it("is a no-op when there is no legacy value", () => {
    migrateLegacyTranslationPreference(fixtureTranslations);
    expect(getTranslationPreference("en")).toBeNull();
    expect(getTranslationPreference("it")).toBeNull();
  });
});
