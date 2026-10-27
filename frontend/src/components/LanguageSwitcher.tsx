"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { ChevronDown, Globe } from "lucide-react";
import { routing } from "@/i18n/routing";
import { localeLabels } from "@/i18n/localeLabels";

export { localeLabels };

// Same structure as TranslationSwitcher (#1223): a styled, truncating label
// with a transparent native <select> stretched over it, so the control can
// never grow wider than its container and the OS picker is preserved.
export default function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const handleChange = (newLocale: string) => {
    router.replace(pathname, { locale: newLocale });
  };

  return (
    <div className="flex w-full min-w-0 items-center gap-1.5">
      <Globe className="w-4 h-4 text-gray-500 shrink-0" aria-hidden="true" />
      <div
        data-testid="language-switcher-control"
        className="relative flex min-w-0 max-w-full flex-1 items-center gap-1 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-600 focus-within:ring-2 focus-within:ring-primary-500"
      >
        <span aria-hidden="true" className="min-w-0 flex-1 truncate">
          {localeLabels[locale] ?? locale}
        </span>
        <ChevronDown
          className="w-3.5 h-3.5 shrink-0 text-gray-400"
          aria-hidden="true"
        />
        {/* text-base (16px) keeps iOS Safari from zooming on focus. */}
        <select
          value={locale}
          onChange={(e) => handleChange(e.target.value)}
          className="absolute inset-0 h-full w-full max-w-full cursor-pointer opacity-0 text-base"
        >
          {routing.locales.map((loc) => (
            <option key={loc} value={loc}>
              {localeLabels[loc]}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
