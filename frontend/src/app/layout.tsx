/**
 * Purpose: Define the shared HTML shell, fonts, metadata, and global styles.
 * Dependencies: Next.js metadata, next/font, and globals.css.
 * Used by: every route in the App Router.
 */

import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LanguageProvider } from "@/components/history/LanguageProvider";
import { dictionaries, languageOf } from "@/lib/historyLanguage";
import { Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Trust Infrastructure",
  description: "Portable trust for independent work.",
};

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const language = languageOf((await cookies()).get("history_language")?.value);
  return (
    <html
      lang={language}
      className={`${inter.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><LanguageProvider language={language} dictionary={dictionaries[language]}>{children}</LanguageProvider></body>
    </html>
  );
}
