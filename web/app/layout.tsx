import type { Metadata } from "next";
import "./globals.css";

// Fonts come from Google Fonts at view time (next/font/google failed in a clean
// Turbopack build). Families are named in globals.css.
const FONTS = "https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800"
  + "&family=JetBrains+Mono:wght@400;500&display=swap";

export const viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
    { media: "(prefers-color-scheme: dark)", color: "#0B0F17" },
  ],
};

export const metadata: Metadata = {
  title: "DaVINCI Silicon · Evidence Board",
  description: "Verification plan and evidence for AI-written RTL: requirements traced to frozen, mutation-tested simulations, every attempt measured.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link rel="stylesheet" href={FONTS} />
      </head>
      <body>{children}</body>
    </html>
  );
}
