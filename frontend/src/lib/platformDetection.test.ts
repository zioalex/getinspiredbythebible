import { describe, it, expect } from "vitest";
import { isIOSUserAgent } from "./platformDetection";

const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";

const IPOD_UA =
  "Mozilla/5.0 (iPod touch; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1";

const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36";

const DESKTOP_CHROME_MACOS_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36";

describe("isIOSUserAgent", () => {
  it("detects a real iPhone Safari user agent", () => {
    expect(isIOSUserAgent(IPHONE_UA)).toBe(true);
  });

  it("detects a real iPod user agent", () => {
    expect(isIOSUserAgent(IPOD_UA)).toBe(true);
  });

  it("does not detect an Android user agent", () => {
    expect(isIOSUserAgent(ANDROID_UA)).toBe(false);
  });

  it("does not detect a desktop Chrome/macOS user agent (also covers iPadOS, which spoofs Macintosh)", () => {
    expect(isIOSUserAgent(DESKTOP_CHROME_MACOS_UA)).toBe(false);
  });

  it("returns false for null", () => {
    expect(isIOSUserAgent(null)).toBe(false);
  });

  it("returns false for an empty string", () => {
    expect(isIOSUserAgent("")).toBe(false);
  });
});
