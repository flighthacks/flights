import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Autofare — Find the Cheapest Business Class Flights",
  description:
    "AI-powered flight search optimizer. Searches hundreds of route combinations to find the cheapest business class fares.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">{children}</body>
    </html>
  );
}
