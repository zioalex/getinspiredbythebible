import "./globals.css";
import type { Metadata } from "next";
import { SITE_URL } from "@/lib/seo";

// Resolves relative Open Graph / canonical URLs (set per page) to absolute ones.
export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
