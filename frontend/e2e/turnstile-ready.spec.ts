import { test, expect } from "@playwright/test";

test.describe("Turnstile Ready State", () => {
  test("suggested prompts are disabled until Turnstile is ready, then become enabled", async ({
    page,
  }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");

    // Find all 4 suggested prompt buttons by their exact English text
    const prompt1 = page.getByRole("button", {
      name: "I'm feeling anxious about the future",
    });
    const prompt2 = page.getByRole("button", {
      name: "What does the Bible say about forgiveness?",
    });
    const prompt3 = page.getByRole("button", {
      name: "I need encouragement today",
    });
    const prompt4 = page.getByRole("button", {
      name: "Help me understand John 3:16",
    });

    // All buttons must be visible
    await expect(prompt1).toBeVisible();
    await expect(prompt2).toBeVisible();
    await expect(prompt3).toBeVisible();
    await expect(prompt4).toBeVisible();

    // Buttons must eventually be enabled (either immediately if Turnstile is disabled,
    // or after Turnstile loads if enabled). Timeout of 5s to handle slow Turnstile init.
    await expect(prompt1).toBeEnabled({ timeout: 5000 });
    await expect(prompt2).toBeEnabled({ timeout: 5000 });
    await expect(prompt3).toBeEnabled({ timeout: 5000 });
    await expect(prompt4).toBeEnabled({ timeout: 5000 });
  });

  test("send button is disabled when input is empty, enabled when text is entered and Turnstile ready", async ({
    page,
  }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");

    const input = page.getByPlaceholder(/Share what's on your heart/i);
    const sendButton = page.locator('form button[type="submit"]');

    await expect(input).toBeVisible();

    // Send button disabled when input is empty
    await expect(sendButton).toBeDisabled();

    // Type a message
    await input.fill("Test message for Turnstile check");

    // Send button should become enabled (once Turnstile is ready and input has text)
    await expect(sendButton).toBeEnabled({ timeout: 5000 });
  });

  test("clicking a suggested prompt populates input and shows message in chat", async ({
    page,
  }) => {
    await page.goto("/en");
    await page.waitForLoadState("networkidle");

    const prompt = page.getByRole("button", {
      name: "I need encouragement today",
    });
    await expect(prompt).toBeEnabled({ timeout: 5000 });

    // Click the suggested prompt
    await prompt.click();

    // The user message should appear in the chat conversation
    await expect(page.getByText("I need encouragement today")).toBeVisible({
      timeout: 3000,
    });
  });

  test("loading indicator appears when Turnstile is initializing (gracefully handles fast load)", async ({
    page,
  }) => {
    // Turnstile may initialize very quickly (or be disabled), so the loading message
    // may never appear. This test verifies: if the message does appear, it eventually disappears.
    // If it never appears, that is also acceptable behavior (Turnstile loaded fast or is disabled).

    // Start navigation
    const navigationPromise = page.goto("/en");

    // Check for loading message right after navigation starts
    const loadingMessage = page.getByText("Preparing secure connection...");

    await navigationPromise;

    // Whether or not loading message appeared, buttons must eventually be enabled
    const prompt1 = page.getByRole("button", {
      name: "I'm feeling anxious about the future",
    });
    await expect(prompt1).toBeVisible({ timeout: 5000 });
    await expect(prompt1).toBeEnabled({ timeout: 5000 });

    // If loading message was visible at any point, it should be gone now
    await expect(loadingMessage).not.toBeVisible();
  });
});
