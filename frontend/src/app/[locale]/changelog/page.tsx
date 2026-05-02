import { readFileSync, existsSync } from "fs";
import { resolve } from "path";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { Metadata } from "next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Changelog" });
  return {
    title: t("title"),
    description: t("description"),
  };
}

export function generateStaticParams() {
  return ["en", "it", "de", "es", "fr", "pt", "ar", "ru", "zh", "hi", "ko"].map(
    (locale) => ({ locale }),
  );
}

export default async function ChangelogPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  const t = await getTranslations({ locale, namespace: "Changelog" });

  // Read from public/CHANGELOG.md, which the prebuild script copies from
  // the repo-root CHANGELOG.md. This works in both local dev and the
  // production standalone Docker image (which ships the public/ folder).
  const changelogPath = resolve(process.cwd(), "public", "CHANGELOG.md");
  const content = existsSync(changelogPath)
    ? readFileSync(changelogPath, "utf8")
    : null;

  return (
    <div className="min-h-screen bg-gradient-to-b from-primary-50 to-white">
      <div className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">{t("title")}</h1>
        {content ? (
          <article className="prose prose-gray max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </article>
        ) : (
          <p className="text-gray-500 italic">{t("empty")}</p>
        )}
      </div>
    </div>
  );
}
