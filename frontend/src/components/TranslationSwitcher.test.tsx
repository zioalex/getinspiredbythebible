import { screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import TranslationSwitcher, {
  translationOptionLabel,
} from "./TranslationSwitcher";
import { renderWithIntl } from "@/test/i18n-helpers";
import enMessages from "../../messages/en.json";
import type { TranslationInfo } from "@/lib/api";

const TRANSLATIONS: TranslationInfo[] = [
  {
    code: "kjv",
    name: "King James Version",
    short_name: "KJV",
    language: "English",
    language_code: "en",
    year: 1611,
  },
  {
    code: "luther1912",
    name: "Luther 1912",
    short_name: "Luther",
    language: "German",
    language_code: "de",
    year: 1912,
  },
  {
    code: "synodal",
    name: "Синодальный перевод",
    short_name: "Synodal",
    language: "Russian",
    language_code: "ru",
  },
];

function renderSwitcher(active = "kjv", onChange = vi.fn()) {
  renderWithIntl(
    <TranslationSwitcher
      translations={TRANSLATIONS}
      activeTranslationCode={active}
      onChange={onChange}
    />,
  );
  return onChange;
}

// #1223: the Bible version select overflowed the mobile menu because a
// native <select> sizes itself to its longest option.
describe("TranslationSwitcher", () => {
  it("shows only the short name in the collapsed control", () => {
    renderSwitcher("kjv");
    const label = screen.getByTestId("translation-switcher-label");
    expect(label).toHaveTextContent(/^KJV$/);
    expect(label).toHaveClass("truncate", "min-w-0");
  });

  it("keeps the full descriptive name in the option list", () => {
    renderSwitcher();
    expect(
      screen.getByRole("option", {
        name: "King James Version — KJV, 1611",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Синодальный перевод — Synodal" }),
    ).toBeInTheDocument();
  });

  it("exposes the full name as a tooltip on the collapsed control", () => {
    renderSwitcher("luther1912");
    expect(screen.getByTestId("translation-switcher-control")).toHaveAttribute(
      "title",
      translationOptionLabel(TRANSLATIONS[1]),
    );
  });

  it("is width-bounded so it cannot spill out of the menu", () => {
    renderSwitcher();
    const control = screen.getByTestId("translation-switcher-control");
    expect(control).toHaveClass("min-w-0", "max-w-full", "flex-1");
    expect(control.parentElement).toHaveClass("w-full", "min-w-0");
  });

  it("uses a >= 16px native select so iOS does not zoom on focus", () => {
    renderSwitcher();
    const select = screen.getByRole("combobox", {
      name: enMessages.Header.bibleVersion,
    });
    expect(select).toHaveClass("text-base", "absolute", "inset-0", "w-full");
    expect(select.className).not.toMatch(/\btext-(xs|sm)\b/);
  });

  it("falls back to the placeholder label when nothing is selected", () => {
    renderSwitcher("");
    expect(screen.getByTestId("translation-switcher-label")).toHaveTextContent(
      enMessages.Header.bibleVersion,
    );
  });

  it("calls onChange with the selected code", () => {
    const onChange = renderSwitcher();
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "luther1912" },
    });
    expect(onChange).toHaveBeenCalledWith("luther1912");
  });

  it("is disabled while translations are loading", () => {
    renderWithIntl(
      <TranslationSwitcher
        translations={[]}
        activeTranslationCode=""
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
