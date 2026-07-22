import "fake-indexeddb/auto";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { screen, waitFor, fireEvent } from "@testing-library/react";
import { renderWithIntl } from "@/test/i18n-helpers";
import ConversationSidebar from "./ConversationSidebar";
import {
  saveFullConversation,
  clearAll,
  __resetDbCache,
} from "@/lib/conversationStore";

function renderSidebar(overrides: Record<string, unknown> = {}) {
  const props = {
    isOpen: true,
    onClose: vi.fn(),
    activeConversationId: null,
    onSelectConversation: vi.fn(),
    onNewConversation: vi.fn(),
    refreshSignal: 0,
    ...overrides,
  };
  renderWithIntl(<ConversationSidebar {...(props as never)} />);
  return props;
}

describe("ConversationSidebar", () => {
  beforeEach(async () => {
    __resetDbCache();
    await clearAll();
  });

  it("renders nothing when closed", () => {
    renderSidebar({ isOpen: false });
    expect(screen.queryByText("Conversation history")).toBeNull();
  });

  it("shows the privacy note and empty state", async () => {
    renderSidebar();
    expect(screen.getByText(/stored only on this device/i)).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/No saved conversations/i)).toBeInTheDocument(),
    );
  });

  it("lists saved conversations and opens one on click", async () => {
    await saveFullConversation("conv-1", "Finding peace", [
      { role: "user", content: "I feel lost" },
    ]);
    const props = renderSidebar();

    await waitFor(() =>
      expect(screen.getByText("Finding peace")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Finding peace"));
    expect(props.onSelectConversation).toHaveBeenCalledWith("conv-1");
  });

  it("fires onNewConversation from the new-conversation button", async () => {
    const props = renderSidebar();
    fireEvent.click(screen.getByText("New conversation"));
    expect(props.onNewConversation).toHaveBeenCalled();
  });

  it("reveals the export passphrase panel", async () => {
    await saveFullConversation("c", "T", [{ role: "user", content: "hi" }]);
    renderSidebar();
    await waitFor(() => screen.getByText("T"));
    fireEvent.click(screen.getByText("Export"));
    expect(screen.getByPlaceholderText(/passphrase/i)).toBeInTheDocument();
  });
});
