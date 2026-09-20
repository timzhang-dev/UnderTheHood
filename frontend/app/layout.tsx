import type { Metadata } from "next";
import { Geist, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/*
 * Two faces, with a deliberate division of labour.
 *
 * Geist carries the interface and the explanations: neutral, quiet, gets out of
 * the way. JetBrains Mono carries everything that is *program state* — code,
 * values, types, variable names, heap ids — because that is where the product's
 * personality belongs, and because a beginner reading `obj_1` or `'c'` needs
 * unambiguous 1/l/I and 0/O.
 */
const sans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ExplainMyCode",
  description:
    "See what your Java code is actually doing. Step through execution and visualize variables, objects, references, and arrays.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-canvas text-ink antialiased">
        {children}
      </body>
    </html>
  );
}
