import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAlly — AI Trading Workstation",
  description: "FinAlly: a simulated AI-powered trading terminal.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-bg-base text-text-primary font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
