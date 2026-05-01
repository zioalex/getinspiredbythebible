import { screen, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import WhatsNewModal from "./WhatsNewModal";
import { renderWithIntl } from "@/test/i18n-helpers";

// Mock next-intl's useLocale
vi.mock("next-intl", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-intl")>();
  return {
    ...actual,
    useLocale: () => "en",
  };
});

// Mock @/i18n/navigation Link
vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const STORAGE_KEY = "vq:lastSeenVersion";

function mockFetch(payload: object) {
  vi.spyOn(global, "fetch").mockResolvedValueOnce({
    ok: true,
    json: async () => payload,
  } as Response);
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("WhatsNewModal", () => {
  it("renders nothing when version is null", async () => {
    mockFetch({ version: null });
    const { container } = renderWithIntl(<WhatsNewModal />);
    // wait for effect
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing on first visit and silently stores version", async () => {
    mockFetch({ version: "1.0.0", body: "Initial release" });
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    // No modal shown — first-ever visit
    expect(container.innerHTML).toBe("");
    // Version silently stored
    expect(localStorage.getItem(STORAGE_KEY)).toBe("1.0.0");
  });

  it("renders nothing when stored version matches current", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.0.0", body: "Nothing new" });
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });

  it("renders modal when stored version differs from current", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.1.0", body: "Something new in 1.1.0" });
    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(screen.getByRole("dialog")).toBeDefined();
    expect(screen.getByText(/Something new in 1\.1\.0/i)).toBeDefined();
  });

  it("dismisses modal and stores new version on dismiss click", async () => {
    localStorage.setItem(STORAGE_KEY, "1.0.0");
    mockFetch({ version: "1.1.0", body: "New features" });
    renderWithIntl(<WhatsNewModal />);
    await act(async () => {});

    const dismissBtn = screen.getAllByText("Got it")[0];
    await act(async () => {
      dismissBtn.click();
    });

    expect(localStorage.getItem(STORAGE_KEY)).toBe("1.1.0");
  });

  it("renders nothing when fetch fails", async () => {
    vi.spyOn(global, "fetch").mockRejectedValueOnce(new Error("network error"));
    const { container } = renderWithIntl(<WhatsNewModal />);
    await act(async () => {});
    expect(container.innerHTML).toBe("");
  });
});
