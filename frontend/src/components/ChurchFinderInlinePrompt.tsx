"use client";

import { MapPin, X } from "lucide-react";
import { useTranslations } from "next-intl";

interface ChurchFinderInlinePromptProps {
  onFindChurch: () => void;
  onDismiss: () => void;
}

export default function ChurchFinderInlinePrompt({
  onFindChurch,
  onDismiss,
}: ChurchFinderInlinePromptProps) {
  const t = useTranslations("ChurchFinder");

  return (
    <div className="flex justify-center my-4">
      <div className="inline-flex items-center gap-3 px-4 py-3 bg-linear-to-r from-teal-50 to-blue-50 border border-teal-100 rounded-2xl shadow-xs max-w-md">
        <MapPin className="w-5 h-5 text-teal-500 shrink-0" />
        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          <p className="text-sm text-gray-600">{t("inlineText")}</p>
          <button
            onClick={onFindChurch}
            className="text-sm font-medium text-teal-600 hover:text-teal-700 hover:underline transition-colors whitespace-nowrap"
          >
            {t("inlineCta")}
          </button>
        </div>
        <button
          onClick={onDismiss}
          className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-full transition-colors shrink-0"
          aria-label={t("dismiss")}
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
