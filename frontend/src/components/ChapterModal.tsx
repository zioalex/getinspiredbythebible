"use client";

import { useEffect } from "react";
import {
  X,
  BookOpen,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { Verse } from "@/lib/api";

interface ChapterModalProps {
  isOpen: boolean;
  onClose: () => void;
  book: string;
  localized_book?: string;
  chapter: number;
  verses?: Verse[];
  highlightVerse?: number;
  isLoading?: boolean;
  translationName?: string;
  error?: boolean;
  onPrevChapter?: () => void;
  onNextChapter?: () => void;
  hasPrevChapter?: boolean;
  hasNextChapter?: boolean;
}

export default function ChapterModal({
  isOpen,
  onClose,
  book,
  localized_book,
  chapter,
  verses,
  highlightVerse,
  isLoading = false,
  translationName,
  error = false,
  onPrevChapter,
  onNextChapter,
  hasPrevChapter = false,
  hasNextChapter = false,
}: ChapterModalProps) {
  const t = useTranslations("ChapterModal");

  // Close on Escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };

    if (isOpen) {
      document.addEventListener("keydown", handleEscape);
      document.body.style.overflow = "hidden";
    }

    return () => {
      document.removeEventListener("keydown", handleEscape);
      document.body.style.overflow = "unset";
    };
  }, [isOpen, onClose]);

  // Scroll to highlighted verse
  useEffect(() => {
    if (isOpen && highlightVerse && verses && verses.length > 0) {
      const timer = setTimeout(() => {
        const element = document.getElementById(`verse-${highlightVerse}`);
        element?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isOpen, highlightVerse, verses]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white sm:rounded-2xl shadow-2xl w-full max-w-2xl max-h-screen sm:max-h-[85vh] flex flex-col sm:m-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-gray-200 bg-primary-50/50">
          <div className="flex items-center gap-3">
            <BookOpen className="w-6 h-6 sm:w-7 sm:h-7 text-primary-600" />
            <div>
              <h2 className="text-xl sm:text-2xl font-serif font-bold text-gray-800">
                {localized_book ? localized_book : book} {chapter}
              </h2>
              <p className="text-sm text-gray-500">
                {verses
                  ? t("verseCount", { count: verses.length })
                  : t("noVerses")}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <X className="w-6 h-6 text-gray-600" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary-600" />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-gray-500">
              <AlertCircle className="w-10 h-10 text-red-400" />
              <p className="text-center text-sm">
                Sorry, this chapter could not be loaded. Please try again.
              </p>
            </div>
          ) : verses && verses.length > 0 ? (
            <div className="space-y-1">
              {verses.map((verse) => (
                <div
                  key={verse.verse}
                  id={`verse-${verse.verse}`}
                  className={`group scroll-mt-6 transition-all py-2 ${
                    highlightVerse === verse.verse
                      ? "bg-amber-100 -mx-3 px-3 rounded-lg border-l-4 border-amber-500"
                      : "hover:bg-gray-50 -mx-3 px-3 rounded-lg"
                  }`}
                >
                  <div className="flex gap-3">
                    <span
                      className={`flex-shrink-0 w-8 text-right text-sm font-bold ${
                        highlightVerse === verse.verse
                          ? "text-amber-700"
                          : "text-gray-400 group-hover:text-gray-600"
                      }`}
                    >
                      {verse.verse}
                    </span>
                    <p
                      className={`flex-1 leading-7 text-[15px] ${
                        highlightVerse === verse.verse
                          ? "text-gray-900 font-medium"
                          : "text-gray-700"
                      }`}
                      style={{ fontFamily: "Georgia, serif" }}
                    >
                      {verse.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center py-12 text-gray-500">
              {t("noVerses")}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-200 px-6 py-4 flex items-center justify-between gap-4">
          <button
            onClick={onPrevChapter}
            disabled={!hasPrevChapter || !onPrevChapter}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary-600 hover:text-primary-800 hover:bg-primary-50 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-4 h-4" />
            Previous
          </button>
          <p className="text-xs text-gray-500 text-center">
            {translationName || t("defaultTranslation")}
          </p>
          <button
            onClick={onNextChapter}
            disabled={!hasNextChapter || !onNextChapter}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-primary-600 hover:text-primary-800 hover:bg-primary-50 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
