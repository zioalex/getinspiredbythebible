import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getLegalDocContent, getLegalDocDate } from "@/lib/legalDocs";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/seo";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Legal" });

  return pageMetadata({
    locale,
    path: "/privacy",
    title: t("privacyTitle"),
    description: t("privacyDescription"),
  });
}

export default async function PrivacyPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "Legal" });
  const content = getLegalDocContent("privacy-policy", locale);
  const lastUpdatedDate = getLegalDocDate("privacy-policy");
  const formattedDate = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(lastUpdatedDate);

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <h1 className="text-3xl font-bold text-primary-900 mb-2">
        {t("privacyTitle")}
      </h1>
      <p className="text-sm text-gray-500 mb-8">
        {t("lastUpdated", { date: formattedDate })}
      </p>
      <article className="prose prose-slate max-w-none">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </article>
    </main>
  );
}
