import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import {
  getMessages,
  getTranslations,
  setRequestLocale,
} from "next-intl/server";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import { routing } from "@/i18n/routing";
import { Providers } from "./providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Metadata" });

  return {
    title: t("title"),
    description: t("description"),
    alternates: {
      languages: {
        en: "/en",
        it: "/it",
        de: "/de",
        es: "/es",
        fr: "/fr",
        pt: "/pt",
        ar: "/ar",
        ru: "/ru",
        zh: "/zh",
        hi: "/hi",
        ko: "/ko",
      },
    },
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }

  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
      <body>
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <ErrorBoundary>
              <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
                {children}
              </div>
            </ErrorBoundary>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
