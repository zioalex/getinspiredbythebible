"use client";

import { usePathname } from "@/i18n/navigation";
import Footer from "./Footer";

// The chat page (the site root) renders its own in-shell link row
// (ChatFooterLinks) because the page-level Footer is unreachable there
// (BITB-079, h-dvh chat + footer-after-content). Every other route keeps
// the normal page-level footer.
export default function FooterGate() {
  const pathname = usePathname();
  if (pathname === "/") return null;
  return <Footer />;
}
