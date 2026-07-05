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
import { pageMetadata, buildJsonLd, SITE_NAME } from "@/lib/seo";
import { Providers } from "./providers";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import Footer from "@/components/Footer";
import WhatsNewModal from "@/components/WhatsNewModal";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Metadata" });

  // Combine the brand name with the tagline so the home page <title> is
  // descriptive rather than a bare 10-char brand string. Both halves come
  // from the locale message files, so this stays fully translated.
  const homeTitle = `${t("title")} — ${t("description")}`;

  return {
    ...pageMetadata({
      locale,
      path: "",
      title: homeTitle,
      description: t("description"),
    }),
    // Child pages set a plain title string and inherit this template, e.g.
    // "Privacy Policy · Vox Quieta". The home page renders `default`.
    title: {
      default: homeTitle,
      template: `%s · ${SITE_NAME}`,
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

  const t = await getTranslations({ locale, namespace: "Metadata" });
  const jsonLd = buildJsonLd({ locale, description: t("description") });

  // When the Turnstile site key is baked into the build, kick off the script
  // fetch from <head> so it races with the HTML download and the dynamic
  // <script> injection in TurnstileProvider hits a warm cache.
  const turnstileSiteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  const preloadTurnstile = !!turnstileSiteKey;

  return (
    <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: jsonLd }}
        />
        {preloadTurnstile && (
          <>
            <link
              rel="preconnect"
              href="https://challenges.cloudflare.com"
              crossOrigin="anonymous"
            />
            <link
              rel="preload"
              as="script"
              href="https://challenges.cloudflare.com/turnstile/v0/api.js"
              crossOrigin="anonymous"
            />
          </>
        )}
      </head>
      <body>
        <NextIntlClientProvider messages={messages}>
          <Providers>
            <ErrorBoundary>
              <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white flex flex-col overflow-x-hidden">
                <div className="flex-1">{children}</div>
                <Footer />
              </div>
              <WhatsNewModal />
            </ErrorBoundary>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
