import { describe, it, expect, afterEach } from "vitest";
import { followUpsEnabled } from "./featureFlags";

// BITB-080 web enablement: `follow_ups` chips render only when this build-time
// flag is explicitly "true" — anything else (unset, "false", stray casing)
// keeps the web client dark even after the backend-side
// CHAT_FOLLOW_UPS_ENABLED rollout.
describe("followUpsEnabled flag (BITB-080)", () => {
  const flagKey = "NEXT_PUBLIC_FOLLOW_UPS_ENABLED";
  const original = process.env[flagKey];

  afterEach(() => {
    if (original === undefined) delete process.env[flagKey];
    else process.env[flagKey] = original;
  });

  it("is off by default (env unset)", () => {
    delete process.env[flagKey];
    expect(followUpsEnabled()).toBe(false);
  });

  it('is on only when set to exactly "true"', () => {
    process.env[flagKey] = "true";
    expect(followUpsEnabled()).toBe(true);
  });

  it('stays off for "false" and stray casing', () => {
    process.env[flagKey] = "false";
    expect(followUpsEnabled()).toBe(false);
    process.env[flagKey] = "True";
    expect(followUpsEnabled()).toBe(false);
  });
});
