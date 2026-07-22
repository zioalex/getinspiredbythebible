/**
 * conversationCrypto — passphrase-based encryption for exporting/importing
 * conversation history.
 *
 * History is stored locally only (see conversationStore.ts). When a user wants
 * to move it between their own devices, they export an encrypted file: the
 * plaintext JSON is sealed with AES-GCM using a key derived from a passphrase
 * via PBKDF2. The passphrase is never stored; without it the file cannot be
 * read. This keeps the data "only in the user's hands" even in transit.
 */

const KDF_ITERATIONS = 210_000;
const SALT_BYTES = 16;
const IV_BYTES = 12;
const KEY_LENGTH_BITS = 256;

export const ENVELOPE_VERSION = 1;

/** Encrypted, self-describing container written to disk on export. */
export interface EncryptedEnvelope {
  v: number;
  kdf: "PBKDF2-SHA256";
  iter: number;
  salt: string; // base64
  iv: string; // base64
  data: string; // base64 AES-GCM ciphertext
}

export class DecryptionError extends Error {
  constructor(message = "Could not decrypt: wrong passphrase or corrupt file") {
    super(message);
    this.name = "DecryptionError";
  }
}

function getSubtle(): SubtleCrypto {
  const c = globalThis.crypto;
  if (!c || !c.subtle) {
    throw new Error("Web Crypto is not available in this environment");
  }
  return c.subtle;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

/** Encode a string to UTF-8 bytes guaranteed to be ArrayBuffer-backed. */
function utf8(text: string): Uint8Array<ArrayBuffer> {
  const src = new TextEncoder().encode(text);
  const out = new Uint8Array(src.length);
  out.set(src);
  return out;
}

async function deriveKey(
  passphrase: string,
  salt: Uint8Array<ArrayBuffer>,
): Promise<CryptoKey> {
  const subtle = getSubtle();
  const keyMaterial = await subtle.importKey(
    "raw",
    utf8(passphrase),
    "PBKDF2",
    false,
    ["deriveKey"],
  );
  return subtle.deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations: KDF_ITERATIONS,
      hash: "SHA-256",
    },
    keyMaterial,
    { name: "AES-GCM", length: KEY_LENGTH_BITS },
    false,
    ["encrypt", "decrypt"],
  );
}

/** Encrypt an arbitrary JSON-serialisable value into an envelope. */
export async function encryptExport(
  payload: unknown,
  passphrase: string,
): Promise<EncryptedEnvelope> {
  if (!passphrase) {
    throw new Error("A passphrase is required to encrypt the export");
  }
  const subtle = getSubtle();
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const iv = crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const key = await deriveKey(passphrase, salt);
  const plaintext = utf8(JSON.stringify(payload));
  const ciphertext = await subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    plaintext,
  );
  return {
    v: ENVELOPE_VERSION,
    kdf: "PBKDF2-SHA256",
    iter: KDF_ITERATIONS,
    salt: bytesToBase64(salt),
    iv: bytesToBase64(iv),
    data: bytesToBase64(new Uint8Array(ciphertext)),
  };
}

/** Decrypt an envelope back into its original value. Throws DecryptionError. */
export async function decryptImport<T = unknown>(
  envelope: EncryptedEnvelope,
  passphrase: string,
): Promise<T> {
  if (
    !envelope ||
    typeof envelope !== "object" ||
    envelope.kdf !== "PBKDF2-SHA256" ||
    typeof envelope.salt !== "string" ||
    typeof envelope.iv !== "string" ||
    typeof envelope.data !== "string"
  ) {
    throw new DecryptionError("Unrecognised or corrupt export file");
  }
  const subtle = getSubtle();
  try {
    const salt = base64ToBytes(envelope.salt);
    const iv = base64ToBytes(envelope.iv);
    const key = await deriveKey(passphrase, salt);
    const plaintext = await subtle.decrypt(
      { name: "AES-GCM", iv },
      key,
      base64ToBytes(envelope.data),
    );
    return JSON.parse(new TextDecoder().decode(plaintext)) as T;
  } catch {
    // Wrong passphrase -> GCM auth failure; corrupt base64/JSON -> parse error.
    throw new DecryptionError();
  }
}

/** True when the given object looks like one of our encrypted envelopes. */
export function isEncryptedEnvelope(
  value: unknown,
): value is EncryptedEnvelope {
  return (
    !!value &&
    typeof value === "object" &&
    (value as EncryptedEnvelope).kdf === "PBKDF2-SHA256" &&
    typeof (value as EncryptedEnvelope).data === "string"
  );
}
