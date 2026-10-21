import { useTranslations } from "next-intl";
import { Heart, type LucideIcon } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { donateUrl, type DonateRef } from "@/lib/donateUrl";

export interface FooterLink {
  href: string;
  label: string;
  external?: boolean;
  icon?: LucideIcon;
}

// Shared with ChatFooterLinks (a compact variant rendered inside the chat
// page's own scroll area, since the page-level Footer below is never
// reachable there — see BITB-079).
export function useFooterLinks({
  supportRef = "web-footer",
}: { supportRef?: DonateRef } = {}): FooterLink[] {
  const tLegal = useTranslations("Legal");
  const tFooter = useTranslations("Footer");

  return [
    { href: "/app", label: tFooter("getApp") },
    { href: "/about", label: tFooter("about") },
    { href: "/privacy", label: tLegal("navPrivacy") },
    { href: "/terms", label: tLegal("navTerms") },
    { href: "/changelog", label: tFooter("changelog") },
    {
      href: donateUrl(supportRef),
      label: tFooter("supportUs"),
      external: true,
      icon: Heart,
    },
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
              {link.icon && (
                <link.icon
                  aria-hidden="true"
                  className="inline-block w-3 h-3 mr-1 align-[-1px]"
                />
              )}
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
