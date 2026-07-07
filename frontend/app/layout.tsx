import type { Metadata } from "next";
import { Noto_Sans_KR, Inter } from "next/font/google";
import Navigation from "@/src/components/Navigation";
import DailyQuote from "@/src/components/DailyQuote";
import PageMarketTabs from "@/src/components/PageMarketTabs";
import { MarketProvider } from "@/src/contexts/MarketContext";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const notoKr = Noto_Sans_KR({ subsets: ["latin"], variable: "--font-noto-kr", weight: ["400", "500", "700", "900"], display: "swap" });

export const metadata: Metadata = {
  title: "AlphaDesk",
  description: "S&P 500 스마트머니 분석 대시보드",
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "AlphaDesk",
  },
  icons: {
    apple: "/icon-192.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={`dark ${inter.variable} ${notoKr.variable}`}>
      <body className="flex h-screen overflow-hidden font-sans" style={{ background: "var(--bg-base)" }}>
        <MarketProvider>
          <Navigation />
          {/* Right side: header + content */}
          <div className="flex flex-1 flex-col overflow-hidden">
            {/* Top header bar */}
            <header className="flex h-20 shrink-0 items-center gap-4 border-b px-4 pl-14 md:pl-4" style={{ background: "var(--bg-card)", borderColor: "var(--border)" }}>
              <DailyQuote />
            </header>
            {/* Page content */}
            <main className="flex-1 overflow-y-auto px-7 pt-8 pb-6">
              <PageMarketTabs />
              {children}
            </main>
          </div>
        </MarketProvider>
      </body>
    </html>
  );
}
