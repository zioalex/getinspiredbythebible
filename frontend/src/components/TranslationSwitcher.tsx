"use client";

import { Book, ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import type { TranslationInfo } from "@/lib/api";

interface TranslationSwitcherProps {
  translations: TranslationInfo[];
  activeTranslationCode: string;
  onChange: (code: string) => void;
}

/** Full descriptive label, shown only inside the open option list. */
export function translationOptionLabel(tr: TranslationInfo): string {
  return `${tr.name} — ${tr.short_name}${tr.year ? `, ${tr.year}` : ""}`;
}

// The collapsed control shows only the short name (e.g. "KJV") in a styled
// box that truncates with an ellipsis, while a transparent native <select>
// is stretched over it to keep the OS picker, keyboard navigation and screen
// reader semantics. A native <select> always sizes itself to its longest
// option, which is what pushed "King James Version — KJV, 1611" out of the
// mobile menu (#1223). Same pattern as the header Bible chip in ChatIsland.
export default function TranslationSwitcher({
  translations,
  activeTranslationCode,
  onChange,
}: TranslationSwitcherProps) {
  const t = useTranslations("Header");
  const active = translations.find((tr) => tr.code === activeTranslationCode);
  const disabled = translations.length === 0;

  return (
    <div className="flex w-full min-w-0 items-center gap-1.5">
      <Book className="w-4 h-4 text-gray-500 shrink-0" aria-hidden="true" />
      <div
        data-testid="translation-switcher-control"
        title={active ? translationOptionLabel(active) : t("bibleVersion")}
        className={`relative flex min-w-0 max-w-full flex-1 items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-600 focus-within:ring-2 focus-within:ring-primary-500 ${
          disabled ? "cursor-not-allowed opacity-60" : ""
        }`}
      >
        <span
          data-testid="translation-switcher-label"
          aria-hidden="true"
          className="min-w-0 flex-1 truncate"
        >
          {active ? active.short_name : t("bibleVersion")}
        </span>
        <ChevronDown
          className="w-3.5 h-3.5 shrink-0 text-gray-400"
          aria-hidden="true"
        />
        {/* text-base (16px) keeps iOS Safari from zooming on focus. */}
        <select
          value={activeTranslationCode}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          aria-label={t("bibleVersion")}
          className="absolute inset-0 h-full w-full max-w-full cursor-pointer opacity-0 text-base disabled:cursor-not-allowed"
        >
          <option value="">{t("bibleVersion")}</option>
          {translations.map((tr) => (
            <option key={tr.code} value={tr.code}>
              {translationOptionLabel(tr)}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
