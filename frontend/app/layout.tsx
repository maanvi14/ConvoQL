import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ConvoQL — Conversational Analytics",
  description: "AI-powered data analyst with agentic SQL reasoning",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased overflow-hidden">
        {children}
      </body>
    </html>
  );
}
