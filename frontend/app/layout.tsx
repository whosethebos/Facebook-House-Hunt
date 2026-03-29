// frontend/app/layout.tsx
import type { Metadata } from "next";
import { DM_Serif_Display, DM_Sans } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const displayFont = DM_Serif_Display({
  weight: ["400"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const bodyFont = DM_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "House Hunt",
  description: "Find your next home from Facebook group listings",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${displayFont.variable} ${bodyFont.variable}`}>
      <body style={{ fontFamily: "var(--font-body, DM Sans), system-ui, sans-serif" }}>
        <nav className="nav-bar">
          <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 24px", height: 60, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            {/* Logo */}
            <Link href="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 9,
                background: "linear-gradient(135deg, var(--accent), var(--accent-2))",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 15, flexShrink: 0,
                boxShadow: "0 2px 12px var(--accent-glow)",
              }}>
                ⌂
              </div>
              <span style={{
                fontFamily: "var(--font-display, DM Serif Display), Georgia, serif",
                fontSize: 19,
                color: "var(--text)",
                letterSpacing: "-0.02em",
                lineHeight: 1,
              }}>
                House Hunt
              </span>
            </Link>

            {/* CTA */}
            <Link href="/search/new" style={{ textDecoration: "none" }}>
              <button className="btn-primary" style={{ fontSize: 13, padding: "8px 16px" }}>
                <span style={{ fontSize: 16, lineHeight: 1, marginTop: -1 }}>+</span>
                New Search
              </button>
            </Link>
          </div>
        </nav>

        <main style={{ maxWidth: 1200, margin: "0 auto", padding: "32px 24px", position: "relative", zIndex: 1 }}>
          {children}
        </main>
      </body>
    </html>
  );
}
