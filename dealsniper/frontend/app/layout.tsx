import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import Link from "next/link";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "Deal Sniper",
  description: "Flight deal finder — monitor prices and catch deals",
};

const navLinks = [
  { href: "/", label: "Dashboard" },
  { href: "/map", label: "Map" },
  { href: "/routes", label: "Routes" },
  { href: "/settings", label: "Settings" },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-background text-foreground`}
      >
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="w-56 shrink-0 border-r bg-card flex flex-col">
            <div className="p-4 border-b">
              <Link href="/" className="text-xl font-bold tracking-tight">
                Deal Sniper
              </Link>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="block px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="p-4 border-t text-xs text-muted-foreground">
              Deal Sniper v2.0
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-auto">
            <div className="max-w-7xl mx-auto p-6">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
