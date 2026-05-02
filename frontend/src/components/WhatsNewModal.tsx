"use client";

import { useState, useEffect } from "react";
import { X } from "lucide-react";
import { useTranslations } from "next-intl";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link } from "@/i18n/navigation";

const STORAGE_KEY = "vq:lastSeenVersion";

interface ChangelogEntry {
  version: string | null;
  date?: string | null;
  body?: string;
}

export default function WhatsNewModal() {
  const t = useTranslations("WhatsNew");
  const [entry, setEntry] = useState<ChangelogEntry | null>(null);

  useEffect(() => {
    // Guard: only runs client-side
    if (typeof window === "undefined") return;

    fetch("/changelog.json")
      .then((r) => {
        if (!r.ok) return null;
        return r.json();
      })
      .then((data: ChangelogEntry | null) => {
        if (!data) return;
        if (!data.version) return;

        const lastSeen = localStorage.getItem(STORAGE_KEY);

        if (lastSeen === null) {
          // First-ever visit: silently record current version so new users
          // are not greeted with a "what's new" popup they have no context for.
          localStorage.setItem(STORAGE_KEY, data.version);
          return;
        }

        if (lastSeen !== data.version) {
          setEntry(data);
        }
      })
      .catch(() => {
        // changelog.json is optional — ignore fetch errors silently
      });
  }, []);

  if (!entry) return null;

  function handleDismiss() {
    if (entry?.version) {
      localStorage.setItem(STORAGE_KEY, entry.version);
    }
    setEntry(null);
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("title")}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
    >
      <div className="relative w-full max-w-lg rounded-2xl bg-white shadow-2xl p-6 max-h-[80vh] flex flex-col">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">{t("title")}</h2>
            {entry.version && (
              <p className="text-sm text-gray-500 mt-0.5">
                {t("versionLabel", { version: entry.version })}
              </p>
            )}
          </div>
          <button
            onClick={handleDismiss}
            aria-label={t("dismiss")}
            className="ml-4 p-1 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {entry.body && (
          <div className="overflow-y-auto flex-1 prose prose-sm prose-gray max-w-none mb-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {entry.body}
            </ReactMarkdown>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          <Link
            href="/changelog"
            className="text-sm text-blue-600 hover:underline"
          >
            {t("viewFullChangelog")}
          </Link>
          <button
            onClick={handleDismiss}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
          >
            {t("dismiss")}
          </button>
        </div>
      </div>
    </div>
  );
}
