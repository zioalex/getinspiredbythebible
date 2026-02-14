import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Bible Inspiration Chat",
  description: "Find spiritual encouragement and guidance through Scripture",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Providers>
          <div className="min-h-screen overflow-x-hidden bg-gradient-to-b from-primary-50 to-white">
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
