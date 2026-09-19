import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ExplainMyCode",
  description:
    "See what your Java code is actually doing. Step through execution and visualize variables, objects, references, and arrays.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
