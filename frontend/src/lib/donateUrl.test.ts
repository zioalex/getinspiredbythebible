import { describe, it, expect, vi, afterEach } from "vitest";
import { donateUrl } from "./donateUrl";

describe("donateUrl", () => {
  it("appends ref to the default Ko-fi base", () => {
    expect(donateUrl("web-menu")).toBe(
      "https://ko-fi.com/voxquieta?ref=web-menu",
    );
  });

  it("uses & when the base already has a query", () => {
    expect(donateUrl("web-about", "https://example.org/d?x=1")).toBe(
      "https://example.org/d?x=1&ref=web-about",
    );
  });

  it("replaces an existing ref", () => {
    expect(donateUrl("web-footer", "https://example.org/d?ref=old")).toBe(
      "https://example.org/d?ref=web-footer",
    );
  });

  it("returns the base unchanged when it is malformed", () => {
    expect(donateUrl("web-chat-footer", "not a url")).toBe("not a url");
  });

  describe("DONATE_BASE_URL env handling (BITB-157)", () => {
    afterEach(() => {
      vi.unstubAllEnvs();
      vi.resetModules();
    });

    it("falls back to Ko-fi when the env var is an empty string", async () => {
      vi.stubEnv("NEXT_PUBLIC_DONATE_URL", "");
      vi.resetModules();
      const mod = await import("./donateUrl");
      expect(mod.DONATE_BASE_URL).toBe("https://ko-fi.com/voxquieta");
    });

    it("uses the env var when set", async () => {
      vi.stubEnv("NEXT_PUBLIC_DONATE_URL", "https://example.org/give");
      vi.resetModules();
      const mod = await import("./donateUrl");
      expect(mod.donateUrl("web-menu")).toBe(
        "https://example.org/give?ref=web-menu",
      );
    });
  });
});
