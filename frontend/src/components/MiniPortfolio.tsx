"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import FlagIcon from "@/src/components/FlagIcon";

interface Position {
  symbol: string;
  name: string | null;
  market: string;
  shares: number;
  avg_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
}

interface Summary {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  market: string;   // 합계는 단일 시장일 때만 계산 (₩·$ 혼합 합산 방지)
}

export default function MiniPortfolio() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        // 포트폴리오 페이지와 동일한 소스: 실거래(my_trades) → 보유 계산 → 현재가 조회
        const trades = await fetch("/api/trades").then((r) => r.json());
        if (!Array.isArray(trades) || trades.length === 0) return;

        const map = new Map<string, { market: string; name: string | null; shares: number; cost: number }>();
        [...trades].reverse().forEach((t: any) => {
          const key = `${t.market}:${t.symbol}`;
          const cur = map.get(key) ?? { market: t.market, name: t.name, shares: 0, cost: 0 };
          if (t.type === "buy") {
            cur.cost = (cur.cost * cur.shares + t.price * t.shares) / (cur.shares + t.shares || 1);
            cur.shares += t.shares;
          } else {
            cur.shares = Math.max(0, cur.shares - t.shares);
          }
          map.set(key, cur);
        });
        const holdings = Array.from(map.entries())
          .filter(([, v]) => v.shares > 0)
          .map(([key, v]) => ({ symbol: key.split(":")[1], ...v }));
        if (holdings.length === 0) return;

        const keys = holdings.map((h) => `${h.market}:${h.symbol}`);
        const prices: Record<string, number | null> = await fetch(
          `/api/portfolio/prices?symbols=${keys.join(",")}`
        ).then((r) => r.json()).catch(() => ({}));

        const pos: Position[] = holdings.map((h) => {
          const price = prices[`${h.market}:${h.symbol}`] ?? null;
          return {
            symbol: h.symbol,
            name: h.name,
            market: h.market,
            shares: h.shares,
            avg_price: h.cost,
            current_price: price,
            unrealized_pnl: price != null ? (price - h.cost) * h.shares : null,
            unrealized_pnl_pct: price != null && h.cost > 0 ? price / h.cost - 1 : null,
          };
        });
        setPositions(pos);

        const markets = new Set(pos.map((p) => p.market));
        if (markets.size === 1) {
          const priced = pos.filter((p) => p.current_price != null);
          const cost = priced.reduce((s, p) => s + p.avg_price * p.shares, 0);
          const value = priced.reduce((s, p) => s + (p.current_price ?? 0) * p.shares, 0);
          if (cost > 0) {
            setSummary({
              total_cost: cost, total_value: value,
              total_pnl: value - cost, total_pnl_pct: (value - cost) / cost,
              market: pos[0].market,
            });
          }
        }
      } catch {
        // 조회 실패 시 "보유 종목 없음" 상태 유지
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return (
    <div className="p-3 animate-pulse" style={{ background: "#111009", height: 80 }} />
  );

  if (positions.length === 0) return (
    <div className="p-3" style={{ background: "#111009", border: "1px solid #262112" }}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#726b58" }}>내 포트폴리오</p>
        <Link href="/portfolio" className="text-[11px]" style={{ color: "#ffb020" }}>등록하기 →</Link>
      </div>
      <p className="text-[12px] text-center py-2" style={{ color: "#423e33" }}>보유 종목 없음</p>
    </div>
  );

  const pnlColor = (pct: number | null) => {
    if (pct == null) return "#726b58";
    if (pct <= -0.06) return "#f87171";
    if (pct < 0) return "#fb923c";
    return "#4ade80";
  };

  const fmt = (n: number) =>
    n >= 0 ? `+${(n * 100).toFixed(1)}%` : `${(n * 100).toFixed(1)}%`;

  return (
    <div className="p-3" style={{ background: "#111009", border: "1px solid #262112" }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-bold uppercase tracking-widest" style={{ color: "#726b58" }}>내 포트폴리오</p>
        <Link href="/portfolio" className="text-[11px]" style={{ color: "#ffb020" }}>전체 →</Link>
      </div>

      {/* Total P&L */}
      {summary && (
        <div className="flex items-baseline gap-2 mb-2.5 pb-2.5" style={{ borderBottom: "1px solid #262112" }}>
          <span
            className="text-lg font-black"
            style={{ color: summary.total_pnl >= 0 ? "#4ade80" : "#f87171" }}
          >
            {summary.total_pnl >= 0 ? "+" : "-"}
            {summary.market === "US" ? "$" : "₩"}
            {Math.abs(summary.total_pnl).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}
          </span>
          <span
            className="text-[12px] font-bold"
            style={{ color: summary.total_pnl_pct >= 0 ? "#4ade80" : "#f87171" }}
          >
            {fmt(summary.total_pnl_pct)}
          </span>
          <span className="text-[11px] ml-auto" style={{ color: "#423e33" }}>
            {positions.length}종목
          </span>
        </div>
      )}

      {/* Position list */}
      <div className="space-y-1.5">
        {positions.map(pos => {
          const pct = pos.unrealized_pnl_pct;
          const nearStop = pct != null && pct <= -0.06;
          return (
            <div key={`${pos.market}-${pos.symbol}`} className="flex items-center gap-2">
              <FlagIcon market={pos.market as "US" | "KR"} size={12} />
              <span className="text-[12px] font-bold flex-1 min-w-0 truncate" style={{ color: "#ece7d8" }}>
                {pos.symbol}
              </span>
              {nearStop && (
                <span className="text-[10px] font-bold px-1" style={{ background: "#f8717122", color: "#f87171" }}>
                  손절임박
                </span>
              )}
              <span className="text-[12px] font-bold tabular-nums shrink-0" style={{ color: pnlColor(pct) }}>
                {pct != null ? fmt(pct) : "—"}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
