import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useConversations } from "./useConversations";
import {
  saveFullConversation,
  clearAll,
  __resetDbCache,
} from "./conversationStore";

// jsdom's Blob/File don't implement text(); browsers do. Polyfill via FileReader.
if (typeof Blob !== "undefined" && !Blob.prototype.text) {
  Blob.prototype.text = function (this: Blob): Promise<string> {
    return new Promise((resolve, reject) => {
      const fr = new FileReader();
      fr.onload = () => resolve(String(fr.result));
      fr.onerror = () => reject(fr.error);
      fr.readAsText(this);
    });
  };
}

describe("useConversations", () => {
  let capturedBlob: Blob | null = null;

  beforeEach(async () => {
    __resetDbCache();
    await clearAll();
    capturedBlob = null;
    // jsdom lacks object-URL support; capture the exported blob instead.
    globalThis.URL.createObjectURL = vi.fn((blob: Blob) => {
      capturedBlob = blob;
      return "blob:mock";
    });
    globalThis.URL.revokeObjectURL = vi.fn();
    // Anchor.click() triggers jsdom "navigation not implemented" noise; stub it.
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads saved conversations", async () => {
    await saveFullConversation("a", "Hope", [{ role: "user", content: "hi" }]);
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.conversations).toHaveLength(1));
    expect(result.current.conversations[0].title).toBe("Hope");
  });

  it("renames and removes conversations", async () => {
    await saveFullConversation("a", "Old", [{ role: "user", content: "hi" }]);
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.conversations).toHaveLength(1));

    await act(async () => {
      await result.current.rename("a", "New");
    });
    expect(result.current.conversations[0].title).toBe("New");

    await act(async () => {
      await result.current.remove("a");
    });
    expect(result.current.conversations).toHaveLength(0);
  });

  it("wipes all conversations", async () => {
    await saveFullConversation("a", "A", [{ role: "user", content: "hi" }]);
    await saveFullConversation("b", "B", [{ role: "user", content: "yo" }]);
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.conversations).toHaveLength(2));

    await act(async () => {
      await result.current.wipeAll();
    });
    expect(result.current.conversations).toHaveLength(0);
  });

  it("round-trips through encrypted export and import", async () => {
    await saveFullConversation("a", "Grace", [
      { role: "user", content: "secret prayer" },
    ]);
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.conversations).toHaveLength(1));

    await act(async () => {
      await result.current.exportEncrypted("my passphrase");
    });
    expect(capturedBlob).not.toBeNull();
    const text = await capturedBlob!.text();
    expect(text).not.toContain("secret prayer"); // encrypted at rest

    await act(async () => {
      await result.current.wipeAll();
    });
    expect(result.current.conversations).toHaveLength(0);

    const file = new File([text], "history.json", {
      type: "application/json",
    });
    let imported = 0;
    await act(async () => {
      imported = await result.current.importEncrypted(file, "my passphrase");
    });
    expect(imported).toBe(1);
    expect(result.current.conversations).toHaveLength(1);
    expect(result.current.conversations[0].title).toBe("Grace");
  });

  it("rejects import with the wrong passphrase", async () => {
    await saveFullConversation("a", "Grace", [{ role: "user", content: "hi" }]);
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.conversations).toHaveLength(1));

    await act(async () => {
      await result.current.exportEncrypted("right pass");
    });
    const text = await capturedBlob!.text();
    const file = new File([text], "history.json");

    await expect(
      result.current.importEncrypted(file, "wrong pass"),
    ).rejects.toThrow();
  });
});
