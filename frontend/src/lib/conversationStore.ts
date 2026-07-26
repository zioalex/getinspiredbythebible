/**
 * conversationStore — privacy-first, browser-local conversation history.
 *
 * All chat history for the web client lives here, in the browser's IndexedDB.
 * It is NEVER sent to or stored on the server. This mirrors the Android app's
 * local Room database (see
 * android/app/schemas/org.voxquieta.app.data.local.VoxQuietaDatabase/1.json)
 * so the two clients share a compatible shape for a future common export format.
 *
 * Every operation is defensive: when IndexedDB is unavailable (SSR, private
 * browsing, blocked storage) the functions resolve to empty/no-op values rather
 * than throwing, matching the localStorage guard style in src/lib/api.ts.
 */

const DB_NAME = "voxquieta";
const DB_VERSION = 1;
const CONVERSATIONS_STORE = "conversations";
const MESSAGES_STORE = "messages";

/** Keep local storage bounded — prune the least-recently-updated beyond this. */
export const MAX_CONVERSATIONS = 200;

export interface StoredConversation {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

export interface StoredMessage {
  id: string;
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  /** Verse references cited by an assistant message (web analog of Android versesJson). */
  versesCited: string[];
  createdAt: number;
}

/** Portable snapshot used by export/import (before encryption). */
export interface ConversationExport {
  version: number;
  exportedAt: number;
  conversations: StoredConversation[];
  messages: StoredMessage[];
}

export const EXPORT_VERSION = 1;

/** True when IndexedDB can be used in the current environment. */
export function isStorageAvailable(): boolean {
  try {
    return typeof indexedDB !== "undefined" && indexedDB !== null;
  } catch {
    return false;
  }
}

function promisifyRequest<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function txDone(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error);
  });
}

let dbPromise: Promise<IDBDatabase> | null = null;

function openDb(): Promise<IDBDatabase> {
  if (!isStorageAvailable()) {
    return Promise.reject(new Error("IndexedDB unavailable"));
  }
  if (!dbPromise) {
    dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(CONVERSATIONS_STORE)) {
          const store = db.createObjectStore(CONVERSATIONS_STORE, {
            keyPath: "id",
          });
          store.createIndex("updatedAt", "updatedAt", { unique: false });
        }
        if (!db.objectStoreNames.contains(MESSAGES_STORE)) {
          const store = db.createObjectStore(MESSAGES_STORE, { keyPath: "id" });
          store.createIndex("conversationId", "conversationId", {
            unique: false,
          });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    // Don't cache a rejected promise: allow a later retry.
    dbPromise.catch(() => {
      dbPromise = null;
    });
  }
  return dbPromise;
}

/** All conversations, most-recently-updated first. Empty on any failure. */
export async function listConversations(): Promise<StoredConversation[]> {
  try {
    const db = await openDb();
    const tx = db.transaction(CONVERSATIONS_STORE, "readonly");
    const all = await promisifyRequest(
      tx.objectStore(CONVERSATIONS_STORE).getAll() as IDBRequest<
        StoredConversation[]
      >,
    );
    return all.sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

export async function getConversation(
  id: string,
): Promise<StoredConversation | null> {
  try {
    const db = await openDb();
    const tx = db.transaction(CONVERSATIONS_STORE, "readonly");
    const result = await promisifyRequest(
      tx.objectStore(CONVERSATIONS_STORE).get(id) as IDBRequest<
        StoredConversation | undefined
      >,
    );
    return result ?? null;
  } catch {
    return null;
  }
}

/** Messages for a conversation in chronological order. Empty on any failure. */
export async function getMessages(
  conversationId: string,
): Promise<StoredMessage[]> {
  try {
    const db = await openDb();
    const tx = db.transaction(MESSAGES_STORE, "readonly");
    const index = tx.objectStore(MESSAGES_STORE).index("conversationId");
    const all = await promisifyRequest(
      index.getAll(conversationId) as IDBRequest<StoredMessage[]>,
    );
    return all.sort((a, b) => a.createdAt - b.createdAt);
  } catch {
    return [];
  }
}

/** Insert or update a conversation row. No-op on failure. */
export async function saveConversation(
  conversation: StoredConversation,
): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(CONVERSATIONS_STORE, "readwrite");
    tx.objectStore(CONVERSATIONS_STORE).put(conversation);
    await txDone(tx);
    await pruneOldConversations();
  } catch {
    // ignore: history is best-effort
  }
}

/**
 * Append a message and bump its conversation's updatedAt in one transaction.
 * No-op on failure.
 */
export async function appendMessage(message: StoredMessage): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(
      [MESSAGES_STORE, CONVERSATIONS_STORE],
      "readwrite",
    );
    tx.objectStore(MESSAGES_STORE).put(message);
    const convStore = tx.objectStore(CONVERSATIONS_STORE);
    const conv = (await promisifyRequest(
      convStore.get(message.conversationId) as IDBRequest<
        StoredConversation | undefined
      >,
    )) as StoredConversation | undefined;
    if (conv) {
      conv.updatedAt = Math.max(conv.updatedAt, message.createdAt);
      convStore.put(conv);
    }
    await txDone(tx);
  } catch {
    // ignore
  }
}

export async function renameConversation(
  id: string,
  title: string,
): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(CONVERSATIONS_STORE, "readwrite");
    const store = tx.objectStore(CONVERSATIONS_STORE);
    const conv = (await promisifyRequest(
      store.get(id) as IDBRequest<StoredConversation | undefined>,
    )) as StoredConversation | undefined;
    if (conv) {
      conv.title = title;
      conv.updatedAt = Date.now();
      store.put(conv);
    }
    await txDone(tx);
  } catch {
    // ignore
  }
}

/** Delete a conversation and all of its messages. No-op on failure. */
export async function deleteConversation(id: string): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(
      [MESSAGES_STORE, CONVERSATIONS_STORE],
      "readwrite",
    );
    tx.objectStore(CONVERSATIONS_STORE).delete(id);
    const index = tx.objectStore(MESSAGES_STORE).index("conversationId");
    const keys = await promisifyRequest(
      index.getAllKeys(id) as IDBRequest<IDBValidKey[]>,
    );
    const msgStore = tx.objectStore(MESSAGES_STORE);
    for (const key of keys) {
      msgStore.delete(key);
    }
    await txDone(tx);
  } catch {
    // ignore
  }
}

/** Wipe all local conversation history. No-op on failure. */
export async function clearAll(): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(
      [MESSAGES_STORE, CONVERSATIONS_STORE],
      "readwrite",
    );
    tx.objectStore(CONVERSATIONS_STORE).clear();
    tx.objectStore(MESSAGES_STORE).clear();
    await txDone(tx);
  } catch {
    // ignore
  }
}

/** Snapshot everything for export. Empty snapshot on failure. */
export async function exportAll(): Promise<ConversationExport> {
  const [conversations, db] = await Promise.all([
    listConversations(),
    openDb().catch(() => null),
  ]);
  let messages: StoredMessage[] = [];
  if (db) {
    try {
      const tx = db.transaction(MESSAGES_STORE, "readonly");
      messages = await promisifyRequest(
        tx.objectStore(MESSAGES_STORE).getAll() as IDBRequest<StoredMessage[]>,
      );
    } catch {
      messages = [];
    }
  }
  return {
    version: EXPORT_VERSION,
    exportedAt: Date.now(),
    conversations,
    messages,
  };
}

/**
 * Merge an exported snapshot back into local storage. Existing rows with the
 * same id are overwritten. Returns the number of conversations imported.
 */
export async function importAll(data: ConversationExport): Promise<number> {
  if (
    !data ||
    !Array.isArray(data.conversations) ||
    !Array.isArray(data.messages)
  ) {
    throw new Error("Invalid conversation export");
  }
  try {
    const db = await openDb();
    const tx = db.transaction(
      [MESSAGES_STORE, CONVERSATIONS_STORE],
      "readwrite",
    );
    const convStore = tx.objectStore(CONVERSATIONS_STORE);
    const msgStore = tx.objectStore(MESSAGES_STORE);
    for (const conv of data.conversations) {
      convStore.put(conv);
    }
    for (const msg of data.messages) {
      msgStore.put(msg);
    }
    await txDone(tx);
    await pruneOldConversations();
    return data.conversations.length;
  } catch (err) {
    throw err instanceof Error ? err : new Error("Import failed");
  }
}

/**
 * Idempotently persist a whole conversation: upsert its row (preserving the
 * original createdAt) and replace all of its messages in one transaction.
 * Message ids are derived from the conversation id + index so repeated saves of
 * the same in-memory thread never duplicate rows. No-op on failure.
 */
export async function saveFullConversation(
  id: string,
  title: string,
  messages: Array<{
    role: "user" | "assistant";
    content: string;
    versesCited?: string[];
  }>,
): Promise<void> {
  try {
    const db = await openDb();
    const now = Date.now();
    const tx = db.transaction(
      [MESSAGES_STORE, CONVERSATIONS_STORE],
      "readwrite",
    );
    const convStore = tx.objectStore(CONVERSATIONS_STORE);
    const msgStore = tx.objectStore(MESSAGES_STORE);

    const existing = (await promisifyRequest(
      convStore.get(id) as IDBRequest<StoredConversation | undefined>,
    )) as StoredConversation | undefined;
    convStore.put({
      id,
      title,
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
    });

    // Replace this conversation's messages wholesale.
    const oldKeys = await promisifyRequest(
      msgStore.index("conversationId").getAllKeys(id) as IDBRequest<
        IDBValidKey[]
      >,
    );
    for (const key of oldKeys) {
      msgStore.delete(key);
    }
    messages.forEach((m, i) => {
      msgStore.put({
        id: `${id}:${i}`,
        conversationId: id,
        role: m.role,
        content: m.content,
        versesCited: m.versesCited ?? [],
        createdAt: now + i,
      });
    });

    await txDone(tx);
    await pruneOldConversations();
  } catch {
    // ignore: history is best-effort
  }
}

/** Drop the least-recently-updated conversations beyond MAX_CONVERSATIONS. */
async function pruneOldConversations(): Promise<void> {
  try {
    const conversations = await listConversations();
    if (conversations.length <= MAX_CONVERSATIONS) return;
    const doomed = conversations.slice(MAX_CONVERSATIONS);
    for (const conv of doomed) {
      await deleteConversation(conv.id);
    }
  } catch {
    // ignore
  }
}

/** Test-only: forget the cached DB handle so a fresh open is forced. */
export function __resetDbCache(): void {
  dbPromise = null;
}
