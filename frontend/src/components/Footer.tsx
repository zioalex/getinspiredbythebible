import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";

export default function Footer() {
  const tLegal = useTranslations("Legal");
  const tFooter = useTranslations("Footer");

  return (
    <footer className="border-t border-gray-200 bg-white py-6 mt-8">
      <div className="max-w-3xl mx-auto px-4 flex flex-wrap items-center justify-center gap-6 text-sm text-gray-500">
        <Link
          href="/privacy"
          className="hover:text-primary-700 transition-colors"
        >
          {tLegal("navPrivacy")}
        </Link>
        <Link
          href="/terms"
          className="hover:text-primary-700 transition-colors"
        >
          {tLegal("navTerms")}
        </Link>
        <Link
          href="/changelog"
          className="hover:text-primary-700 transition-colors"
        >
          {tFooter("changelog")}
        </Link>
      </div>
    </footer>
  );
}
