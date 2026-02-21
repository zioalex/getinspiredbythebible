"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { Globe } from "lucide-react";
import { routing } from "@/i18n/routing";

export const localeLabels: Record<string, string> = {
  en: "English",
  it: "Italiano",
  de: "Deutsch",
  es: "Español",
  fr: "Français",
  pt: "Português",
  ar: "العربية",
};

export default function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const handleChange = (newLocale: string) => {
    router.replace(pathname, { locale: newLocale });
  };

  return (
    <div className="flex items-center gap-1.5">
      <Globe className="w-4 h-4 text-gray-500" />
      <select
        value={locale}
        onChange={(e) => handleChange(e.target.value)}
        className="text-sm border border-gray-200 rounded-lg px-1.5 py-1.5 bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500"
      >
        {routing.locales.map((loc) => (
          <option key={loc} value={loc}>
            {localeLabels[loc]}
          </option>
        ))}
      </select>
    </div>
  );
}
