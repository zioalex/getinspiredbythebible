"use client";

import { useEffect, useRef } from "react";
import { useTranslations } from "next-intl";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface OnlineVoiceConsentDialogProps {
  onAllow: () => void;
  /** "Not now", Esc and a backdrop click all decline. */
  onDecline: () => void;
}

/**
 * BITB-210: one-time, per-device opt-in before the Listen button uses an online voice. Says
 * plainly that the answer text goes to the browser's speech service, and that offline voices
 * never do. Focus-trapped; Esc is "Not now".
 */
export default function OnlineVoiceConsentDialog({
  onAllow,
  onDecline,
}: OnlineVoiceConsentDialogProps) {
  const t = useTranslations("Chat");
  const dialogRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<Element | null>(null);

  useEffect(() => {
    previouslyFocused.current = document.activeElement;
    dialogRef.current?.focus();

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onDecline();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previouslyFocused.current instanceof HTMLElement) {
        previouslyFocused.current.focus();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("onlineVoicesDialogTitle")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onDecline();
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        className="relative w-full max-w-md rounded-2xl bg-white shadow-2xl p-6 focus:outline-hidden"
      >
        <h2 className="text-xl font-bold text-gray-900 mb-3">
          {t("onlineVoicesDialogTitle")}
        </h2>
        <p className="text-gray-600 leading-relaxed mb-6">
          {t("onlineVoicesDialogBody")}
        </p>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onDecline}
            className="min-h-[44px] px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-800 transition-colors"
          >
            {t("onlineVoicesNotNow")}
          </button>
          <button
            type="button"
            onClick={onAllow}
            className="min-h-[44px] px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
          >
            {t("allowOnlineVoices")}
          </button>
        </div>
      </div>
    </div>
  );
}
