"use client";

import { Link } from "@/i18n/navigation";
import { useFooterLinks } from "./Footer";

// The chat page gives its <main> the full viewport height (h-dvh), so the
// page-level <Footer> rendered after it is always one screen below the fold
// and effectively unreachable (BITB-079). This compact row renders the same
// links inside the chat shell's own sticky bottom container instead.
export default function ChatFooterLinks() {
  const links = useFooterLinks();

  return (
    <nav
      data-testid="chat-footer-links"
      className="mt-1 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-[11px] text-gray-400"
    >
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="hover:text-primary-700 transition-colors"
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
