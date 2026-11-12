import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "AlignAI — Semantic Resume Matcher",
  description:
    "AI-powered resume analysis that computes semantic similarity, identifies skill gaps, and generates an ATS-optimised resume tailored to your target role.",
  keywords: ["resume", "ATS", "job matching", "AI", "career", "semantic search"],
  authors: [{ name: "AlignAI" }],
  robots: "index, follow",
};

export const viewport: Viewport = {
  themeColor: "#08090e",
  colorScheme: "dark",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        {/* Ambient background */}
        <div className="bg-mesh" aria-hidden="true" />
        {/* Content */}
        <AuthProvider>
          <div className="relative z-10">{children}</div>
        </AuthProvider>
      </body>
    </html>
  );
}
