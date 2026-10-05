// Single place that composes the donate URL + per-surface `ref` param
// (BITB-168). The base is env-driven (BITB-157) with the live Ko-fi page as
// fallback. No "use client": usable from server and client components.
export const DONATE_BASE_URL =
  process.env.NEXT_PUBLIC_DONATE_URL || "https://ko-fi.com/voxquieta";

export type DonateRef =
  | "web-menu"
  | "web-footer"
  | "web-chat-footer"
  | "web-about";

export function donateUrl(
  ref: DonateRef,
  base: string = DONATE_BASE_URL,
): string {
  try {
    const url = new URL(base);
    url.searchParams.set("ref", ref);
    return url.toString();
  } catch {
    return base;
  }
}
