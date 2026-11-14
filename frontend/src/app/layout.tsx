import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";

import Nav from "@/components/Nav";
import { AuthProvider } from "@/lib/auth";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Mock Interview",
  description: "Practise job interviews out loud and get scored feedback on content and clarity.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <Suspense fallback={<div className="h-14 border-b border-slate-200 dark:border-slate-800" />}>
            <Nav />
          </Suspense>
          <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
          <footer className="mx-auto w-full max-w-5xl px-4 py-6 text-xs text-slate-500">
            Questions and feedback by Gemini; speech-to-text by Whisper. Recordings are deleted after
            transcription.
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
