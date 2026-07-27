import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { ArrowLeft, Github, Mail, BookOpen } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/seo";

const GITHUB_URL = "https://github.com/zioalex/getinspiredbythebible";
const ORIGIN_STORY_URL =
  "https://ai4you.sh/posts/Building-Something-That-Matters-How-Claude-Code-Helped-Me-Create-a-Bible-Inspiration-Chatbot/";
const CONTACT_EMAIL = "contact@voxquieta.org";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "About" });

  return pageMetadata({
    locale,
    path: "/about",
    title: t("metaTitle"),
    description: t("metaDescription"),
  });
}

export default async function AboutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "About" });

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-700 transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("backHome")}
      </Link>

      <h1 className="text-3xl font-bold text-primary-900 mb-4">{t("title")}</h1>
      <p className="text-lg text-gray-700 mb-12 leading-relaxed">
        {t("heroLead")}
      </p>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("whyTitle")}
        </h2>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("whyBody1")}</p>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("whyBody2")}</p>
        <p className="text-gray-600 leading-relaxed">{t("whyBody3")}</p>
      </section>

      <section className="mb-10 p-5 bg-primary-50/50 border border-primary-100 rounded-xl">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("notTitle")}
        </h2>
        <p className="text-gray-600 leading-relaxed">{t("notBody")}</p>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("todayTitle")}
        </h2>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("todayBody")}</p>
        <p className="text-sm text-gray-500 leading-relaxed">
          {t("todayContinuity")}
        </p>
      </section>

      <section className="mb-10">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">
          {t("builtTitle")}
        </h2>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("builtBody1")}</p>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("builtBody2")}</p>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("builtBody3")}</p>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-700 hover:text-primary-800 transition-colors"
        >
          <Github className="w-4 h-4" />
          {t("builtLinkLabel")}
        </a>
      </section>

      <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 bg-white border border-primary-100 rounded-xl mb-10">
        <div className="flex-shrink-0 flex items-center justify-center w-12 h-12 rounded-full bg-primary-50 text-primary-600">
          <BookOpen className="w-5 h-5" />
        </div>
        <div className="flex-1">
          <p className="font-semibold text-primary-900">
            {t("fullStoryTitle")}
          </p>
          <p className="text-sm text-gray-500">{t("fullStoryBody")}</p>
        </div>
        <a
          href={ORIGIN_STORY_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 inline-flex items-center justify-center gap-2 px-5 py-3 text-sm font-semibold text-white bg-teal-600 hover:bg-teal-700 rounded-full shadow-sm hover:shadow transition-all whitespace-nowrap"
        >
          {t("fullStoryLinkLabel")}
        </a>
      </div>

      <section className="border-t border-gray-100 pt-8 text-center">
        <h2 className="text-lg font-semibold text-gray-800 mb-2">
          {t("contactTitle")}
        </h2>
        <p className="text-gray-600 mb-4 leading-relaxed">{t("contactBody")}</p>
        <a
          href={`mailto:${CONTACT_EMAIL}`}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary-700 hover:text-primary-800 transition-colors"
        >
          <Mail className="w-4 h-4" />
          {t("contactLinkLabel")}
        </a>
      </section>
    </main>
  );
}
