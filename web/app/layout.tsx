import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Orbitron } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], weight: ["300", "400", "500", "600"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });
const orbitron = Orbitron({ subsets: ["latin"], weight: ["600", "700"], variable: "--font-orbitron" });

export const metadata: Metadata = {
  title: "DaVINCI Evidence Board",
  description: "Recorded runs of DaVINCI's verified RTL loop: frozen tests, mutation check, measured results.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable} ${orbitron.variable}`}>
      <body>{children}</body>
    </html>
  );
}
