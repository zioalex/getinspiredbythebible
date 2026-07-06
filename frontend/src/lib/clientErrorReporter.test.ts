import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  scrubPII,
  shouldReport,
  reportClientError,
  __resetReporterStateForTest,
  MAX_REPORTS_PER_SESSION,
  MAX_DETAIL_CHARS,
} from "./clientErrorReporter";

beforeEach(() => {
  __resetReporterStateForTest();
  global.fetch = vi.fn(() => Promise.resolve({ ok: true } as Response));
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("scrubPII", () => {
  it("redacts email addresses", () => {
    expect(scrubPII("failed for jane.doe@example.com now")).toBe(
      "failed for [email] now",
    );
  });

  it("redacts JWT-like and long token strings", () => {
    const jwt =
      "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w"; // pragma: allowlist secret
    expect(scrubPII(`token ${jwt} leaked`)).toContain("[jwt]");
    const longToken = "key=ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"; // pragma: allowlist secret
    expect(scrubPII(longToken)).toContain("[token]");
  });

  it("redacts long digit runs", () => {
    expect(scrubPII("phone 5551234567 here")).toBe("phone [num] here");
  });

  it("caps length at MAX_DETAIL_CHARS", () => {
    // Many short words (not one long token-like run, which would be redacted
    // to a placeholder before truncation).
    const long = "word ".repeat(MAX_DETAIL_CHARS);
    expect(scrubPII(long).length).toBe(MAX_DETAIL_CHARS);
  });

  it("returns empty string for empty input", () => {
    expect(scrubPII("")).toBe("");
  });
});

describe("shouldReport (cap + dedupe)", () => {
  it("dedupes identical reports", () => {
    expect(shouldReport("api_failure", "boom")).toBe(true);
    expect(shouldReport("api_failure", "boom")).toBe(false);
  });

  it("enforces the per-session cap", () => {
    for (let i = 0; i < MAX_REPORTS_PER_SESSION; i++) {
      expect(shouldReport("api_failure", `unique-${i}`)).toBe(true);
    }
    expect(shouldReport("api_failure", "one-too-many")).toBe(false);
  });
});

describe("reportClientError", () => {
  it("POSTs a scrubbed {type, detail} body to /api/v1/client-errors", () => {
    reportClientError("window_onerror", "boom for user@example.com");
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock
      .calls[0];
    expect(String(url)).toContain("/api/v1/client-errors");
    const body = JSON.parse((init as RequestInit).body as string);
    expect(body.type).toBe("window_onerror");
    expect(body.detail).toBe("boom for [email]");
  });

  it("dedupes so a repeating error only POSTs once", () => {
    reportClientError("api_failure", "same");
    reportClientError("api_failure", "same");
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("never throws even if fetch rejects", () => {
    global.fetch = vi.fn(() => Promise.reject(new Error("network down")));
    expect(() => reportClientError("react_render", "x")).not.toThrow();
  });
});
