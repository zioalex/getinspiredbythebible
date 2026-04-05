import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Legal | Bible Inspiration",
  description: "Legal documents for Get Inspired by the Bible.",
};

export default async function LegalIndexPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  return (
    <div className="min-h-screen px-4 py-10 sm:px-6 lg:px-8">
      <section className="mx-auto w-full max-w-2xl rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
        <h1 className="text-2xl font-semibold text-gray-900">Legal</h1>
        <p className="mt-3 text-sm text-gray-600">
          Public legal documents for Get Inspired by the Bible.
        </p>

        <div className="mt-6 space-y-3">
          <Link
            href={`/${locale}/privacy-policy`}
            className="block rounded-lg border border-gray-200 px-4 py-3 text-sm font-medium text-gray-800 hover:bg-gray-50"
          >
            Privacy Policy
          </Link>
          <Link
            href={`/${locale}/terms-of-service`}
            className="block rounded-lg border border-gray-200 px-4 py-3 text-sm font-medium text-gray-800 hover:bg-gray-50"
          >
            Terms of Service
          </Link>
        </div>
      </section>
    </div>
  );
}
