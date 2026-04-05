import type { Metadata } from "next";
import { getLegalMarkdown, getLegalMetadata } from "@/lib/legal-content";
import LegalDocument from "@/components/LegalDocument";

export async function generateMetadata(): Promise<Metadata> {
  return getLegalMetadata("terms-of-service");
}

export default async function TermsOfServicePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const markdown = await getLegalMarkdown("terms-of-service", locale);

  return <LegalDocument markdown={markdown} />;
}
