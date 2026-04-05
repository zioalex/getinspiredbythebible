import type { Metadata } from "next";
import { getLegalMarkdown, getLegalMetadata } from "@/lib/legal-content";
import LegalDocument from "@/components/LegalDocument";

export async function generateMetadata(): Promise<Metadata> {
  return getLegalMetadata("privacy-policy");
}

export default async function PrivacyPolicyPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const markdown = await getLegalMarkdown("privacy-policy", locale);

  return <LegalDocument markdown={markdown} />;
}
