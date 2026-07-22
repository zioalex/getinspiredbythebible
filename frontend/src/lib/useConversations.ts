/**
 * useConversations — React state layer over the local conversation store.
 *
 * Holds the (reactive) list of saved conversations for the sidebar and exposes
 * action helpers that mutate the store and then refresh. Export/import glue
 * (encrypt + download, read + decrypt + merge) lives here because it ties the
 * store and the crypto module together.
 */

import { useCallback, useEffect, useState } from "react";
import {
  listConversations,
  renameConversation,
  deleteConversation,
  clearAll,
  exportAll,
  importAll,
  isStorageAvailable,
  StoredConversation,
  ConversationExport,
} from "./conversationStore";
import {
  encryptExport,
  decryptImport,
  isEncryptedEnvelope,
  EncryptedEnvelope,
} from "./conversationCrypto";

export interface UseConversationsResult {
  conversations: StoredConversation[];
  available: boolean;
  loading: boolean;
  refresh: () => Promise<void>;
  rename: (id: string, title: string) => Promise<void>;
  remove: (id: string) => Promise<void>;
  wipeAll: () => Promise<void>;
  /** Encrypt all history with a passphrase and trigger a file download. */
  exportEncrypted: (passphrase: string) => Promise<void>;
  /** Read + decrypt a file and merge it in. Returns conversations imported. */
  importEncrypted: (file: File, passphrase: string) => Promise<number>;
}

function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function exportFilename(): string {
  const stamp = new Date().toISOString().slice(0, 10);
  return `voxquieta-history-${stamp}.vqhist.json`;
}

export function useConversations(): UseConversationsResult {
  const [conversations, setConversations] = useState<StoredConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const available = isStorageAvailable();

  const refresh = useCallback(async () => {
    const list = await listConversations();
    setConversations(list);
    setLoading(false);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const rename = useCallback(
    async (id: string, title: string) => {
      await renameConversation(id, title);
      await refresh();
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      await refresh();
    },
    [refresh],
  );

  const wipeAll = useCallback(async () => {
    await clearAll();
    await refresh();
  }, [refresh]);

  const exportEncrypted = useCallback(async (passphrase: string) => {
    const snapshot = await exportAll();
    const envelope = await encryptExport(snapshot, passphrase);
    downloadJson(exportFilename(), envelope);
  }, []);

  const importEncrypted = useCallback(
    async (file: File, passphrase: string): Promise<number> => {
      const text = await file.text();
      const parsed = JSON.parse(text) as unknown;
      if (!isEncryptedEnvelope(parsed)) {
        throw new Error("This file is not a Vox Quieta history export");
      }
      const snapshot = await decryptImport<ConversationExport>(
        parsed as EncryptedEnvelope,
        passphrase,
      );
      const count = await importAll(snapshot);
      await refresh();
      return count;
    },
    [refresh],
  );

  return {
    conversations,
    available,
    loading,
    refresh,
    rename,
    remove,
    wipeAll,
    exportEncrypted,
    importEncrypted,
  };
}
