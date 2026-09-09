// BITB-115: the Bible-translation preference must be scoped per UI locale so
// switching languages never carries a stale translation choice into the new
// language. See docs/DONE/BITB-115-bible-version-not-reset-on-language-switch.md.
import { TranslationInfo } from "@/lib/api";

const LEGACY_KEY = "preferredTranslation";
const scopedKey = (locale: string) => `preferredTranslation:${locale}`;

export function getTranslationPreference(locale: string): string | null {
  try {
    return localStorage.getItem(scopedKey(locale));
  } catch {
    return null;
  }
}

export function setTranslationPreference(
  locale: string,
  code: string | null,
): void {
  try {
    if (code) {
      localStorage.setItem(scopedKey(locale), code);
    } else {
      localStorage.removeItem(scopedKey(locale));
    }
  } catch {
    // Storage unavailable — in-memory state for this session still works.
  }
}

// One-time migration from the pre-BITB-115 global preference: maps the legacy
// value to its own language (from `availableTranslations`) so it survives only
// there, never leaking into whichever locale happens to be active when this
// runs. A value whose language can't be resolved is discarded either way.
export function migrateLegacyTranslationPreference(
  availableTranslations: TranslationInfo[],
): void {
  try {
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy === null) return;
    const match = availableTranslations.find((t) => t.code === legacy);
    if (match) {
      const key = scopedKey(match.language_code);
      if (!localStorage.getItem(key)) {
        localStorage.setItem(key, legacy);
      }
    }
    localStorage.removeItem(LEGACY_KEY);
  } catch {
    // Storage unavailable — nothing to migrate.
  }
}
