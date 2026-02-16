import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LanguageSwitcher from "./LanguageSwitcher";
import { renderWithIntl } from "@/test/i18n-helpers";

const mockReplace = vi.fn();
const mockPathname = "/some-page";

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname,
}));

vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en", "it", "de"] },
}));

vi.mock("next-intl", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next-intl")>();
  return {
    ...actual,
    useLocale: () => "en",
  };
});

describe("LanguageSwitcher", () => {
  beforeEach(() => {
    mockReplace.mockClear();
  });

  it("renders a select with 3 options", () => {
    renderWithIntl(<LanguageSwitcher />);
    const select = screen.getByRole("combobox");
    const options = screen.getAllByRole("option");
    expect(select).toBeDefined();
    expect(options).toHaveLength(3);
  });

  it("current locale is pre-selected", () => {
    renderWithIntl(<LanguageSwitcher />);
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("en");
  });

  it("changing select value calls router.replace with new locale", () => {
    renderWithIntl(<LanguageSwitcher />);
    const select = screen.getByRole("combobox");
    fireEvent.change(select, { target: { value: "it" } });
    expect(mockReplace).toHaveBeenCalledWith(mockPathname, { locale: "it" });
  });

  it("all locale labels are native names", () => {
    renderWithIntl(<LanguageSwitcher />);
    expect(screen.getByText("English")).toBeDefined();
    expect(screen.getByText("Italiano")).toBeDefined();
    expect(screen.getByText("Deutsch")).toBeDefined();
  });

  it("renders Globe icon", () => {
    const { container } = renderWithIntl(<LanguageSwitcher />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
  });
});
