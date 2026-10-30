/**
 * BITB-255: crisis-card region helpers.
 *
 * The backend picks emergency/crisis contacts by the caller's country
 * (CF-IPCountry first). A user can correct a wrong guess in the card's
 * "Not in {country}?" picker; that override lives only on this device
 * (localStorage, every access guarded) and is sent as `region` +
 * `region_override: true` on later requests.
 */

const STORAGE_KEY = "vq_crisis_region_override";
const ALPHA2 = /^[A-Za-z]{2}$/;

export function getCrisisRegionOverride(): string | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value && ALPHA2.test(value) ? value.toUpperCase() : null;
  } catch {
    return null;
  }
}

export function setCrisisRegionOverride(region: string | null): void {
  try {
    if (region && ALPHA2.test(region)) {
      window.localStorage.setItem(STORAGE_KEY, region.toUpperCase());
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // Storage blocked (private mode etc.): the override just won't persist.
  }
}

/** Region subtag of a BCP-47 tag ("pt-BR" -> "BR", "zh-Hans-CN" -> "CN"). */
export function regionFromTag(tag: string | undefined | null): string | null {
  if (!tag) return null;
  try {
    const region = new Intl.Locale(tag).region;
    if (region && ALPHA2.test(region)) return region.toUpperCase();
  } catch {
    // Fall through to the manual parse below.
  }
  const parts = tag.split(/[-_]/).slice(1);
  const found = parts.find((p) => ALPHA2.test(p));
  return found ? found.toUpperCase() : null;
}

export interface CrisisRequestFields {
  region?: string;
  region_override: boolean;
  supports_crisis_card: true;
}

/**
 * Fields added to every chat request body. An explicit override wins;
 * otherwise the device region (navigator.language, then the active locale).
 */
export function crisisRequestFields(locale?: string): CrisisRequestFields {
  const override = getCrisisRegionOverride();
  if (override) {
    return {
      region: override,
      region_override: true,
      supports_crisis_card: true,
    };
  }
  const navTag =
    typeof navigator !== "undefined" ? navigator.language : undefined;
  const region = regionFromTag(navTag) ?? regionFromTag(locale);
  return {
    ...(region ? { region } : {}),
    region_override: false,
    supports_crisis_card: true,
  };
}
