"use client";

import { Globe, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { localeLabels } from "@/components/LanguageSwitcher";

interface LanguageSwitchSuggestionProps {
  /** Suggested locale code (e.g. "it"). */
  suggestedLocale: string;
  onSwitch: () => void;
  onDismiss: () => void;
}

export default function LanguageSwitchSuggestion({
  suggestedLocale,
  onSwitch,
  onDismiss,
}: LanguageSwitchSuggestionProps) {
  const t = useTranslations("Chat");
  const language = localeLabels[suggestedLocale] ?? suggestedLocale;

  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 sm:gap-3 px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-xl mt-3">
      <div className="flex items-center gap-3">
        <Globe className="w-5 h-5 text-indigo-600 flex-shrink-0" />
        <p className="text-sm text-indigo-800">
          {t("languageSwitchSuggestion", { language })}
        </p>
      </div>
      <div className="flex items-center gap-2 self-end sm:self-auto">
        <button
          onClick={onSwitch}
          className="px-3 py-1.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors"
        >
          {t("languageSwitchAction")}
        </button>
        <button
          onClick={onDismiss}
          className="p-1.5 text-indigo-600 hover:bg-indigo-100 rounded-lg transition-colors"
          aria-label={t("languageSwitchDismiss")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
