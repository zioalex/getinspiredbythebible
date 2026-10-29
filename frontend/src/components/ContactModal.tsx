"use client";

import { useEffect } from "react";
import { MessageSquare, X } from "lucide-react";
import { useTranslations } from "next-intl";
import ContactForm from "./ContactForm";

interface ContactModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Below lg the chat page no longer renders the inline "Get in Touch" form
// under the composer (accidental taps, #1224); the main menu opens it here.
export default function ContactModal({ isOpen, onClose }: ContactModalProps) {
  const t = useTranslations("Contact");

  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
        aria-hidden="true"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="contact-modal-title"
        className="relative bg-white w-full max-w-md max-h-[90dvh] overflow-y-auto rounded-t-2xl sm:rounded-2xl shadow-xl p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] sm:p-6"
      >
        <div className="flex items-center justify-between gap-2 mb-4">
          <h2
            id="contact-modal-title"
            className="flex items-center gap-2 text-lg font-semibold text-gray-800"
          >
            <MessageSquare className="w-5 h-5 shrink-0" aria-hidden="true" />
            {t("getInTouch")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("close")}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <ContactForm embedded />
      </div>
    </div>
  );
}
