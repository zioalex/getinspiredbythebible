/**
 * Detects classic iPhone/iPod Safari user agents. iPadOS defaults to a
 * desktop-class ("Macintosh") user agent since iOS 13, so iPad is
 * intentionally not detected here — this targets the iPhone-specific
 * "Add to Home Screen" funnel the story describes, not iPad.
 */
export function isIOSUserAgent(userAgent: string | null): boolean {
  if (!userAgent) return false;
  return /iPhone|iPod/.test(userAgent);
}
