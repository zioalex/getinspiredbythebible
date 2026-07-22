"use client";

import { useState, useRef, useEffect } from "react";
import { Menu, History as HistoryIcon, MapPin } from "lucide-react";
import { useTranslations } from "next-intl";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import TranslationSwitcher from "@/components/TranslationSwitcher";
import type { TranslationInfo } from "@/lib/api";

interface MainMenuProps {
  onOpenHistory: () => void;
  onOpenChurchFinder: () => void;
  translations: TranslationInfo[];
  activeTranslationCode: string;
  onSelectTranslation: (code: string) => void;
}

export default function MainMenu({
  onOpenHistory,
  onOpenChurchFinder,
  translations,
  activeTranslationCode,
  onSelectTranslation,
}: MainMenuProps) {
  const t = useTranslations("Chat");
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={menuRef} className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        title={t("mainMenuLabel")}
        aria-label={t("mainMenuLabel")}
        className="flex items-center justify-center rounded-full border border-primary-200 p-2 text-primary-600 hover:bg-primary-50 transition-colors"
      >
        <Menu className="w-5 h-5" />
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1">
          <button
            onClick={() => {
              onOpenHistory();
              setOpen(false);
            }}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <HistoryIcon className="w-4 h-4 flex-shrink-0" />
            {t("historyTitle")}
          </button>

          <div className="border-t border-gray-100 my-1" />

          <div className="px-3 py-2" onChange={() => setOpen(false)}>
            <p className="text-xs font-medium text-gray-500 mb-1">
              {t("changeLanguage")}
            </p>
            <LanguageSwitcher />
          </div>

          <div className="px-3 py-2" onChange={() => setOpen(false)}>
            <p className="text-xs font-medium text-gray-500 mb-1">
              {t("changeBibleVersion")}
            </p>
            <TranslationSwitcher
              translations={translations}
              activeTranslationCode={activeTranslationCode}
              onChange={onSelectTranslation}
            />
          </div>

          <div className="border-t border-gray-100 my-1" />

          <button
            onClick={() => {
              onOpenChurchFinder();
              setOpen(false);
            }}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <MapPin className="w-4 h-4 flex-shrink-0" />
            {t("searchCommunity")}
          </button>
        </div>
      )}
    </div>
  );
}
