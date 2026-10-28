import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import LanguageSwitcher, { localeLabels } from "./LanguageSwitcher";
import { renderWithIntl } from "@/test/i18n-helpers";
import { routing } from "@/i18n/routing";

const mockReplace = vi.fn();
const mockPathname = "/some-page";

vi.mock("@/i18n/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname,
}));

vi.mock("@/i18n/routing", () => ({
  routing: { locales: ["en", "it", "de", "es", "fr", "pt", "ar"] },
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

  it("renders one option per configured locale", () => {
    renderWithIntl(<LanguageSwitcher />);
    const select = screen.getByRole("combobox");
    const options = screen.getAllByRole("option");
    expect(select).toBeDefined();
    expect(options).toHaveLength(routing.locales.length);
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

  it("every configured locale has a label and it is displayed", () => {
    renderWithIntl(<LanguageSwitcher />);
    for (const loc of routing.locales) {
      const label = localeLabels[loc];
      expect(label, `Missing localeLabels entry for "${loc}"`).toBeTruthy();
      expect(
        screen.getByRole("option", { name: label }),
        `Option for locale "${loc}" not rendered`,
      ).toBeDefined();
    }
  });

  // #1223: the control must fit the mobile menu instead of sizing itself to
  // its longest option, and must not trigger iOS focus zoom.
  it("shows the current language as a truncating label inside a width-bounded control", () => {
    renderWithIntl(<LanguageSwitcher />);
    const control = screen.getByTestId("language-switcher-control");
    expect(control).toHaveClass("min-w-0", "max-w-full", "flex-1");
    expect(control.parentElement).toHaveClass("w-full", "min-w-0");
    const label = control.querySelector("span.truncate");
    expect(label).toHaveTextContent("English");
  });

  it("keeps the native select at >= 16px and stretched over the control", () => {
    renderWithIntl(<LanguageSwitcher />);
    const select = screen.getByRole("combobox");
    expect(select).toHaveClass("text-base", "absolute", "inset-0", "w-full");
    expect(select.className).not.toMatch(/\btext-(xs|sm)\b/);
  });

  it("renders Globe icon", () => {
    const { container } = renderWithIntl(<LanguageSwitcher />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
  });
});
