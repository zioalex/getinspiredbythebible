import { describe, it, expect } from "vitest";
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
});
