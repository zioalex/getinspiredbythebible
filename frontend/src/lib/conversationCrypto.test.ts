import { describe, it, expect } from "vitest";
import {
  encryptExport,
  decryptImport,
  isEncryptedEnvelope,
  DecryptionError,
} from "./conversationCrypto";

describe("conversationCrypto", () => {
  const payload = {
    version: 1,
    conversations: [{ id: "a", title: "Peace", createdAt: 1, updatedAt: 2 }],
    messages: [
      {
        id: "a:0",
        conversationId: "a",
        role: "user",
        content: "I feel anxious",
        versesCited: [],
        createdAt: 1,
      },
    ],
  };

  it("round-trips a payload with the correct passphrase", async () => {
    const envelope = await encryptExport(payload, "correct horse");
    expect(envelope.kdf).toBe("PBKDF2-SHA256");
    expect(typeof envelope.data).toBe("string");
    const decrypted = await decryptImport(envelope, "correct horse");
    expect(decrypted).toEqual(payload);
  });

  it("does not leak plaintext into the envelope", async () => {
    const envelope = await encryptExport(payload, "hunter2 pass");
    const serialized = JSON.stringify(envelope);
    expect(serialized).not.toContain("anxious");
    expect(serialized).not.toContain("Peace");
  });

  it("rejects a wrong passphrase with DecryptionError", async () => {
    const envelope = await encryptExport(payload, "correct horse");
    await expect(decryptImport(envelope, "wrong passphrase")).rejects.toThrow(
      DecryptionError,
    );
  });

  it("rejects a corrupt envelope", async () => {
    const envelope = await encryptExport(payload, "correct horse");
    envelope.data = envelope.data.slice(0, -8) + "AAAAAAAA";
    await expect(decryptImport(envelope, "correct horse")).rejects.toThrow(
      DecryptionError,
    );
  });

  it("rejects an unrecognised shape", async () => {
    await expect(
      // @ts-expect-error intentionally malformed
      decryptImport({ nope: true }, "x"),
    ).rejects.toThrow(DecryptionError);
  });

  it("requires a passphrase to encrypt", async () => {
    await expect(encryptExport(payload, "")).rejects.toThrow();
  });

  it("recognises its own envelopes", async () => {
    const envelope = await encryptExport(payload, "abc123");
    expect(isEncryptedEnvelope(envelope)).toBe(true);
    expect(isEncryptedEnvelope({ foo: "bar" })).toBe(false);
    expect(isEncryptedEnvelope(null)).toBe(false);
  });
});
