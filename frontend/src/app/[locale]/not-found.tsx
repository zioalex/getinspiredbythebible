import { getTranslations } from "next-intl/server";
import { Link } from "@/i18n/navigation";

export default async function NotFound() {
  const t = await getTranslations("NotFound");

  return (
    <div className="flex flex-col items-center justify-center min-h-screen text-center px-4">
      <h1 className="text-4xl font-serif font-bold text-gray-800 mb-4">
        {t("title")}
      </h1>
      <p className="text-gray-500 mb-6">{t("body")}</p>
      <Link
        href="/"
        className="text-primary-700 underline hover:text-primary-900 transition-colors"
      >
        {t("backHome")}
      </Link>
    </div>
  );
}
