"use client";

import { useState, useRef, useEffect } from "react";
import {
  Menu,
  History as HistoryIcon,
  MapPin,
  Info,
  Heart,
  Volume2,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { localeLabels } from "@/i18n/localeLabels";
import TranslationSwitcher from "@/components/TranslationSwitcher";
import { Link } from "@/i18n/navigation";
import { donateUrl } from "@/lib/donateUrl";
import type { TranslationInfo } from "@/lib/api";
import { useServerConfig } from "@/lib/serverConfig";
import { setShowListen, useShowListenPreference } from "@/lib/ttsPreference";
import {
  setOnlineVoiceConsent,
  useOnlineVoiceConsent,
} from "@/lib/onlineVoiceConsent";
import { stop } from "@/lib/speech";
import { useSpeechAvailability } from "@/lib/useSpeechAvailability";

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
  const tFooter = useTranslations("Footer");
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const locale = useLocale();
  const showListen = useShowListenPreference();
  const { ttsEnabled } = useServerConfig();
  // BITB-210: a no-op (never touches speechSynthesis) while the preference or flag is off.
  const { voice, onlineVoice, availability, ready } = useSpeechAvailability(
    locale,
    ttsEnabled && showListen,
  );
  const consent = useOnlineVoiceConsent();
  const onlineAllowed = consent === "granted";
  // The toggle is only meaningful when the browser has online voices; an offline voice wins
  // regardless, but the choice stays revocable.
  const showOnlineToggle = ready && onlineVoice !== null;
  const showNoVoiceNote = ready && availability === "none";

  const toggleOnlineVoices = () => {
    if (onlineAllowed) {
      setOnlineVoiceConsent("denied");
      // Revoking must silence an online voice that is speaking or paused.
      if (!voice) stop();
    } else {
      setOnlineVoiceConsent("granted");
    }
  };

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
            <HistoryIcon className="w-4 h-4 shrink-0" />
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

          {/* BITB-119: show/hide the Listen (read aloud) button on answers */}
          <button
            type="button"
            role="switch"
            aria-checked={showListen}
            onClick={() => setShowListen(!showListen)}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Volume2 className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span className="flex-1 text-left">{t("showListenButton")}</span>
            <span
              aria-hidden="true"
              className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                showListen ? "bg-primary-600" : "bg-gray-300"
              }`}
            >
              <span
                className={`h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                  showListen ? "translate-x-4" : "translate-x-0.5"
                }`}
              />
            </span>
          </button>

          {/* BITB-210: revocable per-device consent to online (cloud) voices */}
          {showOnlineToggle && (
            <button
              type="button"
              role="switch"
              aria-checked={onlineAllowed}
              onClick={toggleOnlineVoices}
              className="w-full flex items-center gap-3 px-3 py-2 min-h-[44px] text-sm text-gray-700 hover:bg-gray-50 transition-colors"
            >
              <span className="w-4 shrink-0" aria-hidden="true" />
              <span className="flex-1 text-left">{t("allowOnlineVoices")}</span>
              <span
                aria-hidden="true"
                className={`inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
                  onlineAllowed ? "bg-primary-600" : "bg-gray-300"
                }`}
              >
                <span
                  className={`h-4 w-4 rounded-full bg-white shadow-sm transition-transform ${
                    onlineAllowed ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </span>
            </button>
          )}

          {/* BITB-210: explain the missing voice instead of hiding Listen silently */}
          {showNoVoiceNote && (
            <p
              role="status"
              aria-live="polite"
              className="px-3 pb-2 text-xs text-gray-500"
            >
              {t("noVoiceForLanguage", {
                language: localeLabels[locale] ?? locale,
              })}
            </p>
          )}

          <div className="border-t border-gray-100 my-1" />

          <button
            onClick={() => {
              onOpenChurchFinder();
              setOpen(false);
            }}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <MapPin className="w-4 h-4 shrink-0" />
            {t("searchCommunity")}
          </button>

          <div className="border-t border-gray-100 my-1" />

          <Link
            href="/about"
            onClick={() => setOpen(false)}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Info className="w-4 h-4 shrink-0" />
            {tFooter("about")}
          </Link>

          <a
            href={donateUrl("web-menu")}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
            className="w-full flex items-center gap-3 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
          >
            <Heart className="w-4 h-4 shrink-0" aria-hidden="true" />
            {tFooter("supportUs")}
          </a>
        </div>
      )}
    </div>
  );
}
