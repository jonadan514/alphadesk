"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useMarket } from "@/src/contexts/MarketContext";

// 사이드바 그룹 — 기능별이 아닌 사용자 투자 흐름 순서로 배치 (2026-07 UI 개선)
// 오늘(판단) → 시장 → 종목 → 투자 실행 → 관리
const NAV_GROUPS = [
  {
    label: "오늘",
    items: [
      { href: "/",          label: "개요",      emoji: "📊", color: "#ffb020" },
      { href: "/briefing",  label: "주간 브리핑", emoji: "📰", color: "#ffb020" },
    ],
  },
  {
    label: "시장",
    items: [
      { href: "/regime",    label: "시장 체제", emoji: "🧭", color: "#ffb020" },
      { href: "/sector",    label: "섹터 분석", emoji: "🏭", color: "#ffb020" },
    ],
  },
  {
    label: "종목",
    items: [
      { href: "/top-picks", label: "종목 분석", emoji: "🔎", color: "#ffb020" },
      { href: "/watchlist", label: "워치리스트",  emoji: "🔭", color: "#ffb020" },
    ],
  },
  {
    label: "투자 실행",
    items: [
      { href: "/workflow",  label: "매수 체크",  emoji: "✅", color: "#ffb020" },
      { href: "/portfolio", label: "포트폴리오",  emoji: "💼", color: "#ffb020" },
    ],
  },
  {
    label: "관리",
    items: [
      { href: "/risk",      label: "리스크",    emoji: "🛡️", color: "#ffb020" },
      { href: "/scorecard", label: "성적표",    emoji: "📈", color: "#ffb020" },
      { href: "/guide",     label: "가이드",     emoji: "📖", color: "#ffb020" },
    ],
  },
] as const;

function staleness(dateStr: string | null): { label: string; color: string } {
  if (!dateStr) return { label: "데이터 없음", color: "#423e33" };
  const days = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (days === 0) return { label: "오늘 업데이트", color: "#4ade80" };
  if (days === 1) return { label: "어제 업데이트", color: "#facc15" };
  if (days <= 3)  return { label: `${days}일 전 업데이트`, color: "#fb923c" };
  return { label: `${days}일 전 업데이트`, color: "#f87171" };
}

function SidebarInner({
  onClose,
  lastDate,
  market,
}: {
  onClose?: () => void;
  lastDate: string | null;
  market: string;
}) {
  const pathname = usePathname();
  const { label: freshnessLabel, color: freshnessColor } = staleness(lastDate);
  const isStale = lastDate
    ? Math.floor((Date.now() - new Date(lastDate).getTime()) / 86_400_000) > 1
    : true;

  return (
    <>
      {/* Logo */}
      <div
        className="flex h-20 shrink-0 items-center border-b px-5"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="text-2xl font-black tracking-tight" style={{ color: "#ffb020" }}>
          Alpha<span style={{ color: "#ece7d8" }}>Desk</span>
        </span>
        {onClose && (
          <button
            className="ml-auto p-2 rounded"
            onClick={onClose}
            style={{ color: "#726b58" }}
            aria-label="메뉴 닫기"
          >
            ✕
          </button>
        )}
      </div>

      {/* Nav groups */}
      <nav className="flex-1 overflow-y-auto min-h-0 py-3 px-2">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={gi > 0 ? "mt-4" : ""}>
            <p
              className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-widest"
              style={{ color: "#423e33" }}
            >
              {group.label}
            </p>
            {group.items.map(({ href, label: itemLabel, emoji, color: itemColor }) => {
              const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className="flex items-center gap-2.5 px-3 py-1.5 text-[13px] transition-all duration-150 relative my-0.5"
                  style={{
                    color: isActive ? "#ece7d8" : "#726b58",
                    background: isActive ? `${itemColor}15` : "transparent",
                    fontWeight: isActive ? 600 : 400,
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) e.currentTarget.style.background = "transparent";
                  }}
                >
                  {isActive && (
                    <span
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4"
                      style={{ background: itemColor }}
                    />
                  )}
                  <span
                    className="shrink-0 text-base leading-none"
                    style={{ opacity: isActive ? 1 : 0.6, transition: "opacity 0.15s" }}
                  >
                    {emoji}
                  </span>
                  <span style={{ letterSpacing: "0.01em" }}>{itemLabel}</span>
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* 내 대시보드 링크 */}
      <div className="shrink-0 px-2 pb-2">
        <a
          href="https://invest-dashboard-orpin.vercel.app"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2.5 px-3 py-1.5 text-[13px] transition-all duration-150"
          style={{ color: "#726b58" }}
          onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <span className="shrink-0 text-base leading-none" style={{ opacity: 0.6 }}>🌿</span>
          <span style={{ letterSpacing: "0.01em" }}>우리집 투자</span>
          <span className="ml-auto text-[11px]" style={{ color: "#423e33" }}>↗</span>
        </a>
      </div>

      {/* Bottom: data freshness */}
      <div className="shrink-0 border-t px-3 py-3" style={{ borderColor: "var(--border)" }}>
        <div
          className="px-3 py-2 flex items-center gap-2"
          style={{ background: "#0e0d08", border: "1px solid #262112" }}
        >
          <span
            className="h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: freshnessColor, boxShadow: `0 0 5px ${freshnessColor}` }}
          />
          <div className="min-w-0">
            <p className="text-[11px] font-medium truncate" style={{ color: freshnessColor }}>
              {freshnessLabel}
            </p>
            {isStale && (
              <p className="text-[11px] truncate" style={{ color: "#fb923c" }}>
                Actions에서 Daily Analysis 실행 권장
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

export default function Navigation() {
  const pathname = usePathname();
  const { market } = useMarket();
  const [lastDate, setLastDate] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    fetch("/api/data/status")
      .then((r) => r.json())
      .then((d) => {
        const date = market === "KR" ? (d.lastKrAnalysis ?? null) : (d.lastAnalysis ?? null);
        setLastDate(date);
      })
      .catch(() => {});
  }, [market]);

  // 페이지 이동 시 모바일 메뉴 닫기
  useEffect(() => {
    setIsOpen(false);
  }, [pathname]);

  return (
    <>
      {/* ── 데스크톱: 고정 사이드바 ── */}
      <aside
        className="hidden md:flex w-56 shrink-0 flex-col border-r h-full overflow-hidden"
        style={{ background: "#0a0a08", borderColor: "var(--border)" }}
      >
        <SidebarInner lastDate={lastDate} market={market} />
      </aside>

      {/* ── 모바일: 햄버거 버튼 ── */}
      <button
        className="md:hidden fixed top-0 left-0 z-[60] flex items-center justify-center w-14 h-20"
        onClick={() => setIsOpen(true)}
        aria-label="메뉴 열기"
      >
        <svg width="20" height="16" viewBox="0 0 20 16" fill="none">
          <rect y="0"  width="20" height="2" rx="1" fill="#ece7d8" />
          <rect y="7"  width="20" height="2" rx="1" fill="#ece7d8" />
          <rect y="14" width="20" height="2" rx="1" fill="#ece7d8" />
        </svg>
      </button>

      {/* ── 모바일: 백드롭 ── */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 z-[50] bg-black/60"
          onClick={() => setIsOpen(false)}
        />
      )}

      {/* ── 모바일: 슬라이드 드로어 ── */}
      <aside
        className={`md:hidden fixed inset-y-0 left-0 z-[55] flex flex-col w-64 border-r overflow-hidden transition-transform duration-200 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
        style={{ background: "#0a0a08", borderColor: "var(--border)" }}
      >
        <SidebarInner onClose={() => setIsOpen(false)} lastDate={lastDate} market={market} />
      </aside>
    </>
  );
}
