import { describe, it, expect, vi } from "vitest";

const notFound = vi.fn(() => {
  throw new Error("NEXT_NOT_FOUND");
});
vi.mock("next/navigation", () => ({ notFound }));

import CatchAllNotFound from "./page";

describe("[locale] catch-all", () => {
  it("delegates unmatched paths to the localized not-found page", () => {
    expect(() => CatchAllNotFound()).toThrow("NEXT_NOT_FOUND");
    expect(notFound).toHaveBeenCalledTimes(1);
  });
});
