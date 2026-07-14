"use client";

import { useEffect, useRef, useState } from "react";
import {
  X,
  Plus,
  Trash2,
  Pencil,
  Check,
  Download,
  Upload,
  ShieldCheck,
  MessageSquare,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { useConversations } from "@/lib/useConversations";
import { DecryptionError } from "@/lib/conversationCrypto";

interface ConversationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewConversation: () => void;
  /** Bump from the parent after saving a message to refresh the list. */
  refreshSignal?: number;
}

type Panel = "none" | "export" | "import";

export default function ConversationSidebar({
  isOpen,
  onClose,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
  refreshSignal,
}: ConversationSidebarProps) {
  const t = useTranslations("History");
  const {
    conversations,
    available,
    refresh,
    rename,
    remove,
    wipeAll,
    exportEncrypted,
    importEncrypted,
  } = useConversations();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [panel, setPanel] = useState<Panel>("none");
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingFileRef = useRef<File | null>(null);

  // Refresh the list when the parent signals a save.
  useEffect(() => {
    if (refreshSignal !== undefined) void refresh();
  }, [refreshSignal, refresh]);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (isOpen) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [isOpen, onClose]);

  const resetPanel = () => {
    setPanel("none");
    setPassphrase("");
    setError(null);
    pendingFileRef.current = null;
  };

  const startEdit = (id: string, title: string) => {
    setEditingId(id);
    setEditValue(title);
  };

  const commitEdit = async () => {
    if (editingId && editValue.trim()) {
      await rename(editingId, editValue.trim());
    }
    setEditingId(null);
    setEditValue("");
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(t("confirmDelete"))) return;
    await remove(id);
    if (id === activeConversationId) onNewConversation();
  };

  const handleClearAll = async () => {
    if (!window.confirm(t("confirmClearAll"))) return;
    await wipeAll();
    onNewConversation();
  };

  const handleExport = async () => {
    setError(null);
    if (passphrase.length < 6) {
      setError(t("passphraseTooShort"));
      return;
    }
    setBusy(true);
    try {
      await exportEncrypted(passphrase);
      setStatus(t("exportDone"));
      resetPanel();
    } catch {
      setError(t("exportFailed"));
    } finally {
      setBusy(false);
    }
  };

  const handleFilePicked = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null;
    pendingFileRef.current = file;
    setError(null);
    // reset input so re-picking the same file fires change again
    e.target.value = "";
  };

  const handleImport = async () => {
    setError(null);
    const file = pendingFileRef.current;
    if (!file) {
      setError(t("chooseFile"));
      return;
    }
    if (!passphrase) {
      setError(t("passphraseRequired"));
      return;
    }
    setBusy(true);
    try {
      const count = await importEncrypted(file, passphrase);
      setStatus(t("importDone", { count }));
      resetPanel();
    } catch (err) {
      if (err instanceof DecryptionError) {
        setError(t("wrongPassphrase"));
      } else {
        setError(t("importFailed"));
      }
    } finally {
      setBusy(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex"
      role="dialog"
      aria-modal="true"
      aria-label={t("title")}
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <aside className="relative flex h-full w-80 max-w-[85vw] flex-col bg-white shadow-xl dark:bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3 dark:border-gray-700">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {t("title")}
          </h2>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
            aria-label={t("close")}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <button
          onClick={() => {
            onNewConversation();
            onClose();
          }}
          className="mx-3 mt-3 flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-800 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-100 dark:hover:bg-gray-800"
        >
          <Plus className="h-4 w-4" />
          {t("newConversation")}
        </button>

        {/* Conversation list */}
        <div className="mt-3 flex-1 overflow-y-auto px-2">
          {!available && (
            <p className="px-2 py-4 text-xs text-gray-500 dark:text-gray-400">
              {t("storageUnavailable")}
            </p>
          )}
          {available && conversations.length === 0 && (
            <p className="px-2 py-4 text-xs text-gray-500 dark:text-gray-400">
              {t("empty")}
            </p>
          )}
          <ul className="space-y-1">
            {conversations.map((conv) => (
              <li
                key={conv.id}
                className={`group flex items-center gap-1 rounded-lg px-2 py-2 text-sm ${
                  conv.id === activeConversationId
                    ? "bg-indigo-50 dark:bg-indigo-900/30"
                    : "hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}
              >
                {editingId === conv.id ? (
                  <>
                    <input
                      autoFocus
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void commitEdit();
                        if (e.key === "Escape") setEditingId(null);
                      }}
                      className="min-w-0 flex-1 rounded border border-gray-300 bg-white px-1 py-0.5 text-sm dark:border-gray-600 dark:bg-gray-800"
                    />
                    <button
                      onClick={() => void commitEdit()}
                      className="rounded p-1 text-gray-500 hover:text-indigo-600"
                      aria-label={t("saveTitle")}
                    >
                      <Check className="h-4 w-4" />
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => {
                        onSelectConversation(conv.id);
                        onClose();
                      }}
                      className="flex min-w-0 flex-1 items-center gap-2 text-left"
                    >
                      <MessageSquare className="h-4 w-4 flex-shrink-0 text-gray-400" />
                      <span className="truncate text-gray-800 dark:text-gray-100">
                        {conv.title || t("untitled")}
                      </span>
                    </button>
                    <button
                      onClick={() => startEdit(conv.id, conv.title)}
                      className="rounded p-1 text-gray-400 opacity-0 hover:text-indigo-600 group-hover:opacity-100"
                      aria-label={t("rename")}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      onClick={() => void handleDelete(conv.id)}
                      className="rounded p-1 text-gray-400 opacity-0 hover:text-red-600 group-hover:opacity-100"
                      aria-label={t("delete")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>

        {/* Footer: privacy note + data controls */}
        <div className="border-t border-gray-200 px-3 py-3 dark:border-gray-700">
          <p className="mb-2 flex items-start gap-1.5 text-[11px] leading-snug text-gray-500 dark:text-gray-400">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-green-600" />
            {t("privacyNote")}
          </p>

          {panel === "none" && (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => {
                  setStatus(null);
                  setPanel("export");
                }}
                disabled={!available}
                className="flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                <Download className="h-3.5 w-3.5" />
                {t("export")}
              </button>
              <button
                onClick={() => {
                  setStatus(null);
                  setPanel("import");
                }}
                disabled={!available}
                className="flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
              >
                <Upload className="h-3.5 w-3.5" />
                {t("import")}
              </button>
              <button
                onClick={() => void handleClearAll()}
                disabled={!available || conversations.length === 0}
                className="flex items-center gap-1 rounded-md border border-red-200 px-2 py-1 text-xs text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:hover:bg-red-900/20"
              >
                <Trash2 className="h-3.5 w-3.5" />
                {t("clearAll")}
              </button>
            </div>
          )}

          {(panel === "export" || panel === "import") && (
            <div className="space-y-2">
              <p className="text-xs text-gray-600 dark:text-gray-300">
                {panel === "export" ? t("exportHint") : t("importHint")}
              </p>
              {panel === "import" && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".json,application/json"
                    onChange={handleFilePicked}
                    className="block w-full text-xs text-gray-600 file:mr-2 file:rounded file:border-0 file:bg-gray-100 file:px-2 file:py-1 file:text-xs dark:text-gray-300 dark:file:bg-gray-800"
                  />
                </>
              )}
              <input
                type="password"
                value={passphrase}
                onChange={(e) => setPassphrase(e.target.value)}
                placeholder={t("passphrasePlaceholder")}
                className="w-full rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-600 dark:bg-gray-800"
              />
              {error && <p className="text-xs text-red-600">{error}</p>}
              <div className="flex gap-2">
                <button
                  onClick={() =>
                    panel === "export"
                      ? void handleExport()
                      : void handleImport()
                  }
                  disabled={busy}
                  className="rounded-md bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {panel === "export" ? t("export") : t("import")}
                </button>
                <button
                  onClick={resetPanel}
                  className="rounded-md border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                >
                  {t("cancel")}
                </button>
              </div>
            </div>
          )}

          {status && panel === "none" && (
            <p className="mt-2 text-xs text-green-600">{status}</p>
          )}
        </div>
      </aside>
    </div>
  );
}
