"use client";

import { Book } from "lucide-react";
import { useTranslations } from "next-intl";
import type { TranslationInfo } from "@/lib/api";

interface TranslationSwitcherProps {
  translations: TranslationInfo[];
  activeTranslationCode: string;
  onChange: (code: string) => void;
}

export default function TranslationSwitcher({
  translations,
  activeTranslationCode,
  onChange,
}: TranslationSwitcherProps) {
  const t = useTranslations("Header");

  return (
    <div className="flex items-center gap-1.5">
      <Book className="w-4 h-4 text-gray-500 flex-shrink-0" />
      <select
        value={activeTranslationCode}
        onChange={(e) => onChange(e.target.value)}
        disabled={translations.length === 0}
        aria-label={t("bibleVersion")}
        className="text-sm border border-gray-200 rounded-lg px-1.5 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">{t("bibleVersion")}</option>
        {translations.map((tr) => (
          <option key={tr.code} value={tr.code}>
            {tr.name} — {tr.short_name}
            {tr.year ? `, ${tr.year}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
