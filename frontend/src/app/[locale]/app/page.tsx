import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import {
  Smartphone,
  MessageCircle,
  Globe,
  ShieldCheck,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import { Link } from "@/i18n/navigation";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/seo";
import { PLAY_STORE_URL } from "@/lib/testerLinks";
import AppInstallCta from "@/components/AppInstallCta";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "App" });

  return pageMetadata({
    locale,
    path: "/app",
    title: t("metaTitle"),
    description: t("metaDescription"),
  });
}

export default async function AppStoryPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "App" });

  const features = [
    { icon: Smartphone, title: t("feature1Title"), body: t("feature1Body") },
    { icon: MessageCircle, title: t("feature2Title"), body: t("feature2Body") },
    { icon: Globe, title: t("feature3Title"), body: t("feature3Body") },
    { icon: ShieldCheck, title: t("feature4Title"), body: t("feature4Body") },
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

      {/* Official Play Store feature graphic as the hero */}
      <img
        src="/app-hero.png"
        alt={t("heroAlt")}
        width={1024}
        height={500}
        className="w-full h-auto rounded-2xl shadow-sm mb-8"
      />

      <h1 className="text-3xl font-bold text-primary-900 mb-4">{t("title")}</h1>

      <p className="text-lg text-gray-700 mb-4 leading-relaxed">
        {t("storyLead")}
      </p>
      <p className="text-gray-600 mb-4 leading-relaxed">{t("storyBody1")}</p>
      <p className="text-gray-600 mb-8 leading-relaxed">{t("storyBody2")}</p>

      {/* Primary call to action — Google Play on Android/desktop, iOS
          "Add to Home Screen" instructions on iPhone. No App Store badge
          here: there is no listing yet (BITB-088 adds one). The iOS/non-iOS
          branch is detected client-side in AppInstallCta so this page stays
          statically generated. */}
      <AppInstallCta
        iconAlt={t("iconAlt")}
        ctaSub={t("ctaSub")}
        ctaButton={t("ctaButton")}
        iosCtaTitle={t("iosCtaTitle")}
        iosCtaBody={t("iosCtaBody")}
        iosCtaSub={t("iosCtaSub")}
        playStoreUrl={PLAY_STORE_URL}
      />

      <h2 className="text-lg font-semibold text-gray-800 mb-4">
        {t("featuresTitle")}
      </h2>

      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-14">
        {features.map((feature, index) => {
          const Icon = feature.icon;
          return (
            <li
              key={index}
              className="flex items-start gap-4 p-5 bg-white border border-primary-100 rounded-xl"
            >
              <div className="flex-shrink-0 flex items-center justify-center w-10 h-10 rounded-full bg-primary-50 text-primary-600">
                <Icon className="w-5 h-5" />
              </div>
              <div>
                <p className="font-medium text-gray-800">{feature.title}</p>
                <p className="text-sm text-gray-500 mt-1 leading-relaxed">
                  {feature.body}
                </p>
              </div>
            </li>
          );
        })}
      </ul>

      {/* Beta participation — intentionally understated, secondary to the app CTA */}
      <div className="border-t border-gray-100 pt-6 text-center">
        <p className="text-sm text-gray-400">{t("betaLead")}</p>
        <Link
          href="/tester"
          className="inline-flex items-center gap-1 mt-1 text-sm text-gray-400 hover:text-primary-600 transition-colors"
        >
          {t("betaLink")}
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </main>
  );
}
