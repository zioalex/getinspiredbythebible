import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  crisisRequestFields,
  getCrisisRegionOverride,
  regionFromTag,
  setCrisisRegionOverride,
} from "./crisisRegion";

describe("crisisRegion (BITB-255)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("round-trips an override, upper-casing it", () => {
    expect(getCrisisRegionOverride()).toBeNull();
    setCrisisRegionOverride("at");
    expect(getCrisisRegionOverride()).toBe("AT");
    setCrisisRegionOverride(null);
    expect(getCrisisRegionOverride()).toBeNull();
  });

  it("ignores invalid stored/new values", () => {
    window.localStorage.setItem("vq_crisis_region_override", "XYZ");
    expect(getCrisisRegionOverride()).toBeNull();
    setCrisisRegionOverride("not-a-region");
    expect(window.localStorage.getItem("vq_crisis_region_override")).toBeNull();
  });

  it("never throws when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    expect(getCrisisRegionOverride()).toBeNull();
    expect(() => setCrisisRegionOverride("DE")).not.toThrow();
  });

  it.each([
    ["pt-BR", "BR"],
    ["de-AT", "AT"],
    ["zh-Hans-CN", "CN"],
    ["en", null],
    ["", null],
    [undefined, null],
  ])("regionFromTag(%s) -> %s", (tag, expected) => {
    expect(regionFromTag(tag)).toBe(expected);
  });

  it("sends the navigator region, else the locale region, else omits it", () => {
    const lang = vi.spyOn(window.navigator, "language", "get");
    lang.mockReturnValue("fr-CA");
    expect(crisisRequestFields("de")).toEqual({
      region: "CA",
      region_override: false,
      supports_crisis_card: true,
    });
    lang.mockReturnValue("en");
    expect(crisisRequestFields("pt-BR").region).toBe("BR");
    const bare = crisisRequestFields("it");
    expect(bare).toEqual({
      region_override: false,
      supports_crisis_card: true,
    });
    expect("region" in bare).toBe(false);
  });

  it("an override wins and sets region_override", () => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue("it-IT");
    setCrisisRegionOverride("CH");
    expect(crisisRequestFields("it")).toEqual({
      region: "CH",
      region_override: true,
      supports_crisis_card: true,
    });
  });
});
