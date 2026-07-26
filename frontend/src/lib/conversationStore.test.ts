import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach } from "vitest";
import {
  isStorageAvailable,
  listConversations,
  getConversation,
  getMessages,
  saveConversation,
  appendMessage,
  saveFullConversation,
  renameConversation,
  deleteConversation,
  clearAll,
  exportAll,
  importAll,
  __resetDbCache,
} from "./conversationStore";

describe("conversationStore", () => {
  beforeEach(async () => {
    __resetDbCache();
    await clearAll();
  });

  it("reports storage as available under fake-indexeddb", () => {
    expect(isStorageAvailable()).toBe(true);
  });

  it("saves and lists conversations most-recent-first", async () => {
    await saveConversation({
      id: "a",
      title: "Older",
      createdAt: 1,
      updatedAt: 100,
    });
    await saveConversation({
      id: "b",
      title: "Newer",
      createdAt: 2,
      updatedAt: 200,
    });
    const list = await listConversations();
    expect(list.map((c) => c.id)).toEqual(["b", "a"]);
  });

  it("appends messages and bumps the conversation updatedAt", async () => {
    await saveConversation({
      id: "a",
      title: "Chat",
      createdAt: 1,
      updatedAt: 1,
    });
    await appendMessage({
      id: "a:0",
      conversationId: "a",
      role: "user",
      content: "hi",
      versesCited: [],
      createdAt: 500,
    });
    const msgs = await getMessages("a");
    expect(msgs).toHaveLength(1);
    expect(msgs[0].content).toBe("hi");
    const conv = await getConversation("a");
    expect(conv?.updatedAt).toBe(500);
  });

  it("saveFullConversation is idempotent (no duplicate messages)", async () => {
    const messages = [
      { role: "user" as const, content: "one" },
      {
        role: "assistant" as const,
        content: "two",
        versesCited: ["John 3:16"],
      },
    ];
    await saveFullConversation("c", "Title", messages);
    await saveFullConversation("c", "Title", messages);
    const stored = await getMessages("c");
    expect(stored).toHaveLength(2);
    expect(stored.map((m) => m.content)).toEqual(["one", "two"]);
    expect(stored[1].versesCited).toEqual(["John 3:16"]);
  });

  it("saveFullConversation preserves createdAt across resaves", async () => {
    await saveFullConversation("c", "T", [{ role: "user", content: "x" }]);
    const first = await getConversation("c");
    await new Promise((r) => setTimeout(r, 5));
    await saveFullConversation("c", "T2", [{ role: "user", content: "x" }]);
    const second = await getConversation("c");
    expect(second?.createdAt).toBe(first?.createdAt);
    expect(second?.title).toBe("T2");
  });

  it("renames a conversation", async () => {
    await saveConversation({
      id: "a",
      title: "Old",
      createdAt: 1,
      updatedAt: 1,
    });
    await renameConversation("a", "New");
    expect((await getConversation("a"))?.title).toBe("New");
  });

  it("deletes a conversation and its messages", async () => {
    await saveFullConversation("a", "T", [
      { role: "user", content: "hi" },
      { role: "assistant", content: "hello" },
    ]);
    await deleteConversation("a");
    expect(await getConversation("a")).toBeNull();
    expect(await getMessages("a")).toHaveLength(0);
  });

  it("clearAll wipes everything", async () => {
    await saveFullConversation("a", "T", [{ role: "user", content: "hi" }]);
    await saveFullConversation("b", "T2", [{ role: "user", content: "yo" }]);
    await clearAll();
    expect(await listConversations()).toHaveLength(0);
  });

  it("exports and re-imports a full snapshot", async () => {
    await saveFullConversation("a", "First", [
      { role: "user", content: "hi" },
      { role: "assistant", content: "peace be with you" },
    ]);
    const snapshot = await exportAll();
    expect(snapshot.conversations).toHaveLength(1);
    expect(snapshot.messages).toHaveLength(2);

    await clearAll();
    expect(await listConversations()).toHaveLength(0);

    const count = await importAll(snapshot);
    expect(count).toBe(1);
    expect(await listConversations()).toHaveLength(1);
    expect(await getMessages("a")).toHaveLength(2);
  });

  it("rejects an invalid import payload", async () => {
    await expect(
      // @ts-expect-error intentionally malformed
      importAll({ conversations: "nope" }),
    ).rejects.toThrow();
  });
});
