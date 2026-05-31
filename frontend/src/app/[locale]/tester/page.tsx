import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { Users, CheckCircle2, Smartphone, ArrowLeft } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/seo";
import {
  TESTER_GROUP_URL,
  TESTER_OPTIN_URL,
  PLAY_STORE_URL,
} from "@/lib/testerLinks";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Tester" });

  return pageMetadata({
    locale,
    path: "/tester",
    title: t("metaTitle"),
    description: t("metaDescription"),
  });
}

export default async function TesterPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "Tester" });

  const steps = [
    {
      icon: Users,
      title: t("step1Title"),
      body: t("step1Body"),
      cta: t("step1Button"),
      href: TESTER_GROUP_URL,
    },
    {
      icon: CheckCircle2,
      title: t("step2Title"),
      body: t("step2Body"),
      cta: t("step2Button"),
      href: TESTER_OPTIN_URL,
    },
    {
      icon: Smartphone,
      title: t("step3Title"),
      body: t("step3Body"),
      cta: t("step3Button"),
      href: PLAY_STORE_URL,
    },
  ];

  return (
    <main className="max-w-3xl mx-auto px-4 py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-primary-700 transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" />
        {t("backHome")}
      </Link>

      <h1 className="text-3xl font-bold text-primary-900 mb-3">{t("title")}</h1>
      <p className="text-gray-600 mb-10 leading-relaxed">{t("intro")}</p>

      <h2 className="text-lg font-semibold text-gray-800 mb-4">
        {t("stepsTitle")}
      </h2>

      <ol className="space-y-4">
        {steps.map((step, index) => {
          const Icon = step.icon;
          return (
            <li
              key={index}
              className="flex flex-col sm:flex-row sm:items-center gap-4 p-5 bg-white border border-primary-100 rounded-xl"
            >
              <div className="flex items-start gap-4 flex-1">
                <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-primary-50 text-primary-600">
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-medium text-gray-800">
                    <span className="text-primary-500 mr-2">{index + 1}.</span>
                    {step.title}
                  </p>
                  <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                    {step.body}
                  </p>
                </div>
              </div>
              <a
                href={step.href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-shrink-0 self-start sm:self-center inline-flex items-center justify-center px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors whitespace-nowrap"
              >
                {step.cta}
              </a>
            </li>
          );
        })}
      </ol>

      <p className="text-sm text-gray-400 mt-8 leading-relaxed">{t("note")}</p>
    </main>
  );
}
