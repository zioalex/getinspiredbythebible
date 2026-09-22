import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

// Placeholder Ko-fi page — a human must replace this with the real,
// permanent support URL before relying on it (BITB-074). NEXT_PUBLIC_DONATE_URL
// is documented in .env.*.example / scripts/env-manifest.yaml but is NOT YET
// wired into docker-compose.yml, frontend/Dockerfile, or azure-deploy.yml's
// build args — Next.js inlines NEXT_PUBLIC_* at build time, so setting the
// env var alone has no effect on a built/deployed app today. Until that
// plumbing lands, edit the fallback string below directly.
const DONATE_URL =
  process.env.NEXT_PUBLIC_DONATE_URL || "https://ko-fi.com/voxquieta";

export interface FooterLink {
  href: string;
  label: string;
  external?: boolean;
}

// Shared with ChatFooterLinks (a compact variant rendered inside the chat
// page's own scroll area, since the page-level Footer below is never
// reachable there — see BITB-079).
export function useFooterLinks(): FooterLink[] {
  const tLegal = useTranslations("Legal");
  const tFooter = useTranslations("Footer");

  return [
    { href: "/app", label: tFooter("getApp") },
    { href: "/about", label: tFooter("about") },
    { href: "/privacy", label: tLegal("navPrivacy") },
    { href: "/terms", label: tLegal("navTerms") },
    { href: "/changelog", label: tFooter("changelog") },
    { href: DONATE_URL, label: tFooter("supportUs"), external: true },
  ];
}

export default function Footer() {
  const links = useFooterLinks();

  return (
    <footer className="border-t border-gray-200 bg-white py-6 mt-8">
      <div className="max-w-3xl mx-auto px-4 flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500">
        {links.map((link) =>
          link.external ? (
            <a
              key={link.href}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary-700 transition-colors"
            >
              {link.label}
            </a>
          ) : (
            <Link
              key={link.href}
              href={link.href}
              className="hover:text-primary-700 transition-colors"
            >
              {link.label}
            </Link>
          ),
        )}
      </div>
    </footer>
  );
}
